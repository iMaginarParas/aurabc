import razorpay
import uuid
import logging
from sqlalchemy.orm import Session
from datetime import datetime

from ..config import settings
from ..models import Service, Order, Payment

logger = logging.getLogger(__name__)

# Initialize Razorpay client
razorpay_client = None
if settings.openai_api_key: # Just checking settings
    # We will declare razorpay_key_id and razorpay_key_secret inside settings
    # For now, let's extract them from os.environ or configs dynamically
    import os
    rzp_id = os.getenv("RAZORPAY_KEY_ID") or ""
    rzp_secret = os.getenv("RAZORPAY_KEY_SECRET") or ""
    
    if rzp_id and rzp_secret:
        try:
            razorpay_client = razorpay.Client(auth=(rzp_id, rzp_secret))
            logger.info("Razorpay Client initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize Razorpay Client: {str(e)}")
    else:
        logger.warning("RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET missing. Running in payment simulation mode.")

def create_order_transaction(db: Session, service: Service, user_id: str = None) -> Order:
    """
    Creates an Order in the database and generates a corresponding order in Razorpay.
    """
    receipt_no = f"rcpt_{uuid.uuid4().hex[:12]}"
    amount_in_rupees = service.price
    amount_in_paise = int(amount_in_rupees * 100)
    
    razorpay_order_id = None
    
    if razorpay_client:
        try:
            logger.info(f"Creating Razorpay order for service: {service.title} of amount {amount_in_rupees} INR")
            order_data = {
                "amount": amount_in_paise,
                "currency": service.currency,
                "receipt": receipt_no,
                "payment_capture": 1
            }
            rzp_order = razorpay_client.order.create(data=order_data)
            razorpay_order_id = rzp_order["id"]
        except Exception as e:
            logger.error(f"Razorpay order generation failed: {str(e)}. Falling back to simulation mode.")
            
    # Mock fallback if Razorpay client is not configured or errors out
    if not razorpay_order_id:
        razorpay_order_id = f"order_sim_{uuid.uuid4().hex[:14]}"
        logger.info(f"Generated simulated Razorpay Order ID: {razorpay_order_id}")

    db_order = Order(
        user_id=user_id,
        service_id=service.id,
        razorpay_order_id=razorpay_order_id,
        amount=amount_in_rupees,
        currency=service.currency,
        payment_status="pending"
    )
    
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return db_order

def verify_payment_signature_and_log(
    db: Session, 
    order_id: str, 
    payment_id: str, 
    signature: str,
    billing_name: str,
    email: str
) -> Payment:
    """
    Verifies the Razorpay cryptographical signature on the backend.
    Saves the payment transaction in the DB and marks the order as paid.
    """
    # Find the corresponding order
    db_order = db.query(Order).filter(Order.razorpay_order_id == order_id).first()
    if not db_order:
        raise ValueError("Matching Order not found in database record logs.")

    is_verified = False
    import os
    app_env = os.getenv("APP_ENV", "production").lower()
    
    # Standard check for simulation mode
    if order_id.startswith("order_sim_"):
        if app_env == "development":
            logger.info("Bypassing cryptographic check for simulated checkout transaction in development.")
            is_verified = True
        else:
            logger.critical(f"Rejecting simulated transaction ID '{order_id}' in production mode.")
            raise ValueError("Simulated transactions are disabled in production.")
    elif razorpay_client:
        try:
            rzp_secret = os.getenv("RAZORPAY_KEY_SECRET") or ""
            params_dict = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature
            }
            # Verify signature using utility
            razorpay_client.utility.verify_payment_signature(params_dict)
            is_verified = True
            logger.info("Razorpay payment signature verified successfully.")
        except Exception as e:
            logger.error(f"Razorpay signature check failed: {str(e)}")
            raise ValueError("Cryptographic payment signature check failed. Transaction invalid.")
    else:
        # Fallback approve in dev environment if key is missing
        if app_env == "development":
            logger.info("No Razorpay keys set. Approving transaction in simulation sandbox.")
            is_verified = True
        else:
            logger.critical("Razorpay configuration keys missing in production mode. Verification failed.")
            raise ValueError("Razorpay configurations are missing on server. Cannot verify signature.")

    if not is_verified:
        raise ValueError("Invalid transaction signature.")

    # 1. Update Order Status
    db_order.payment_status = "paid"
    
    # 2. Log Payment audit record
    receipt_no = f"INV_{uuid.uuid4().hex[:10].upper()}"
    db_payment = Payment(
        order_id=db_order.id,
        razorpay_payment_id=payment_id,
        razorpay_signature=signature,
        amount=db_order.amount,
        payment_method="NetBanking/UPI/Card",
        status="captured",
        receipt_number=receipt_no
    )
    
    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)
    db.refresh(db_order)

    # 3. Send HTML Email Invoice using standard SMTP service
    email_html = generate_payment_confirmation_email_html(db_order, db_payment, billing_name, email)
    from .email_service import send_email
    send_email(email, f"Aura Routes AI Payment Receipt - {db_order.service_title}", email_html)

    return db_payment

def generate_payment_confirmation_email_html(order: Order, payment: Payment, billing_name: str, email: str) -> str:
    """
    Generates a professional HTML transaction invoice template for client confirmation.
    """
    support_email = os.getenv("SUPPORT_EMAIL", "support@auraroutes.com")
    
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Aura Routes AI Payment Invoice</title>
  <style>
    body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f9fafb; margin: 0; padding: 40px 0; color: #1f2937; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.03); overflow: hidden; }}
    .header {{ background-color: #2563eb; color: #ffffff; padding: 32px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 24px; font-weight: 800; letter-spacing: -0.5px; }}
    .header p {{ margin: 8px 0 0 0; font-size: 14px; color: #93c5fd; }}
    .content {{ padding: 32px; }}
    .greeting {{ font-size: 16px; font-weight: bold; margin-bottom: 20px; }}
    .summary-table {{ width: 100%; border-collapse: collapse; margin: 24px 0; }}
    .summary-table th {{ text-align: left; padding: 12px; border-bottom: 2px solid #f3f4f6; font-size: 11px; text-transform: uppercase; color: #9ca3af; font-weight: bold; }}
    .summary-table td {{ padding: 16px 12px; border-bottom: 1px solid #f3f4f6; font-size: 14px; }}
    .summary-table td.price {{ text-align: right; font-weight: bold; }}
    .summary-table th.price-hdr {{ text-align: right; }}
    .total-row {{ font-weight: bold; background-color: #f9fafb; }}
    .meta-box {{ background-color: #f3f4f6; border-radius: 12px; padding: 16px; font-size: 12px; color: #4b5563; margin-bottom: 24px; line-height: 1.6; }}
    .meta-box strong {{ color: #1f2937; }}
    .footer {{ text-align: center; font-size: 12px; color: #9ca3af; padding: 24px; border-t: 1px solid #f3f4f6; background-color: #fafafa; }}
    .cta-btn {{ display: inline-block; background-color: #2563eb; color: #ffffff !important; padding: 12px 28px; border-radius: 9999px; text-decoration: none; font-size: 14px; font-weight: bold; margin: 16px 0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Aura Routes AI</h1>
      <p>Payment Invoice & Confirmation</p>
    </div>
    <div class="content">
      <div class="greeting">Dear {billing_name},</div>
      <p>Thank you for your purchase. We have successfully processed your transaction, and your requested service is now active in your dashboard lifecycle logs.</p>
      
      <table class="summary-table">
        <thead>
          <tr>
            <th>Item Purchased</th>
            <th class="price-hdr">Price</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{order.service.title}<br><span style="font-size: 11px; color:#9ca3af;">{order.service.short_description}</span></td>
            <td class="price">₹{order.amount:.2f}</td>
          </tr>
          <tr class="total-row">
            <td>Total Paid (including GST)</td>
            <td class="price">₹{order.amount:.2f}</td>
          </tr>
        </tbody>
      </table>

      <div class="meta-box">
        <strong>TRANSACTION INFO:</strong><br>
        Invoice Receipt Number: {payment.receipt_number}<br>
        Razorpay Order ID: {order.razorpay_order_id}<br>
        Razorpay Payment ID: {payment.razorpay_payment_id}<br>
        Transaction Timestamp: {payment.transaction_date.strftime('%Y-%m-%d %H:%M:%S UTC')}
      </div>

      <div style="text-align: center;">
        <a href="https://auraroutes.com/dashboard" class="cta-btn">Access Your Purchased Service</a>
      </div>

      <p style="font-size:12px; color:#6b7280; text-align: center; margin-top:20px;">
        For technical assistance, email <a href="mailto:{support_email}">{support_email}</a>.
      </p>
    </div>
    <div class="footer">
      © {datetime.utcnow().year} Aura Routes AI • Innovation Arcade, Sector 5, HSR Layout, Bengaluru, India
    </div>
  </div>
</body>
</html>
"""

def seed_initial_services(db: Session):
    """
    Populates the Service catalog table if it is currently empty.
    """
    if db.query(Service).count() > 0:
        return
        
    logger.info("Seeding initial service packages into the database...")
    initial_services = [
        {
            "slug": "ai-sop-generator",
            "title": "AI SOP Generator",
            "short_description": "Auto-draft premium Statements of Purpose.",
            "description": "Utilize context-aware LLM architectures to compile structured Statements of Purpose aligned to destination-specific guidelines.",
            "price": 999.00,
            "currency": "INR",
            "icon": "FileText",
            "badge": "Popular",
            "display_order": 1,
            "features": ["3 Complete SOP drafts", "Grammar & structure checking", "Covers 15+ majors", "Instant export to PDF/DOC"]
        },
        {
            "slug": "ai-doc-checker",
            "title": "AI Document Checker",
            "short_description": "Validate transcripts and credentials.",
            "description": "Upload academic transcripts and recommendation files to scan for gaps against targeted university check gates.",
            "price": 499.00,
            "currency": "INR",
            "icon": "SearchCode",
            "badge": "Best Value",
            "display_order": 2,
            "features": ["5 Document scans", "Verify against target requirements", "GPA conversion calculator", "Feedback report"]
        },
        {
            "slug": "ai-visa-doc-checker",
            "title": "AI Visa Document Checker",
            "short_description": "Optimize visa files for approvals.",
            "description": "Perform structural audits of sponsor letters, logs, and passport scans to eliminate error points prior to submission.",
            "price": 699.00,
            "currency": "INR",
            "icon": "ShieldCheck",
            "badge": "New",
            "display_order": 3,
            "features": ["2 Complete visa scans", "Financial sponsor audit", "Immigration check rules", "Pre-refusal validation logs"]
        },
        {
            "slug": "ai-eligibility-premium",
            "title": "AI Eligibility Premium Report",
            "short_description": "Deep-dive immigration evaluation logs.",
            "description": "Acquire detailed breakdowns of strengths, weaknesses, university target lists, and visa probability meters.",
            "price": 799.00,
            "currency": "INR",
            "icon": "Sparkles",
            "badge": "Popular",
            "display_order": 4,
            "features": ["Comprehensive 10-page report", "Score card breakdown", "10 University matches", "Personalized improvements checklist"]
        },
        {
            "slug": "study-abroad-consultation",
            "title": "Study Abroad Consultation",
            "short_description": "1-on-1 advisor slot booking.",
            "description": "Book a live 45-minute virtual meeting with our senior advisors to map profiles and shortlists.",
            "price": 999.00,
            "currency": "INR",
            "icon": "GraduationCap",
            "badge": "Best Value",
            "display_order": 5,
            "features": ["45 Min zoom call", "Course & country mapping", "Scholarship guidance", "Application checklist planning"]
        },
        {
            "slug": "mbbs-abroad-consultation",
            "title": "MBBS Abroad Consultation",
            "short_description": "NMC approved medical pathways guidance.",
            "description": "Comprehensive mapping session for medical aspirants targeting approved medical colleges in Georgia, Kazakhstan, or Egypt.",
            "price": 1499.00,
            "currency": "INR",
            "icon": "Stethoscope",
            "badge": "Best Value",
            "display_order": 6,
            "features": ["60 Min NMC pathway call", "Eligibility checks and translations", "Collateral loan advice", "NEXT/USMLE prep guidance"]
        }
    ]

    for s_data in initial_services:
        db_service = Service(
            slug=s_data["slug"],
            title=s_data["title"],
            description=s_data["description"],
            short_description=s_data["short_description"],
            price=s_data["price"],
            currency=s_data["currency"],
            icon=s_data["icon"],
            badge=s_data["badge"],
            display_order=s_data["display_order"],
            features=s_data["features"]
        )
        db.add(db_service)
        
    db.commit()
    logger.info("Database seeding completed.")

def seed_dashboard_defaults(db: Session):
    """
    Populates settings, notifications, appointments, and activity logs for guest_user
    if they do not already exist (Module 7 bootstrap utility).
    """
    from ..models import UserSetting, Notification, Appointment, DashboardActivity
    
    # 1. User Settings Seed
    if db.query(UserSetting).filter(UserSetting.user_id == "guest_user").count() == 0:
        logger.info("Seeding default UserSetting record for guest_user...")
        settings_rec = UserSetting(
            user_id="guest_user",
            email_notifications=True,
            sms_notifications=False,
            marketing_emails=False,
            privacy_profile_public=False,
            language="English"
        )
        db.add(settings_rec)

    # 2. Notifications Seed
    if db.query(Notification).filter(Notification.user_id == "guest_user").count() == 0:
        logger.info("Seeding mock Notification records...")
        notifications_list = [
            Notification(
                user_id="guest_user",
                type="success",
                title="Premium Access Unlocked",
                message="Your payment for AI SOP Generator has been verified successfully. Start drafting!",
                is_read=False
            ),
            Notification(
                user_id="guest_user",
                type="info",
                title="Profile Audit Completed",
                message="Your student profile is currently at 80% completeness. Fill in remaining goals.",
                is_read=True
            )
        ]
        for notif in notifications_list:
            db.add(notif)

    # 3. Appointments Seed
    if db.query(Appointment).filter(Appointment.user_id == "guest_user").count() == 0:
        logger.info("Seeding mock Appointment records...")
        from datetime import datetime, timedelta
        appt = Appointment(
            user_id="guest_user",
            consultant_name="Dr. Aris Vane (Senior Study Advisor)",
            date_time=datetime.utcnow() + timedelta(days=1, hours=2),  # Scheduled for tomorrow
            meeting_link="https://zoom.us/j/983457193",
            status="upcoming",
            notes="Initial profile scoping, study destinations mapping, and scholarship evaluations."
        )
        db.add(appt)

    # 4. Activities Seed
    if db.query(DashboardActivity).filter(DashboardActivity.user_id == "guest_user").count() == 0:
        logger.info("Seeding mock DashboardActivity records...")
        activities = [
            DashboardActivity(user_id="guest_user", activity_type="Payment", description="Purchased AI SOP Generator package (₹999)."),
            DashboardActivity(user_id="guest_user", activity_type="SOP Draft", description="Generated initial Statement of Purpose draft."),
        ]
        for act in activities:
            db.add(act)

    db.commit()
    logger.info("Dashboard database defaults seeding completed.")

def seed_universities(db: Session):
    """
    Seeds a catalog of 20+ top global universities into the database (Module 8).
    """
    from ..models import University
    
    if db.query(University).count() > 0:
        return
        
    logger.info("Seeding top global universities database...")
    unis = [
        # USA
        {"name": "MIT (Massachusetts Institute of Technology)", "country": "USA", "world_ranking": 1, "tuition_fee_range": "$55,000 - $60,000 USD", "average_living_cost": "$18,000 - $22,000 USD", "admission_rate": "7%"},
        {"name": "Stanford University", "country": "USA", "world_ranking": 2, "tuition_fee_range": "$54,000 - $58,000 USD", "average_living_cost": "$19,000 - $23,000 USD", "admission_rate": "4%"},
        {"name": "Harvard University", "country": "USA", "world_ranking": 4, "tuition_fee_range": "$56,000 - $62,000 USD", "average_living_cost": "$20,000 - $24,000 USD", "admission_rate": "5%"},
        {"name": "NYU (New York University)", "country": "USA", "world_ranking": 38, "tuition_fee_range": "$52,000 - $58,000 USD", "average_living_cost": "$22,000 - $26,000 USD", "admission_rate": "12%"},
        # Canada
        {"name": "University of Toronto", "country": "Canada", "world_ranking": 21, "tuition_fee_range": "$38,000 - $58,000 CAD", "average_living_cost": "$18,000 - $22,000 CAD", "admission_rate": "43%"},
        {"name": "UBC (University of British Columbia)", "country": "Canada", "world_ranking": 34, "tuition_fee_range": "$36,000 - $52,000 CAD", "average_living_cost": "$17,000 - $20,000 CAD", "admission_rate": "50%"},
        {"name": "McGill University", "country": "Canada", "world_ranking": 30, "tuition_fee_range": "$35,000 - $48,000 CAD", "average_living_cost": "$16,000 - $19,000 CAD", "admission_rate": "46%"},
        {"name": "University of Waterloo", "country": "Canada", "world_ranking": 112, "tuition_fee_range": "$32,000 - $45,000 CAD", "average_living_cost": "$15,000 - $18,000 CAD", "admission_rate": "53%"},
        # UK
        {"name": "University of Oxford", "country": "UK", "world_ranking": 3, "tuition_fee_range": "£28,000 - £42,000 GBP", "average_living_cost": "£12,000 - £15,000 GBP", "admission_rate": "17%"},
        {"name": "University of Cambridge", "country": "UK", "world_ranking": 5, "tuition_fee_range": "£30,000 - £44,000 GBP", "average_living_cost": "£12,000 - £16,000 GBP", "admission_rate": "21%"},
        {"name": "Imperial College London", "country": "UK", "world_ranking": 6, "tuition_fee_range": "£32,000 - £40,000 GBP", "average_living_cost": "£14,000 - £18,000 GBP", "admission_rate": "15%"},
        {"name": "UCL (University College London)", "country": "UK", "world_ranking": 9, "tuition_fee_range": "£26,000 - £36,000 GBP", "average_living_cost": "£13,000 - £17,000 GBP", "admission_rate": "29%"},
        # Germany
        {"name": "TUM (Technical University of Munich)", "country": "Germany", "world_ranking": 37, "tuition_fee_range": "€0 - €6,000 EUR", "average_living_cost": "€11,000 - €13,000 EUR", "admission_rate": "8%"},
        {"name": "LMU Munich (Ludwig Maximilian University)", "country": "Germany", "world_ranking": 54, "tuition_fee_range": "€0 - €3,000 EUR", "average_living_cost": "€11,000 - €12,000 EUR", "admission_rate": "10%"},
        {"name": "Heidelberg University", "country": "Germany", "world_ranking": 65, "tuition_fee_range": "€0 - €3,000 EUR", "average_living_cost": "€10,000 - €12,000 EUR", "admission_rate": "15%"},
        # Australia
        {"name": "University of Melbourne", "country": "Australia", "world_ranking": 14, "tuition_fee_range": "$36,000 - $50,000 AUD", "average_living_cost": "$21,000 - $25,000 AUD", "admission_rate": "70%"},
        {"name": "University of Sydney", "country": "Australia", "world_ranking": 19, "tuition_fee_range": "$38,000 - $48,000 AUD", "average_living_cost": "$22,000 - $26,000 AUD", "admission_rate": "30%"},
        {"name": "UNSW Sydney", "country": "Australia", "world_ranking": 19, "tuition_fee_range": "$35,000 - $46,000 AUD", "average_living_cost": "$21,000 - $24,000 AUD", "admission_rate": "60%"},
        # Ireland
        {"name": "Trinity College Dublin", "country": "Ireland", "world_ranking": 81, "tuition_fee_range": "€18,000 - €26,000 EUR", "average_living_cost": "€12,000 - €15,000 EUR", "admission_rate": "33%"},
        {"name": "UCD (University College Dublin)", "country": "Ireland", "world_ranking": 171, "tuition_fee_range": "€16,000 - €24,000 EUR", "average_living_cost": "€11,000 - €14,000 EUR", "admission_rate": "38%"},
        # New Zealand
        {"name": "University of Auckland", "country": "New Zealand", "world_ranking": 68, "tuition_fee_range": "$32,000 - $44,000 NZD", "average_living_cost": "$18,000 - $22,000 NZD", "admission_rate": "45%"}
    ]
    
    for u in unis:
        uni_rec = University(
            name=u["name"],
            country=u["country"],
            world_ranking=u["world_ranking"],
            tuition_fee_range=u["tuition_fee_range"],
            average_living_cost=u["average_living_cost"],
            admission_rate=u["admission_rate"]
        )
        db.add(uni_rec)
        
    db.commit()
    logger.info("Universities seeded successfully.")

def seed_applications(db: Session):
    """
    Seeds a set of mock university applications, tasks, timelines, and document checklists (Module 9).
    """
    from ..models import Application, ApplicationTask, ApplicationDocument, ApplicationTimeline, ApplicationCalendarItem
    
    if db.query(Application).count() > 0:
        return
        
    logger.info("Seeding application pipeline records...")
    
    # 1. University of Toronto Application
    uoft = Application(
        user_id="guest_user",
        university="University of Toronto",
        country="Canada",
        course="M.S. in Computer Science",
        degree="Master's",
        intake="Fall 2026",
        tuition_fee="$38,000 CAD",
        application_fee="$125 CAD",
        deadline="2026-01-15",
        current_status="Shortlisted",
        priority="High",
        notes="High ranking. Require GIC account setup and study permit application logs."
    )
    db.add(uoft)
    db.commit() # Commit to get ID
    db.refresh(uoft)
    
    # Add tasks
    db.add(ApplicationTask(application_id=uoft.id, title="Draft Statement of Purpose", status="completed", due_date="2025-10-10", priority="High", notes="Verify ATS structure."))
    db.add(ApplicationTask(application_id=uoft.id, title="Request Academic LORs", status="pending", due_date="2025-11-01", priority="Medium", notes="Needs signs from HOD."))
    db.add(ApplicationTask(application_id=uoft.id, title="Pay application fees", status="pending", due_date="2026-01-14", priority="High"))
    
    # Add documents
    db.add(ApplicationDocument(application_id=uoft.id, document_name="Passport", status="Uploaded", file_path="/static/uploads/passport_scan.pdf"))
    db.add(ApplicationDocument(application_id=uoft.id, document_name="SOP", status="Uploaded", file_path="/static/uploads/sop_uoft.pdf"))
    db.add(ApplicationDocument(application_id=uoft.id, document_name="Transcripts", status="Pending"))
    
    # Add timeline
    db.add(ApplicationTimeline(application_id=uoft.id, event_title="Application Created", event_description="Shortlisted course for Fall 2026 intake term."))
    db.add(ApplicationTimeline(application_id=uoft.id, event_title="SOP Uploaded", event_description="Uploaded AI generated draft."))
    
    # Add calendar
    db.add(ApplicationCalendarItem(application_id=uoft.id, event_title="U of T Application Deadline", event_type="Deadline", event_date="2026-01-15"))


    # 2. TUM Application
    tum = Application(
        user_id="guest_user",
        university="TUM (Technical University of Munich)",
        country="Germany",
        course="M.S. in Software Engineering",
        degree="Master's",
        intake="Fall 2026",
        tuition_fee="€0 EUR",
        application_fee="€0 EUR",
        deadline="2026-05-31",
        current_status="Interested",
        priority="Medium",
        notes="No tuition fee program. Focus on coding challenges."
    )
    db.add(tum)
    db.commit()
    db.refresh(tum)
    
    # Add tasks
    db.add(ApplicationTask(application_id=tum.id, title="Get transcripts certified", status="pending", due_date="2025-12-15", priority="Medium"))
    
    # Add documents
    db.add(ApplicationDocument(application_id=tum.id, document_name="Passport", status="Uploaded"))
    db.add(ApplicationDocument(application_id=tum.id, document_name="Resume", status="Pending"))
    
    # Add timeline
    db.add(ApplicationTimeline(application_id=tum.id, event_title="Application Created", event_description="Identified no tuition fees software course."))
    
    # Add calendar
    db.add(ApplicationCalendarItem(application_id=tum.id, event_title="TUM Application Deadline", event_type="Deadline", event_date="2026-05-31"))
    
    db.commit()
    logger.info("Application seeds populated successfully.")

def seed_scholarships(db: Session):
    """
    Seeds a catalog of top global scholarships into the database (Module 11).
    """
    from ..models import Scholarship
    
    if db.query(Scholarship).count() > 0:
        return
        
    logger.info("Seeding global scholarships database catalog...")
    scholars = [
        {
            "name": "Fulbright-Nehru Master's Fellowships",
            "provider": "USIEF (United States-India Educational Foundation)",
            "country": "USA",
            "university": "All USA Universities",
            "funding_amount": "$45,000 USD / Year",
            "coverage": "Full Tuition, Living Stipend, Travel Airfare, Health Insurance",
            "eligibility_criteria": "GPA 80% equivalent. Minimum 3 years work experience. IELTS 7.0+ overall.",
            "difficulty_level": "High",
            "deadline": "2026-05-15",
            "website_placeholder": "https://www.usief.org.in"
        },
        {
            "name": "Commonwealth Master's Scholarships",
            "provider": "CSC (Commonwealth Scholarship Commission)",
            "country": "UK",
            "university": "All UK Universities",
            "funding_amount": "£25,000 GBP / Year",
            "coverage": "Full Tuition, Airfare, Monthly Living Allowance, Thesis Grant",
            "eligibility_criteria": "GPA 85% equivalent. Cannot afford to study without this funding.",
            "difficulty_level": "High",
            "deadline": "2025-10-15",
            "website_placeholder": "https://cscuk.fcdo.gov.uk"
        },
        {
            "name": "DAAD Development-Related Postgraduate Courses (EPOS)",
            "provider": "DAAD (German Academic Exchange Service)",
            "country": "Germany",
            "university": "All German Public Universities",
            "funding_amount": "€11,000 EUR / Year",
            "coverage": "Monthly Stipend (€934), Travel Allowance, Health Insurance",
            "eligibility_criteria": "At least 2 years professional experience. IELTS 6.5+.",
            "difficulty_level": "Medium",
            "deadline": "2025-11-30",
            "website_placeholder": "https://www.daad.de"
        },
        {
            "name": "Ontario Graduate Scholarship (OGS)",
            "provider": "Government of Ontario",
            "country": "Canada",
            "university": "Ontario Universities (U of T, Waterloo, McMaster)",
            "funding_amount": "$15,000 CAD / Year",
            "coverage": "Partial Tuition Offset",
            "eligibility_criteria": "A- average in last 2 years. Registered in graduate studies.",
            "difficulty_level": "Medium",
            "deadline": "2026-01-31",
            "website_placeholder": "https://osap.gov.on.ca"
        },
        {
            "name": "Chevening Scholarships",
            "provider": "FCDO (Foreign, Commonwealth & Development Office)",
            "country": "UK",
            "university": "All UK Universities",
            "funding_amount": "£28,000 GBP / Year",
            "coverage": "Full Tuition, Living Allowance, Arrival/Departure Allowances",
            "eligibility_criteria": "At least 2 years work experience. Commitment to return to home country for 2 years.",
            "difficulty_level": "High",
            "deadline": "2025-11-05",
            "website_placeholder": "https://www.chevening.org"
        }
    ]

    for s in scholars:
        db_s = Scholarship(
            name=s["name"],
            provider=s["provider"],
            country=s["country"],
            university=s["university"],
            funding_amount=s["funding_amount"],
            coverage=s["coverage"],
            eligibility_criteria=s["eligibility_criteria"],
            difficulty_level=s["difficulty_level"],
            deadline=s["deadline"],
            website_placeholder=s["website_placeholder"]
        )
        db.add(db_s)
        
    db.commit()
    logger.info("Scholarship catalog seeded successfully.")

def seed_whatsapp_defaults(db: Session):
    """
    Seeds default notification templates and preferences for guest_user (Module 9 Extension).
    """
    from ..models import NotificationTemplate, UserNotificationPreference
    
    # 1. Templates Seeding
    if db.query(NotificationTemplate).count() == 0:
        logger.info("Seeding reusable WhatsApp templates...")
        templates = [
            {
                "name": "Welcome Message",
                "event": "STUDENT_REGISTERED",
                "template": "Hi {{student_name}} 👋\n\nWelcome to Aura Routes AI! Prepare your study abroad files with premium AI assistance.\n\nBest,\nAura Routes AI"
            },
            {
                "name": "Eligibility Completion",
                "event": "ELIGIBILITY_COMPLETED",
                "template": "Hi {{student_name}} 👋\n\nYour AI Study Eligibility Report has been successfully generated. You can now view it on your dashboard.\n\nBest,\nAura Routes AI Team"
            },
            {
                "name": "Payment Successful Confirmation",
                "event": "PAYMENT_SUCCESS",
                "template": "Hi {{student_name}} 👋\n\nThank you! We've received your payment of {{amount}} for the {{service_name}} package.\n\nThank you,\nAura Routes AI"
            },
            {
                "name": "Payment Failed Warning",
                "event": "PAYMENT_FAILED",
                "template": "Hi {{student_name}} 👋\n\nAlert! Your payment transaction of {{amount}} for {{service_name}} was declined.\n\nSupport,\nAura Routes AI"
            },
            {
                "name": "SOP Ready Alert",
                "event": "SOP_GENERATED",
                "template": "Hi {{student_name}} 👋\n\nYour AI Statement of Purpose (SOP) is ready for download in your workspace. Check it out!\n\nBest,\nAura Routes AI"
            },
            {
                "name": "Document Scan Audit Completed",
                "event": "DOCUMENT_CHECK_COMPLETED",
                "template": "Hi {{student_name}} 👋\n\nOur AI Document Checker has finished analyzing your uploaded files. Gaps report is generated.\n\nBest,\nAura Routes AI"
            },
            {
                "name": "Consultation Booked Alert",
                "event": "CONSULTATION_BOOKED",
                "template": "Hi {{student_name}} 👋\n\nYour consultation session with {{consultant_name}} has been booked for {{date_time}}.\n\nBest,\nAura Routes AI"
            }
        ]
        for t in templates:
            db.add(NotificationTemplate(
                name=t["name"],
                event=t["event"],
                template=t["template"],
                active=True
            ))

    # 2. User opt-in preferences defaults
    if db.query(UserNotificationPreference).filter(UserNotificationPreference.user_id == "guest_user").count() == 0:
        logger.info("Seeding default UserNotificationPreference opt-in categories for guest_user...")
        db.add(UserNotificationPreference(
            user_id="guest_user",
            enable_whatsapp=True,
            categories=["eligibility", "payments", "sop", "documents", "consultations", "account", "general"]
        ))

    db.commit()
    logger.info("WhatsApp default configurations seeded successfully.")





