import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.courses.activites import create_activities_router
from backend.database import Base, User


class ActivityAudienceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        with self.session_factory() as db:
            db.add_all(
                [
                    User(
                        id=1,
                        identity="admin@example.com",
                        name="Admin",
                        password_hash="unused",
                        role="admin",
                        active=True,
                    ),
                    User(
                        id=2,
                        identity="employee1@example.com",
                        name="Employee One",
                        password_hash="unused",
                        role="user",
                        active=True,
                    ),
                    User(
                        id=3,
                        identity="employee2@example.com",
                        name="Employee Two",
                        password_hash="unused",
                        role="user",
                        active=True,
                    ),
                ]
            )
            db.commit()

        self.current_employee_id = 2
        app = FastAPI()

        def get_db():
            with self.session_factory() as db:
                yield db

        def require_user():
            return User(id=self.current_employee_id, role="user")

        def require_admin():
            return User(id=1, role="admin")

        def require_csrf():
            return None

        app.include_router(
            create_activities_router(
                get_db=get_db,
                require_user=require_user,
                require_admin=require_admin,
                require_csrf=require_csrf,
            )
        )
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def test_selected_and_public_activity_visibility(self):
        specific = self.client.post(
            "/api/v1/admin/activities",
            json={
                "title": "Selected activity",
                "kind": "activity",
                "description": "For one employee",
                "start_date": "2026-12-01",
                "end_date": "2026-12-01",
                "location": "Office",
                "employee_ids": [2],
            },
        )
        self.assertEqual(specific.status_code, 201)
        self.assertEqual(specific.json()["employee_ids"], [2])
        self.assertFalse(specific.json()["all_employees"])

        public = self.client.post(
            "/api/v1/admin/activities",
            json={
                "title": "Public program",
                "kind": "program",
                "description": "For everyone",
                "start_date": "2026-12-02",
                "end_date": "2026-12-03",
                "location": "Training room",
                "employee_ids": None,
            },
        )
        self.assertEqual(public.status_code, 201)
        self.assertTrue(public.json()["all_employees"])

        employee_one_activities = self.client.get("/api/v1/activities").json()
        self.assertEqual(
            {activity["title"] for activity in employee_one_activities},
            {"Selected activity", "Public program"},
        )

        self.current_employee_id = 3
        employee_two_activities = self.client.get("/api/v1/activities").json()
        self.assertEqual(
            {activity["title"] for activity in employee_two_activities},
            {"Public program"},
        )

        admin_activities = self.client.get("/api/v1/admin/activities").json()
        selected_activity = next(
            activity
            for activity in admin_activities
            if activity["title"] == "Selected activity"
        )
        self.assertEqual(selected_activity["employee_names"], ["Employee One"])

    def test_invalid_employee_selection_is_rejected(self):
        response = self.client.post(
            "/api/v1/admin/activities",
            json={
                "title": "Invalid audience",
                "kind": "activity",
                "description": "Not assigned to a real employee",
                "start_date": "2026-12-01",
                "end_date": "2026-12-01",
                "location": "Office",
                "employee_ids": [999],
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/v1/admin/activities").json(), [])


if __name__ == "__main__":
    unittest.main()
