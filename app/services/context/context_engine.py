import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import Dict, Any

from app.models import (
    EligibilityRequest,
    EligibilityResult,
    SOPDocument,
    VisaDocumentCheck,
    SavedScholarship,
    UploadedDocument,
    Order,
    Service,
    Profile,
    AcademicProfile,
    StudyPreference,
    FinancialProfile,
    StudentDocument
)

logger = logging.getLogger(__name__)

class ContextEngine:
    @staticmethod
    def get_student_context_data(db: Session, user_id: str, email: str) -> Dict[str, Any]:
        """
        Gathers all student milestones, profiles, results, documents, and payments
        and returns a structured dictionary of context data.
        """
        context = {
            "profile": None,
            "eligibility_result": None,
            "latest_sop": None,
            "latest_visa_check": None,
            "saved_scholarships": [],
            "uploaded_documents": [],
            "payments_and_services": [],
            "journey_stage": "Profile Scoping"
        }

        try:
            # 1. Profile information
            master_profile = db.query(Profile).filter(Profile.user_id == user_id).first()
            if master_profile:
                ap = master_profile.academic_profile
                sp = master_profile.study_preferences
                fp = master_profile.financial_profile
                
                english_exam = "None"
                english_score = None
                if ap:
                    if ap.ielts_score is not None:
                        english_exam = "IELTS"
                        english_score = ap.ielts_score
                    elif ap.toefl_score is not None:
                        english_exam = "TOEFL"
                        english_score = ap.toefl_score
                    elif ap.pte_score is not None:
                        english_exam = "PTE"
                        english_score = ap.pte_score
                    elif ap.duolingo_score is not None:
                        english_exam = "Duolingo"
                        english_score = ap.duolingo_score

                context["profile"] = {
                    "full_name": master_profile.full_name,
                    "email": master_profile.email,
                    "phone": master_profile.phone,
                    "country_residence": master_profile.country_residence,
                    "nationality": master_profile.nationality,
                    "qualification": ap.highest_qualification if ap else None,
                    "gpa_10th": ap.gpa_10th if ap else 0.0,
                    "gpa_12th": ap.gpa_12th if ap else 0.0,
                    "grad_year": ap.grad_year if ap else None,
                    "english_exam": english_exam,
                    "english_score": english_score,
                    "preferred_country": ", ".join(sp.preferred_countries) if (sp and sp.preferred_countries) else None,
                    "preferred_course": ", ".join(sp.preferred_courses) if (sp and sp.preferred_courses) else None,
                    "preferred_intake": sp.target_intake if sp else None,
                    "budget_range": sp.budget if sp else None,
                    "work_experience": sum(item.get("years", 0) for item in ap.work_experience) if (ap and ap.work_experience and isinstance(ap.work_experience, list)) else 0.0,
                    "gap_years": ap.backlogs if ap else 0,
                    "neet_score": ap.neet_score if ap else None,
                    "passport_available": master_profile.passport_number is not None and master_profile.passport_number != ""
                }

                # 2. Eligibility results (nested migration)
                result = db.query(EligibilityResult).filter(EligibilityResult.request_id == master_profile.id).first()
                if result:
                    context["eligibility_result"] = {
                        "overall_score": result.overall_score,
                        "admission_probability": result.admission_probability,
                        "scholarship_potential": result.scholarship_potential,
                        "visa_readiness": result.visa_readiness,
                        "strengths": result.strengths,
                        "weaknesses": result.weaknesses,
                        "suggested_improvements": result.suggested_improvements,
                        "recommended_countries": result.recommended_countries,
                        "recommended_universities": result.recommended_universities
                    }
            else:
                profile = db.query(EligibilityRequest).filter(EligibilityRequest.email == email).first()
                if profile:
                    context["profile"] = {
                        "full_name": profile.full_name,
                        "email": profile.email,
                        "phone": profile.phone,
                        "country_residence": profile.country_residence,
                        "nationality": profile.nationality,
                        "qualification": profile.qualification,
                        "gpa_10th": profile.gpa_10th,
                        "gpa_12th": profile.gpa_12th,
                        "grad_year": profile.grad_year,
                        "english_exam": profile.english_exam,
                        "english_score": profile.english_score,
                        "preferred_country": profile.preferred_country,
                        "preferred_course": profile.preferred_course,
                        "preferred_intake": profile.preferred_intake,
                        "budget_range": profile.budget_range,
                        "work_experience": profile.work_experience,
                        "gap_years": profile.gap_years,
                        "neet_score": profile.neet_score,
                        "passport_available": profile.passport_available
                    }

                    # 2. Eligibility results
                    result = db.query(EligibilityResult).filter(EligibilityResult.request_id == profile.id).first()
                    if result:
                        context["eligibility_result"] = {
                            "overall_score": result.overall_score,
                            "admission_probability": result.admission_probability,
                            "scholarship_potential": result.scholarship_potential,
                            "visa_readiness": result.visa_readiness,
                            "strengths": result.strengths,
                            "weaknesses": result.weaknesses,
                            "suggested_improvements": result.suggested_improvements,
                            "recommended_countries": result.recommended_countries,
                            "recommended_universities": result.recommended_universities
                        }

            # 3. Latest SOP
            sop = db.query(SOPDocument).filter(SOPDocument.user_id == user_id).order_by(desc(SOPDocument.created_at)).first()
            if sop:
                context["latest_sop"] = {
                    "title": sop.title,
                    "course_name": sop.course_name,
                    "target_university": sop.target_university,
                    "created_at": sop.created_at.isoformat() if sop.created_at else None
                }

            # 4. Latest Visa audit check
            visa = db.query(VisaDocumentCheck).filter(VisaDocumentCheck.user_id == user_id).order_by(desc(VisaDocumentCheck.created_at)).first()
            if visa:
                context["latest_visa_check"] = {
                    "destination_country": visa.destination_country,
                    "readiness_score": visa.readiness_score,
                    "checklist_status": visa.checklist_status,
                    "general_advice": visa.general_advice,
                    "created_at": visa.created_at.isoformat() if visa.created_at else None
                }

            # 5. Saved scholarships list
            scholarships = db.query(SavedScholarship).filter(SavedScholarship.user_id == user_id).all()
            for s in scholarships:
                context["saved_scholarships"].append({
                    "name": s.name,
                    "provider": s.provider,
                    "funding_amount": s.funding_amount,
                    "deadline": s.deadline
                })

            # 6. Uploaded documents checklist
            docs = db.query(UploadedDocument).filter(UploadedDocument.user_id == user_id).all()
            for d in docs:
                context["uploaded_documents"].append({
                    "filename": d.filename,
                    "document_type": d.document_type,
                    "file_size_kb": round(d.file_size / 1024, 1) if d.file_size else 0
                })

            # Also load Master Document Vault uploads
            vault_docs = db.query(StudentDocument).filter(StudentDocument.user_id == user_id).all()
            for vd in vault_docs:
                context["uploaded_documents"].append({
                    "filename": vd.filename,
                    "document_type": vd.category,
                    "file_size_kb": round(vd.file_size / 1024, 1) if vd.file_size else 0
                })

            # 7. Paid premium services and order history
            orders = db.query(Order).filter(Order.user_id == user_id).all()
            for o in orders:
                context["payments_and_services"].append({
                    "service_slug": o.service.slug if o.service else "unknown",
                    "service_title": o.service.title if o.service else "Unknown Service",
                    "amount": o.amount,
                    "payment_status": o.payment_status
                })

            # 8. Determine Journey Stage dynamically
            if context["payments_and_services"]:
                paid_slugs = [p["service_slug"] for p in context["payments_and_services"] if p["payment_status"] == "paid"]
                if "premium-consulting" in paid_slugs or "visa-preparation" in paid_slugs:
                    context["journey_stage"] = "Visa Preparation & Interview"
                elif "sop-review" in paid_slugs:
                    context["journey_stage"] = "University Application (SOP Drafting)"
                else:
                    context["journey_stage"] = "Service Selection"
            elif context["latest_sop"] or context["uploaded_documents"]:
                context["journey_stage"] = "Document Collection"
            elif context["eligibility_result"]:
                context["journey_stage"] = "University Shortlisting"
            else:
                context["journey_stage"] = "Profile Scoping"

        except Exception as e:
            logger.error(f"Failed to compile context data: {str(e)}")

        return context

    @staticmethod
    def compile_context_prompt(context_data: Dict[str, Any]) -> str:
        """
        Formats the context dictionary into a clean markdown prompt injection.
        """
        lines = ["\n[STUDENT PLATFORM CONTEXT SNAPSHOT]"]
        
        # Journey Stage
        lines.append(f"Current Journey Stage: {context_data['journey_stage']}")
        
        # Profile Info
        p = context_data["profile"]
        if p:
            lines.append("\n**Student Profile:**")
            lines.append(f"- Name: {p['full_name']}")
            lines.append(f"- Email: {p['email']}")
            lines.append(f"- Resident of: {p['country_residence']} (Nationality: {p['nationality']})")
            lines.append(f"- Qualification: {p['qualification']} (GPA 10th: {p['gpa_10th']}%, 12th: {p['gpa_12th']}%)")
            lines.append(f"- Target Country: {p['preferred_country']} (Preferred Course: {p['preferred_course']})")
            lines.append(f"- Target Intake: {p['preferred_intake']} (Budget: {p['budget_range']})")
            lines.append(f"- English Exam: {p['english_exam']} (Score: {p['english_score']})")
            lines.append(f"- Work Exp: {p['work_experience']} yrs | Gaps: {p['gap_years']} yrs | Passport: {'Yes' if p['passport_available'] else 'No'}")
        else:
            lines.append("\n**Student Profile:** No profile registered yet.")

        # Eligibility Result
        er = context_data["eligibility_result"]
        if er:
            lines.append("\n**Eligibility Evaluation:**")
            lines.append(f"- Assessment Score: {er['overall_score']}/100")
            lines.append(f"- Adm Probability: {er['admission_probability']} | Scholarship Potential: {er['scholarship_potential']} | Visa Readiness: {er['visa_readiness']}")
            lines.append(f"- Strengths: {', '.join(er['strengths'][:3])}")
            lines.append(f"- Recommended Countries: {', '.join(er['recommended_countries'])}")
        
        # Latest SOP
        sop = context_data["latest_sop"]
        if sop:
            lines.append("\n**Latest Generated SOP:**")
            lines.append(f"- Title: {sop['title']}")
            lines.append(f"- Course target: {sop['course_name']} at {sop['target_university']}")
        
        # Latest Visa Check
        vc = context_data["latest_visa_check"]
        if vc:
            lines.append("\n**Latest Visa Document Scan Audit:**")
            lines.append(f"- Destination: {vc['destination_country']} (Readiness: {vc['readiness_score']}/100)")
            lines.append(f"- General Advice: {vc['general_advice']}")
        
        # Saved Scholarships
        ss = context_data["saved_scholarships"]
        if ss:
            lines.append("\n**Saved Scholarships:**")
            for item in ss[:3]:
                lines.append(f"- {item['name']} ({item['provider']}) - Deadline: {item['deadline']}")
        
        # Uploaded Reference Documents
        docs = context_data["uploaded_documents"]
        if docs:
            lines.append("\n**Vault Documents:**")
            for doc in docs[:4]:
                lines.append(f"- {doc['filename']} ({doc['document_type']}) - Size: {doc['file_size_kb']} KB")
        
        # Premium Subscriptions
        pmt = context_data["payments_and_services"]
        if pmt:
            lines.append("\n**Orders & Service Access:**")
            for item in pmt:
                lines.append(f"- {item['service_title']} (Status: {item['payment_status']})")
        
        lines.append("[END OF SNAPSHOT]\n")
        return "\n".join(lines)
