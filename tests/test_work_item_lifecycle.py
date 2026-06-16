import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import WorkItem
from app.routers.work_items import block_work_item, done_work_item


class WorkItemLifecycleTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_done_clears_blocked_reason(self):
        item = WorkItem(title="Blocked item", status="Blocked", blocked_reason="Waiting for vendor")
        self.db.add(item)
        self.db.commit()

        done_work_item(item.id, self.db)

        self.db.refresh(item)
        self.assertEqual(item.status, "Done")
        self.assertIsNone(item.blocked_reason)
        self.assertIsNotNone(item.completed_at)

    def test_blocked_clears_completed_at(self):
        item = WorkItem(title="Done item", status="Done", completed_at=datetime.now(timezone.utc))
        self.db.add(item)
        self.db.commit()

        block_work_item(item.id, "Regression found", self.db)

        self.db.refresh(item)
        self.assertEqual(item.status, "Blocked")
        self.assertEqual(item.blocked_reason, "Regression found")
        self.assertIsNone(item.completed_at)


if __name__ == "__main__":
    unittest.main()
