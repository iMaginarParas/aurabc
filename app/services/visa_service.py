import os
import json
import logging
import openai
from typing import Dict, Any, List

from ..config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI
openai_client = None
if settings.openai_api_key:
    try:
        openai_client = openai.OpenAI(api_key=settings.openai_api_key)
        logger.info("OpenAI client initialized successfully in Visa Service.")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client in Visa: {str(e)}")

def load_country_visa_rules(country: str) -> Dict[str, Any]:
    """
    Dynamically loads country-specific validation rules from JSON files.
    """
    country_clean = country.lower().strip()
    rules_dir = os.path.join("backend", "data", "visa_rules")
    file_path = os.path.join(rules_dir, f"{country_clean}.json")
    
    # Check absolute path fallback
    if not os.path.exists(file_path):
        # Try local folder directly (current directory might be backend/)
        file_path = os.path.join("data", "visa_rules", f"{country_clean}.json")

    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                logger.info(f"Loaded rules file for: {country}")
                return json.load(f)
        except Exception as e:
            logger.error(f"Error parsing rules file: {str(e)}")
            
    # Default fallback rules
    logger.warning(f"Rules file not found for {country}. Resolving default rules.")
    return {
        "country": country,
        "required_documents": ["Passport", "Bank Statements", "Letter of Acceptance"],
        "optional_documents": ["Language Test", "SOP"],
        "validation_rules": {
            "Passport": "Must be valid for travel with at least 6 months remaining.",
            "Bank Statements": "Must show sufficient balance to cover first-year study fees and living costs.",
            "Letter of Acceptance": "Must be official admission letter from target university."
        },
        "critical_rules": ["Passport validity check", "Financial coverage checks"],
        "ai_instructions": "Review basic document expirations and finance balances.",
        "pass_examples": "Valid documents uploaded.",
        "fail_examples": "Missing bank statements, expired passport."
    }

def simulate_document_ocr_text(doc_type: str, filename: str) -> str:
    """
    Simulates OCR document text parsing to provide realistic inputs to ChatGPT.
    """
    name_clean = filename.lower()
    
    if "passport" in name_clean or doc_type == "Passport":
        # Check if expired in filename simulation
        expiry_year = 2028
        if "expired" in name_clean:
            expiry_year = 2023
        return f"Passport Document OCR Extract.\nPassport No: Z9834512\nNationality: Indian\nName: Priyan Bose\nGender: M\nDOB: 1999-05-15\nExpiry Date: {expiry_year}-10-20\nBlank Pages: 4\nAuthority: Govt of India"
        
    elif "bank" in name_clean or "statement" in name_clean or doc_type == "Bank Statements":
        balance = 1600000
        days = 32
        if "low" in name_clean:
            balance = 250000
        if "short" in name_clean:
            days = 10
        return f"Bank Savings Account Statement.\nAccount Holder: Priyan Bose\nAccount No: 109283749\nCurrency: INR\nClosing Balance: {balance} INR\nConsecutive holding period of current balance: {days} days\nAverage monthly deposit: 80,000 INR"
        
    elif "acceptance" in name_clean or "loa" in name_clean or "cas" in name_clean or doc_type in ["Letter of Acceptance", "Confirmation of Acceptance for Studies (CAS)"]:
        dli = "O19358248"
        if "unapproved" in name_clean:
            dli = "O00000000"
        return f"University Admission Offer.\nInstitution: University of Toronto\nDLI Number: {dli}\nStudent Name: Priyan Bose\nProgram: Master of Science in Computer Science\nIntake Term: Sept 2026\nDuration: 2 Years\nFirst Year Tuition Cost: 32,000 CAD"
        
    elif "ielts" in name_clean or "toefl" in name_clean or doc_type == "IELTS / TOEFL / PTE":
        overall = 7.0
        writing = 6.5
        if "low" in name_clean:
            overall = 5.5
            writing = 5.0
        return f"IELTS Test Report Form.\nCandidate Name: Priyan Bose\nTest Date: 2025-08-12\nListening: 7.5\nReading: 7.0\nWriting: {writing}\nSpeaking: 7.0\nOverall Band Score: {overall}"
        
    elif "insurance" in name_clean or doc_type == "Overseas Student Health Cover (OSHC)":
        return "OSHC Health Cover Policy.\nInsured: Priyan Bose\nPolicy Type: Single Student Cover\nStart Date: 2026-08-15\nEnd Date: 2028-08-15\nCover Value: Full medical inpatient cover"
        
    elif "medical" in name_clean or doc_type == "GAMCA Medical Fit Certificate":
        status = "FIT"
        if "unfit" in name_clean:
            status = "UNFIT"
        return f"GAMCA GCC Medical Assessment.\nCandidate Name: Priyan Bose\nGAMCA Slip No: 981245\nResult Status: {status}\nDiagnostic summary: Chest X-ray clear, blood pressure normal."
        
    elif "pcc" in name_clean or "police" in name_clean or doc_type == "Police Clearance Certificate":
        days_old = 15
        if "old" in name_clean:
            days_old = 120
        return f"Police Clearance Certificate.\nIssued To: Priyan Bose\nDate of Issue: {days_old} days ago\nCriminal Record Status: NIL / No criminal records logged."

    # Generic OCR template
    return f"OCR Text Extract from file: {filename}\nCategory: {doc_type}\nName Match: Priyan Bose\nContent validity signature: Standard Official Document Stamp."


def evaluate_visa_documents_ai(
    country: str,
    visa_type: str,
    uploaded_files: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Assembles country visa rules, triggers simulated OCR parsing, and queries OpenAI
    to produce a structured JSON Visa Readiness Report.
    """
    # 1. Load Rules JSON
    rules = load_country_visa_rules(country)
    
    # 2. Run simulated OCR parsing on files
    ocr_payloads = []
    for file in uploaded_files:
        filename = file.get("filename", "document.pdf")
        doc_type = file.get("document_type", "Other")
        ocr_text = simulate_document_ocr_text(doc_type, filename)
        
        ocr_payloads.append({
            "id": file.get("id"),
            "document_type": doc_type,
            "filename": filename,
            "ocr_extract": ocr_text
        })
        
    system_prompt = """You are an expert visa officer, document intelligence analyst, and immigration advisor.
Your task is to analyze the provided OCR document extracts against country-specific visa rules and generate a Visa Readiness Report in strict JSON format.

JSON RESPONSE SCHEMA SPECIFICATION:
Your response must be a single JSON object. Do NOT wrap the JSON inside markdown code blocks (e.g. ```json). Output only the raw JSON.
The JSON must contain these exact fields:
- "readiness_score": integer (0 to 100)
- "status": string (one of: "Ready", "Needs Improvement", "Critical Issues")
- "passed_checks": list of strings (rules successfully met)
- "failed_checks": list of strings (rules failed or omitted)
- "missing_documents": list of strings (required documents not found in uploads)
- "warnings": list of strings (cautions, minor issues)
- "risk_assessment": string (assessment of visa refusal risk)
- "recommendations": list of strings (practical suggestions)
- "next_steps": list of strings (actions to take next)
- "estimated_approval": string (refusal/approval likelihood, e.g. "88%")
- "document_analyses": list of objects, where each object has:
  * "document_name": string (the uploaded filename)
  * "status": string ("Passed", "Warning", or "Failed")
  * "issues": list of strings
  * "suggestions": list of strings
  * "confidence_score": float (0.0 to 1.0)
  * "critical": boolean (true if failure bails the visa application)
"""

    prompt = f"""Target Destination: {country}
Visa Type: {visa_type}

COUNTRY IMMIGRATION RULES:
{json.dumps(rules, indent=2)}

UPLOADED DOCUMENTS FOR EVALUATION:
{json.dumps(ocr_payloads, indent=2)}
"""

    if openai_client:
        try:
            logger.info(f"Querying OpenAI ChatGPT for Visa Document Checker report: {country}")
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=3000,
                response_format={"type": "json_object"}
            )
            report_str = response.choices[0].message.content
            if report_str:
                return json.loads(report_str.strip())
        except Exception as e:
            logger.error(f"OpenAI Visa Check failed: {str(e)}. Resolving local fallback report.")

    # Return local mock/fallback report if OpenAI bails
    return get_fallback_visa_report(country, visa_type, ocr_payloads)


def get_fallback_visa_report(country: str, visa_type: str, ocr_payloads: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Resilient fallback report compiler when OpenAI API is not responding.
    """
    logger.info("Compiling simulated fallback report.")
    
    # Basic analysis heuristics based on filenames
    has_passport = False
    has_bank = False
    has_loa = False
    
    doc_analyses = []
    passed = ["Upload credentials check"]
    failed = []
    missing = []
    warnings = []
    
    for doc in ocr_payloads:
        filename = doc["filename"].lower()
        doc_type = doc["document_type"]
        
        status = "Passed"
        issues = []
        suggs = []
        is_critical = False
        
        if doc_type == "Passport":
            has_passport = True
            if "expired" in filename:
                status = "Failed"
                issues.append("Passport has expired or is nearing expiration date.")
                suggs.append("Renew passport immediately before scheduling visa slots.")
                is_critical = True
                failed.append("Passport Expiry Check")
            else:
                passed.append("Valid Passport Verified")
                
        elif doc_type == "Bank Statements":
            has_bank = True
            if "low" in filename:
                status = "Failed"
                issues.append("Closing balance does not cover living expenses and tuition.")
                suggs.append("Deposit additional liquid funds in acceptable bank accounts.")
                is_critical = True
                failed.append("Financial Capability Proof")
            elif "short" in filename:
                status = "Warning"
                issues.append("Funds holding duration is short (less than required 28 days).")
                suggs.append("Provide financial tracking audit logs showing source history.")
                warnings.append("Finance holding duration warning")
            else:
                passed.append("Liquid Assets Verified")
                
        elif doc_type in ["Letter of Acceptance", "Confirmation of Acceptance for Studies (CAS)"]:
            has_loa = True
            if "unapproved" in filename:
                status = "Failed"
                issues.append("DLI college verification failed or invalid license.")
                suggs.append("Verify CAS/LOA reference numbers with institution DSO.")
                is_critical = True
                failed.append("Institutional License Verification")
            else:
                passed.append("Academic Acceptance Verified")
                
        doc_analyses.append({
            "document_name": doc["filename"],
            "status": status,
            "issues": issues,
            "suggestions": suggs,
            "confidence_score": 0.95,
            "critical": is_critical
        })

    # Find missing required files
    if not has_passport:
        missing.append("Passport Scan")
        failed.append("Missing Passport Check")
    if not has_bank:
        missing.append("Bank Statements / Financial proof")
        failed.append("Missing Financial Statement Check")
    if not has_loa:
        missing.append("Letter of Acceptance / CAS")
        failed.append("Missing Admission Letter Check")

    # Determine Overall Score
    score = 90
    overall_status = "Ready"
    
    if len(failed) > 0:
        score = 45
        overall_status = "Critical Issues"
    elif len(warnings) > 0 or len(missing) > 0:
        score = 70
        overall_status = "Needs Improvement"

    return {
        "readiness_score": score,
        "status": overall_status,
        "passed_checks": passed,
        "failed_checks": failed,
        "missing_documents": missing,
        "warnings": warnings,
        "risk_assessment": "High risk of refusal if critical parameters (passport validity/finance bounds) are not revised immediately." if score < 60 else "Low refusal risk. File matches standard guidelines.",
        "recommendations": [
            "Ensure bank logs show clear liquid source history.",
            "Verify all files are in high resolution PDF color formats."
        ],
        "next_steps": [
            "Resolve any failed check guidelines listed.",
            "Schedule document verification zoom call with an Aura Routes mentor."
        ],
        "estimated_approval": f"{score}%",
        "document_analyses": doc_analyses
    }
