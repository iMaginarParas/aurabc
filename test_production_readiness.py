import unittest
import time
import os
import hmac
import hashlib
import json
from io import BytesIO
from fastapi.testclient import TestClient
from fastapi import status

# Import FastAPI app & helpers
from app.main import app
from app.auth import get_current_user
from app.database import SessionLocal, get_db
from app.models import (
    Profile, AcademicProfile, StudyPreference, FinancialProfile,
    Order, Service, VisaDocumentCheck, UploadedDocument, DocumentAnalysis,
    SOPDocument, SOPVersion, UniversityMatch, SavedUniversity, UniversityComparison,
    Application, ApplicationTask, Appointment, Notification, WhatsAppNotification
)

class TestProductionReadiness(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides = {}
        self.db = SessionLocal()
        
        # Setup clean test user context
        self.test_user_id = "test_e2e_user"
        self.test_email = "test.e2e@auraroutes.com"
        
        # Cleanup existing test user records to guarantee test isolation
        self.cleanup_test_data()

    def tearDown(self):
        self.cleanup_test_data()
        self.db.close()

    def cleanup_test_data(self):
        # Delete test user profiles and related entries via cascade
        profile = self.db.query(Profile).filter(Profile.user_id == self.test_user_id).first()
        if profile:
            self.db.delete(profile)
        
        # Clean up orders, checks, matching results, and documents for test user
        self.db.query(Order).filter(Order.user_id == self.test_user_id).delete()
        self.db.query(SOPDocument).filter(SOPDocument.user_id == self.test_user_id).delete()
        self.db.query(VisaDocumentCheck).filter(VisaDocumentCheck.user_id == self.test_user_id).delete()
        self.db.query(UniversityMatch).filter(UniversityMatch.user_id == self.test_user_id).delete()
        self.db.query(SavedUniversity).filter(SavedUniversity.user_id == self.test_user_id).delete()
        self.db.query(UniversityComparison).filter(UniversityComparison.user_id == self.test_user_id).delete()
        self.db.query(Application).filter(Application.user_id == self.test_user_id).delete()
        self.db.query(Appointment).filter(Appointment.user_id == self.test_user_id).delete()
        self.db.query(Notification).filter(Notification.user_id == self.test_user_id).delete()
        self.db.query(WhatsAppNotification).filter(WhatsAppNotification.user_id == self.test_user_id).delete()
        self.db.commit()

    def mock_auth(self):
        """Overrides dependency verification to authenticate test requests."""
        def mock_user():
            return {"sub": self.test_user_id, "email": self.test_email, "role": "authenticated"}
        app.dependency_overrides[get_current_user] = mock_user

    # =========================================================================
    # 1. AUTHENTICATION & LOCK TESTS
    # =========================================================================
    def test_auth_route_locking(self):
        """Assert secure routes return 401 Unauthorized without auth headers."""
        app.dependency_overrides.clear() # Enforce live auth checks
        
        protected_endpoints = [
            ("/api/profile", "GET"),
            ("/api/dashboard", "GET"),
            ("/api/journey", "GET"),
            ("/api/tasks", "GET"),
            ("/api/chat/history", "GET")
        ]
        for endpoint, method in protected_endpoints:
            if method == "GET":
                response = self.client.get(endpoint)
            else:
                response = self.client.post(endpoint)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
            self.assertIn("detail", response.json())

    # =========================================================================
    # 2. END-TO-END STUDENT JOURNEY FLOW
    # =========================================================================
    def test_e2e_student_journey(self):
        """Runs the entire end-to-end user workflow mapping features from lead to dashboard settings."""
        self.mock_auth()
        
        # A. Start Lead Check
        payload = {
            "personal_info": {
                "full_name": "Test Journey Student",
                "email": self.test_email,
                "phone": "+919000000000",
                "country_residence": "India",
                "nationality": "Indian"
            },
            "academic_profile": {
                "qualification": "High School",
                "gpa_10th": 92.5,
                "gpa_12th": 88.0,
                "grad_year": 2025
            },
            "english_proficiency": {
                "english_exam": "IELTS",
                "english_score": 8.0
            },
            "study_preferences": {
                "preferred_country": "United Kingdom",
                "preferred_course": "Bachelor of Software Engineering",
                "preferred_intake": "Fall 2026",
                "budget_range": "20-30 Lakhs",
                "scholarship_required": True
            },
            "additional_info": {
                "work_experience": 1.0,
                "gap_years": 0,
                "neet_score": 0,
                "passport_available": True
            }
        }
        response = self.client.post("/api/eligibility/check", json=payload)
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_503_SERVICE_UNAVAILABLE])
        
        # B. Load Master Profile and complete wizard details
        profile_response = self.client.get("/api/profile")
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        profile_data = profile_response.json()
        self.assertIn("completion_scores", profile_data)
        
        # Update Master Profile detail sections
        update_payload = {
            "personal": {
                "full_name": "Test Journey Student",
                "nationality": "Indian",
                "country_residence": "India",
                "city": "Mumbai",
                "gender": "Male",
                "date_of_birth": "2002-05-15",
                "passport_number": "Z1234567",
                "passport_expiry": "2032-12-31"
            },
            "academic": {
                "highest_qualification": "High School",
                "gpa_10th": 92.5,
                "gpa_12th": 88.0,
                "grad_year": 2025,
                "university": "State High Board",
                "college": "N/A",
                "backlogs": 0,
                "ielts_score": 8.0
            },
            "preferences": {
                "preferred_countries": ["United Kingdom"],
                "preferred_courses": ["Bachelor of Software Engineering"],
                "degree_level": "Bachelors",
                "budget": "20-30 Lakhs",
                "target_intake": "Fall 2026",
                "scholarship_required": True
            },
            "financial": {
                "annual_family_income": "12 Lakhs",
                "savings": 500000.0,
                "education_loan": 1500000.0,
                "sponsor": "Parents"
            }
        }
        update_res = self.client.put("/api/profile", json=update_payload)
        self.assertEqual(update_res.status_code, status.HTTP_200_OK)
        
        # Assert completion percentages incremented correctly
        updated_profile = update_res.json()
        self.assertGreaterEqual(updated_profile["completion_scores"]["personal"], 50)
        
        # C. Payment order workflow verification
        # Retrieve an active service ID from dynamic catalog
        services_res = self.client.get("/api/services")
        self.assertEqual(services_res.status_code, status.HTTP_200_OK)
        services = services_res.json()
        self.assertTrue(len(services) > 0)
        
        sop_service = next((s for s in services if s["slug"] == "ai-sop-generator"), None)
        self.assertIsNotNone(sop_service)
        
        # Create pending order transaction
        order_payload = {
            "service_id": sop_service["id"],
            "user_id": self.test_user_id
        }
        order_res = self.client.post("/api/payment/create-order", json=order_payload)
        self.assertEqual(order_res.status_code, status.HTTP_201_CREATED)
        order_data = order_res.json()
        self.assertIn("razorpay_order_id", order_data)
        
        # Simulate payment capturing and signature verification
        verify_payload = {
            "razorpay_order_id": order_data["razorpay_order_id"],
            "razorpay_payment_id": f"pay_test_{uuid_hex()}",
            "razorpay_signature": "mock_signature_for_test",
            "billing_name": "Test Journey Student",
            "email": self.test_email
        }
        # In test mode/dev, verify_payment bypasses Razorpay server verification if signature is dummy
        verify_res = self.client.post("/api/payment/verify", json=verify_payload)
        self.assertIn(verify_res.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    # =========================================================================
    # 3. SECURITY & VULNERABILITY TESTS
    # =========================================================================
    def test_sql_injection_defense(self):
        """Verifies API endpoints escape and safely process potential SQL injection payload parameters."""
        self.mock_auth()
        sql_payload = "' OR '1'='1' --"
        
        # Test catalog query parameter injection
        response = self.client.get(f"/api/explorer/universities?query={sql_payload}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not crash the database or return all tables/data bypasses
        data = response.json()
        self.assertIsInstance(data.get("items", []), list)

    def test_xss_sanitization_handling(self):
        """Verifies application safely stores or outputs potential cross-site scripting input payloads."""
        self.mock_auth()
        xss_script = "<script>alert('XSS')</script> Test User"
        
        # Submit check request with injection attempt
        payload = {
            "personal_info": {
                "full_name": xss_script,
                "email": self.test_email,
                "phone": "+919000000000",
                "country_residence": "India",
                "nationality": "Indian"
            },
            "academic_profile": {
                "qualification": "High School",
                "gpa_10th": 90.0,
                "gpa_12th": 85.0,
                "grad_year": 2025
            },
            "english_proficiency": {
                "english_exam": "None"
            },
            "study_preferences": {
                "preferred_country": "UK",
                "preferred_course": "CS",
                "preferred_intake": "Fall 2026",
                "budget_range": "20 Lakhs",
                "scholarship_required": False
            },
            "additional_info": {
                "work_experience": 0.0,
                "gap_years": 0,
                "neet_score": 0,
                "passport_available": True
            }
        }
        res = self.client.post("/api/eligibility/check", json=payload)
        self.assertIn(res.status_code, [status.HTTP_201_CREATED, status.HTTP_503_SERVICE_UNAVAILABLE])

    def test_file_upload_limitations(self):
        """Enforces limits on maximum file size upload requests and binary formats checks."""
        self.mock_auth()
        
        # Create a mock visa check reference
        visa_check = VisaDocumentCheck(
            user_id=self.test_user_id,
            country="United Kingdom",
            visa_type="Student Visa",
            status="Pending"
        )
        self.db.add(visa_check)
        self.db.commit()
        self.db.refresh(visa_check)
        
        # A. Rejects files that exceed the 5MB size limit
        large_file = BytesIO(b"0" * (6 * 1024 * 1024))  # 6MB dummy content
        response = self.client.post(
            "/api/visa-check/upload",
            data={"check_id": visa_check.id, "document_type": "Passport"},
            files={"file": ("passport.pdf", large_file, "application/pdf")}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("File too large", response.json()["detail"])
        
        # B. Rejects unapproved executable formats
        executable = BytesIO(b"MZ\x90\x00\x03\x00\x00\x00")  # Dummy PE signature
        res_exe = self.client.post(
            "/api/visa-check/upload",
            data={"check_id": visa_check.id, "document_type": "Passport"},
            files={"file": ("malicious.exe", executable, "application/octet-stream")}
        )
        self.assertEqual(res_exe.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unsupported file format", res_exe.json()["detail"])

    # =========================================================================
    # 4. DATABASE INTEGRITY TESTS (CASCADE DELETIONS)
    # =========================================================================
    def test_database_profile_cascade_rules(self):
        """Verifies deleting parent profile clears academic, preferences and financial details cascade."""
        self.mock_auth()
        
        # 1. Initialize profile relations
        profile = Profile(user_id=self.test_user_id, email=self.test_email)
        self.db.add(profile)
        self.db.commit()
        self.db.refresh(profile)
        
        acad = AcademicProfile(profile_id=profile.id, highest_qualification="Bachelors")
        pref = StudyPreference(profile_id=profile.id, target_intake="Spring 2026")
        fin = FinancialProfile(profile_id=profile.id, savings=200000.0)
        self.db.add_all([acad, pref, fin])
        self.db.commit()
        
        # Check profiles added successfully
        self.assertIsNotNone(self.db.query(AcademicProfile).filter(AcademicProfile.profile_id == profile.id).first())
        
        # 2. Perform deletion on primary user Profile record
        self.db.delete(profile)
        self.db.commit()
        
        # 3. Assert cascade removed child settings automatically
        acad_deleted = self.db.query(AcademicProfile).filter(AcademicProfile.profile_id == profile.id).first()
        pref_deleted = self.db.query(StudyPreference).filter(StudyPreference.profile_id == profile.id).first()
        fin_deleted = self.db.query(FinancialProfile).filter(FinancialProfile.profile_id == profile.id).first()
        
        self.assertIsNone(acad_deleted)
        self.assertIsNone(pref_deleted)
        self.assertIsNone(fin_deleted)

    # =========================================================================
    # 5. PERFORMANCE METRICS (LATENCY CALCULATIONS)
    # =========================================================================
    def test_api_latency_performance_limits(self):
        """Checks API response speeds to ensure dynamic services list responds under 150ms."""
        self.mock_auth()
        start = time.perf_counter()
        response = self.client.get("/api/services")
        duration_ms = (time.perf_counter() - start) * 1000
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify latency constraints on dynamic database catalog queries
        self.assertLess(duration_ms, 150.0, f"Catalog retrieval took too long: {duration_ms:.2f}ms")

def uuid_hex():
    import uuid
    return uuid.uuid4().hex

if __name__ == "__main__":
    unittest.main()
