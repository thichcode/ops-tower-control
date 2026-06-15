import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AIReview, Service, User, WorkItem, WorkItemEvidence
from app.services.ai_review import (
    apply_review,
    build_evidence,
    create_or_refresh_review,
    reject_review,
    validate_suggestion,
)


class AIReviewTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.user = User(display_name="Engineer A", email="a@example.com")
        self.service = Service(name="Cloudflare", status="active")
        self.db.add_all([self.user, self.service])
        self.db.commit()
        self.item = WorkItem(
            title="Restore DNS",
            description="Requester confirms the issue still exists.",
            status="Open",
            service_id=self.service.id,
            assignee_id=self.user.id,
        )
        self.db.add(self.item)
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_rule_review_does_not_change_work_item(self):
        review = create_or_refresh_review(self.db, self.item, use_ai=False)

        self.assertEqual(review.provider, "rules")
        self.assertEqual(review.state, "pending")
        self.assertEqual(self.item.status, "Open")

    def test_review_evidence_contains_conversation_messages(self):
        self.db.add(WorkItemEvidence(
            work_item_id=self.item.id,
            source="Teams",
            source_message_id="Teams:reply-1",
            thread_id="thread-1",
            sender_name="Requester",
            body_excerpt="Confirmed fixed.",
        ))
        self.db.commit()

        review = create_or_refresh_review(self.db, self.item, use_ai=False)

        self.assertEqual(review.evidence["conversation_evidence"][0]["body"], "Confirmed fixed.")

    def test_invalid_ai_values_are_removed(self):
        result = validate_suggestion(
            {
                "status": "Closed",
                "service": "Unknown",
                "assignee": "Unknown",
                "confidence": 4,
                "rationale": "guess",
                "signals": [],
            },
            {"allowed_services": ["Cloudflare"], "allowed_assignees": ["Engineer A"]},
        )

        self.assertEqual(result["status"], "Open")
        self.assertIsNone(result["service"])
        self.assertIsNone(result["assignee"])
        self.assertEqual(result["confidence"], 1.0)

    def test_approve_is_the_only_step_that_applies_status(self):
        review = create_or_refresh_review(self.db, self.item, use_ai=False)

        apply_review(self.db, review, "Done", self.service.id, self.user.id)

        self.assertEqual(self.item.status, "Done")
        self.assertIsNotNone(self.item.completed_at)
        self.assertEqual(review.state, "approved")


    def test_build_evidence_redacts_requester_name(self):
        self.item.requester_name = "Alice Smith"
        self.db.commit()

        evidence = build_evidence(self.db, self.item)

        self.assertEqual(evidence["work_item"]["requester"], "[REDACTED]")

    def test_build_evidence_redacts_sender_name(self):
        self.db.add(WorkItemEvidence(
            work_item_id=self.item.id,
            source="Teams",
            sender_name="Bob Jones",
            body_excerpt="Please help with this issue.",
        ))
        self.db.commit()

        evidence = build_evidence(self.db, self.item)

        self.assertEqual(evidence["conversation_evidence"][0]["sender"], "[REDACTED]")

    def test_build_evidence_redacts_secrets_from_body_excerpt(self):
        self.db.add(WorkItemEvidence(
            work_item_id=self.item.id,
            source="Teams",
            sender_name="Bob Jones",
            body_excerpt="My api_key=abc123 is secret, but context remains",
        ))
        self.db.commit()

        evidence = build_evidence(self.db, self.item)

        self.assertNotIn("abc123", evidence["conversation_evidence"][0]["body"])
        self.assertNotIn("api_key", evidence["conversation_evidence"][0]["body"])
        self.assertIn("[REDACTED]", evidence["conversation_evidence"][0]["body"])
        self.assertIn("context remains", evidence["conversation_evidence"][0]["body"])

    def test_apply_review_records_reviewer_id(self):
        reviewer = User(display_name="Reviewer", email="reviewer@example.com")
        self.db.add(reviewer)
        self.db.commit()
        review = create_or_refresh_review(self.db, self.item, use_ai=False)

        apply_review(self.db, review, "Done", self.service.id, self.user.id, reviewer_id=reviewer.id)

        self.assertEqual(review.reviewer_id, reviewer.id)
        self.assertEqual(review.state, "approved")

    def test_reject_review_records_reviewer_id(self):
        reviewer = User(display_name="Reviewer", email="reviewer@example.com")
        self.db.add(reviewer)
        self.db.commit()
        review = create_or_refresh_review(self.db, self.item, use_ai=False)

        reject_review(self.db, review, reviewer_id=reviewer.id)

        self.assertEqual(review.reviewer_id, reviewer.id)
        self.assertEqual(review.state, "rejected")


if __name__ == "__main__":
    unittest.main()
