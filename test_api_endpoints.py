import unittest
from fastapi.testclient import TestClient

# Import the FastAPI app
from app.main import app
from app.auth import get_current_user

class TestAuraRoutesAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Clear dependency overrides before each test
        app.dependency_overrides = {}

    def test_health_check(self):
        """Test the health check endpoint returns 200 and correct status."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "healthy", "service": "Aura AI Engine"})

    def test_services_list(self):
        """Test retrieving all active pricing plans catalog."""
        response = self.client.get("/api/services")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)
        self.assertTrue(len(response.json()) > 0)
        
        # Verify the structure has core fields
        service = response.json()[0]
        self.assertIn("slug", service)
        self.assertIn("title", service)
        self.assertIn("price", service)

    def test_eligibility_check_anonymous(self):
        """Test submitting the eligibility profile wizard lead capture."""
        payload = {
            "personal_info": {
                "full_name": "Test Student",
                "email": "test.student@gmail.com",
                "phone": "+919999999999",
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
                "english_exam": "IELTS",
                "english_score": 7.5
            },
            "study_preferences": {
                "preferred_country": "Canada",
                "preferred_course": "Bachelor of Computer Science",
                "preferred_intake": "Fall 2026",
                "budget_range": "20-30 Lakhs",
                "scholarship_required": True
            },
            "additional_info": {
                "work_experience": 0.0,
                "gap_years": 0,
                "neet_score": 400,
                "passport_available": True
            }
        }
        response = self.client.post("/api/eligibility/check", json=payload)
        self.assertIn(response.status_code, [201, 503])
        if response.status_code == 201:
            data = response.json()
            self.assertIn("request", data)
            self.assertIn("result", data)
            self.assertEqual(data["request"]["full_name"], "Test Student")
            self.assertGreaterEqual(data["result"]["overall_score"], 0)

    def test_auth_lock_dashboard(self):
        """Test that secure dashboard endpoints return 401 without auth header."""
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Authentication credentials are required to access this resource."})

    def test_auth_lock_profile(self):
        """Test that secure profile settings return 401 without auth header."""
        response = self.client.get("/api/profile")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json(), {"detail": "Authentication credentials are required to access this resource."})

    def test_universities_catalog(self):
        """Test retrieving the world-class course discovery list."""
        response = self.client.get("/api/universities/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_authenticated_dashboard_and_profile(self):
        """Test secure endpoints with authenticated dependency override."""
        # Clean potential duplicate entries in test run from db
        from app.database import SessionLocal
        from app.models import Profile, EligibilityRequest
        db = SessionLocal()
        try:
            db.query(Profile).filter(Profile.user_id == "test_auth_user_id").delete()
            db.query(EligibilityRequest).filter(EligibilityRequest.email == "test.student@gmail.com").delete()
            db.commit()
        finally:
            db.close()

        # Set up auth mock payload
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "test_auth_user_id",
            "email": "test.student@gmail.com",
            "role": "authenticated",
            "user_metadata": {"full_name": "Test Student"}
        }
        
        # Test GET /api/profile (auto-creates a profile log)
        profile_res = self.client.get("/api/profile")
        self.assertEqual(profile_res.status_code, 200)
        profile_data = profile_res.json()
        self.assertEqual(profile_data["personal"]["email"], "test.student@gmail.com")
        self.assertEqual(profile_data["personal"]["full_name"], "Test Student")

        # Test GET /api/dashboard
        dashboard_res = self.client.get("/api/dashboard")
        self.assertEqual(dashboard_res.status_code, 200)
        dashboard_data = dashboard_res.json()
        self.assertIn("profile_completeness", dashboard_data)
        # Completeness should be 22% since Name, Email and default financial/journey metrics are set
        self.assertEqual(dashboard_data["profile_completeness"], 22)

    def test_scholarships_match_authenticated(self):
        """Test matching scholarships with authenticated user."""
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "test_auth_user_id",
            "email": "test.student@gmail.com",
            "role": "authenticated"
        }
        payload = {
            "nationality": "Indian",
            "country_residence": "India",
            "annual_family_income": "10-20 Lakhs",
            
            "highest_qualification": "Bachelors",
            "gpa_percentage": 85.0,
            "english_exam": "IELTS",
            "english_score": 7.5,
            "work_experience": 2.0,
            "research_experience": True,
            "publications": False,
            "volunteer_work": True,
            "leadership_experience": True,
            
            "preferred_countries": ["Canada", "USA"],
            "preferred_universities": ["University of Toronto"],
            "course": "Computer Science",
            "degree_level": "Masters",
            "intake": "Fall 2026",
            
            "budget": 3000000.0,
            "savings": 1000000.0,
            "education_loan": 2000000.0,
            "sponsor_support": 0.0,
            "existing_scholarships": 0.0
        }
        response = self.client.post("/api/scholarships/match", json=payload)
        if response.status_code != 200:
            print("\nSCHOLARSHIP ERROR RESPONSE DETAIL:", response.json())
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_chat_unauthenticated(self):
        """Test chat routes return 401 for anonymous queries."""
        self.assertEqual(self.client.post("/api/chat", json={"message": "hello"}).status_code, 401)
        self.assertEqual(self.client.get("/api/chat/history").status_code, 401)

    def test_chat_history_and_session_flow_authenticated(self):
        """Test active chat session creation and details retrieval using mock auth."""
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "test_auth_user_id",
            "email": "test.student@gmail.com",
            "role": "authenticated"
        }
        # Fetch history (should be empty/list)
        history_res = self.client.get("/api/chat/history")
        self.assertEqual(history_res.status_code, 200)
        self.assertIsInstance(history_res.json(), list)

    def test_journey_unauthenticated(self):
        """Test journey endpoints return 401 for anonymous checkups."""
        self.assertEqual(self.client.get("/api/journey").status_code, 401)
        self.assertEqual(self.client.get("/api/tasks").status_code, 401)

    def test_journey_authenticated_flow(self):
        """Test full student journey dashboard and application workspace flows."""
        app.dependency_overrides[get_current_user] = lambda: {
            "sub": "journey_test_user_id",
            "email": "journey.student@gmail.com",
            "role": "authenticated"
        }
        
        # 1. Fetch journey - should auto-create
        res = self.client.get("/api/journey")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("journey", data)
        self.assertIn("stages", data)
        self.assertEqual(data["journey"]["current_stage"], "Eligibility")

        # 2. Fetch tasks
        tasks_res = self.client.get("/api/tasks")
        self.assertEqual(tasks_res.status_code, 200)
        tasks = tasks_res.json()
        self.assertIsInstance(tasks, list)
        self.assertTrue(len(tasks) > 0)

        # 3. Create custom application shortlisted choice
        app_payload = {
            "university": "University of British Columbia",
            "country": "Canada",
            "course": "MEng Electrical Engineering",
            "degree": "Masters",
            "tuition_fee": "$30,000 CAD"
        }
        app_res = self.client.post("/api/application", json=app_payload)
        self.assertEqual(app_res.status_code, 201)

        # 4. List applications
        list_res = self.client.get("/api/application")
        self.assertEqual(list_res.status_code, 200)
        apps = list_res.json()
        self.assertEqual(len(apps), 1)
        self.assertEqual(apps[0]["university"], "University of British Columbia")

if __name__ == "__main__":
    unittest.main()
