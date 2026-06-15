import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User
from app.services.performance import Period, compute_performance, get_available_periods


class PerformanceReportingTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_members_without_evidence_do_not_rank_ahead(self):
        self.db.add_all([
            User(display_name="Active", email="active@example.com"),
            User(display_name="No Evidence", email="none@example.com"),
        ])
        self.db.commit()
        from app.models import WorkItem
        active = self.db.query(User).filter(User.email == "active@example.com").one()
        self.db.add(WorkItem(
            title="Delivered work",
            assignee_id=active.id,
            status="Done",
            created_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
            completed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        ))
        self.db.commit()

        results = compute_performance(self.db, Period("quarter", 2026, 2))

        self.assertEqual(results[0]["user"].display_name, "Active")
        self.assertEqual(results[-1]["values"]["evidence_count"], 0)

    def test_available_periods_excludes_future_quarters(self):
        from app.models import WorkItem
        self.db.add(WorkItem(title="Work", created_at=datetime(2026, 1, 2, tzinfo=timezone.utc)))
        self.db.commit()

        periods = get_available_periods(self.db)

        self.assertNotIn("2026-Q3", [period.key() for period in periods])
        self.assertNotIn("2026-Q4", [period.key() for period in periods])


if __name__ == "__main__":
    unittest.main()
