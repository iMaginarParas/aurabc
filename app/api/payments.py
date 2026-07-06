import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
import json

from ..database import get_db
from ..models import Service, Order, Payment, EligibilityRequest
from ..services.notifications.dispatcher import dispatch_whatsapp_event
from ..schemas import (
    ServiceResponse,
    OrderCreate,
    OrderResponse,
    PaymentVerify,
    PaymentResponse,
    PaginatedPaymentsResponse
)
from ..services.payment_service import (
    create_order_transaction,
    verify_payment_signature_and_log
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["payments"])

@router.get("/api/services", response_model=List[ServiceResponse])
def get_services(db: Session = Depends(get_db)):
    """
    Returns all active services from the dynamic catalog database.
    """
    return db.query(Service).filter(Service.active == True).order_by(Service.display_order).all()

@router.get("/api/services/{slug}", response_model=ServiceResponse)
def get_service_by_slug(slug: str, db: Session = Depends(get_db)):
    """
    Returns details for a specific service slug.
    """
    service = db.query(Service).filter(Service.slug == slug, Service.active == True).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service package not found."
        )
    return service

@router.post("/api/payment/create-order", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_payment_order(
    payload: OrderCreate,
    db: Session = Depends(get_db)
):
    """
    Prepares a transaction checkout by generating a Razorpay Order and saving a pending record in DB.
    """
    service = db.query(Service).filter(Service.id == payload.service_id, Service.active == True).first()
    if not service:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requested service package is unavailable."
        )

    try:
        db_order = create_order_transaction(db, service, payload.user_id)
        return db_order
    except Exception as e:
        logger.error(f"Failed to generate transaction order: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to initiate transaction. Please try again."
        )

@router.post("/api/payment/verify", response_model=PaymentResponse)
def verify_payment(
    payload: PaymentVerify,
    db: Session = Depends(get_db)
):
    """
    Verifies the Razorpay payment signature and logs the payment as captured.
    """
    try:
        db_payment = verify_payment_signature_and_log(
            db=db,
            order_id=payload.razorpay_order_id,
            payment_id=payload.razorpay_payment_id,
            signature=payload.razorpay_signature,
            billing_name=payload.billing_name,
            email=payload.email
        )
        
        # Dispatch WhatsApp Notification
        try:
            profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == payload.email).first()
            phone = profile.phone if profile else "+919876543210"
            dispatch_whatsapp_event(
                db=db,
                user_id=db_payment.order.user_id or "guest_user",
                event_type="PAYMENT_SUCCESS",
                payload={
                    "student_name": payload.billing_name,
                    "amount": f"Rs {db_payment.amount}",
                    "service_name": db_payment.order.service.title
                },
                phone_number=phone
            )
        except Exception as dispatch_err:
            logger.error(f"Failed to auto-dispatch WhatsApp notification: {str(dispatch_err)}")

        return db_payment
    except ValueError as val_err:
        logger.error(f"Payment validation failed: {str(val_err)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as e:
        logger.error(f"Unexpected payment verification failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying the payment. Support has been notified."
        )

@router.post("/api/payment/webhook", status_code=status.HTTP_200_OK)
async def handle_payment_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Asynchronous Webhook endpoint listening for events from Razorpay to guarantee consistency.
    """
    body_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature") or ""
    
    logger.info("Webhook received from Razorpay.")
    
    # In production, verify the webhook signature here using a webhook secret key.
    # For now, we decode and parse the event payload
    try:
        event_data = json.loads(body_bytes.decode("utf-8"))
        event_type = event_data.get("event")
        
        logger.info(f"Processing Razorpay webhook event: {event_type}")
        
        if event_type == "payment.captured":
            payment_payload = event_data["payload"]["payment"]["entity"]
            order_id = payment_payload["order_id"]
            payment_id = payment_payload["id"]
            
            # Retrieve order
            db_order = db.query(Order).filter(Order.razorpay_order_id == order_id).first()
            if db_order and db_order.payment_status != "paid":
                logger.info(f"Webhook transitioning Order {db_order.id} status to 'paid'")
                db_order.payment_status = "paid"
                
                # Check if payment record already logged
                payment_exists = db.query(Payment).filter(Payment.razorpay_payment_id == payment_id).first()
                if not payment_exists:
                    receipt_no = f"INV_{payment_id.upper()}"
                    db_payment = Payment(
                        order_id=db_order.id,
                        razorpay_payment_id=payment_id,
                        razorpay_signature="WEBHOOK_VERIFIED",
                        amount=db_order.amount,
                        payment_method=payment_payload.get("method", "Webhook"),
                        status="captured",
                        receipt_number=receipt_no
                    )
                    db.add(db_payment)
                db.commit()
                
                # Dispatch Webhook Payment Success Notification
                try:
                    email = payment_payload.get("email")
                    profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == email).first() if email else None
                    phone = profile.phone if profile else payment_payload.get("contact", "+919876543210")
                    dispatch_whatsapp_event(
                        db=db,
                        user_id=db_order.user_id or "guest_user",
                        event_type="PAYMENT_SUCCESS",
                        payload={
                            "student_name": payment_payload.get("billing_address", {}).get("name", "Student Partner"),
                            "amount": f"Rs {db_order.amount}",
                            "service_name": db_order.service.title
                        },
                        phone_number=phone
                    )
                except Exception as dispatch_err:
                    logger.error(f"Failed to webhook-dispatch WhatsApp notification: {str(dispatch_err)}")
                
        elif event_type == "payment.failed":
            payment_payload = event_data["payload"]["payment"]["entity"]
            order_id = payment_payload.get("order_id")
            if order_id:
                db_order = db.query(Order).filter(Order.razorpay_order_id == order_id).first()
                if db_order:
                    logger.warning(f"Webhook transition Order {db_order.id} status to 'failed'")
                    db_order.payment_status = "failed"
                    db.commit()
                    
                    # Dispatch Webhook Payment Failed Notification
                    try:
                        email = payment_payload.get("email")
                        profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == email).first() if email else None
                        phone = profile.phone if profile else payment_payload.get("contact", "+919876543210")
                        dispatch_whatsapp_event(
                            db=db,
                            user_id=db_order.user_id or "guest_user",
                            event_type="PAYMENT_FAILED",
                            payload={
                                "student_name": "Student Partner",
                                "amount": f"Rs {db_order.amount}",
                                "service_name": db_order.service.title
                            },
                            phone_number=phone
                        )
                    except Exception as dispatch_err:
                        logger.error(f"Failed to webhook-dispatch fail WhatsApp notification: {str(dispatch_err)}")

        return {"status": "event processed"}
    except Exception as e:
        logger.error(f"Error handling webhook event: {str(e)}")
        # Webhook should always return 200 to prevent Razorpay from continuous retries
        return {"status": "error", "message": str(e)}

@router.get("/api/orders/{order_id}", response_model=OrderResponse)
def get_order_by_id(order_id: str, db: Session = Depends(get_db)):
    """
    Fetches the details of an order by ID.
    """
    db_order = db.query(Order).filter(Order.id == order_id).first()
    if not db_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found."
        )
    return db_order

@router.get("/api/payments/history", response_model=PaginatedPaymentsResponse)
def get_payment_history(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Fetches transaction payment audit history logs (Admin ready).
    """
    query = db.query(Payment)
    total = query.count()
    pages = (total + limit - 1) // limit if total > 0 else 0
    offset = (page - 1) * limit
    
    payments = query.order_by(desc(Payment.transaction_date)).offset(offset).limit(limit).all()

    return PaginatedPaymentsResponse(
        total=total,
        page=page,
        limit=limit,
        pages=pages,
        payments=payments
    )
