import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AIReview, WorkItem, WorkItemEvidence
from app.routers.intake import TeamsIntakePayload, intake_teams


class TeamsIntakeTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def payload(self, **overrides):
        data = {
            "command": "/task Restore DNS",
            "original_message_text": "DNS is unavailable",
            "reply_text": "/task Restore DNS",
            "sender_name": "Requester",
            "assignee_name": "Engineer",
            "message_id": "message-1",
            "conversation_id": "conversation-1",
        }
        data.update(overrides)
        return TeamsIntakePayload(**data)

    def test_reply_in_same_conversation_queues_review_without_changing_task(self):
        first = intake_teams(self.payload(), self.db)
        second = intake_teams(self.payload(
            command="Confirmed fixed",
            reply_text="Confirmed fixed",
            message_id="message-2",
        ), self.db)

        self.assertFalse(first["review_queued"])
        self.assertTrue(second["evidence_attached"])
        self.assertTrue(second["review_queued"])
        self.assertEqual(self.db.query(WorkItem).count(), 1)
        self.assertEqual(self.db.query(WorkItem).one().status, "Open")
        self.assertEqual(self.db.query(WorkItemEvidence).count(), 2)
        self.assertEqual(self.db.query(AIReview).count(), 1)

    def test_duplicate_message_is_ignored(self):
        intake_teams(self.payload(), self.db)
        duplicate = intake_teams(self.payload(), self.db)

        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(self.db.query(WorkItemEvidence).count(), 1)
        self.assertEqual(self.db.query(AIReview).count(), 0)


if __name__ == "__main__":
    unittest.main()
