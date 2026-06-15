import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AIReview, Service, User, WorkItem, WorkItemEvidence


class MemberIntakeTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)
        self.db = self.Session()
        self.db.add(Service(name="Cloudflare", category="Infra", status="active"))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def package(self, **item_overrides):
        item = {
            "source": "Teams",
            "source_id": "msg-1",
            "source_url": "https://teams.example/message/msg-1",
            "thread_id": "thread-1",
            "created_at": "2026-06-09T08:30:00Z",
            "sender_name": "Requester A",
            "sender_email": "requester@example.com",
            "assignee_name": "Engineer A",
            "assignee_email": "engineer.a@example.com",
            "title": "Restore Cloudflare DNS",
            "body_excerpt": "Restore Cloudflare DNS token=secret-value [DONE]",
            "service_hint": "Cloudflare",
            "status_hint": "Done",
            "estimate_hours": 2,
        }
        item.update(item_overrides)
        return {
            "schema_version": "1.0",
            "collector": {
                "type": "local-helper",
                "version": "0.1.0",
                "member_name": "Engineer A",
                "member_email": "engineer.a@example.com",
                "collected_at": "2026-06-09T09:00:00Z",
            },
            "privacy": {
                "mode": "filtered",
                "ruleset_name": "default-work-evidence",
                "previewed_by_member": True,
                "redaction_enabled": True,
            },
            "items": [item],
        }

    def test_redacts_secret_like_text(self):
        from app.services.member_intake import redact_text

        redacted = redact_text("Deploy with token=secret-value and Bearer abc.def")

        self.assertEqual(redacted, "Deploy with [REDACTED] and [REDACTED]")

    def test_imports_member_package_item(self):
        from app.services.member_intake import import_member_package

        result = import_member_package(self.db, self.package())

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["review"], 0)
        item = self.db.query(WorkItem).one()
        self.assertEqual(item.title, "Restore Cloudflare DNS")
        self.assertEqual(item.status, "Done")
        self.assertEqual(item.source, "Teams")
        self.assertEqual(item.source_id, "Teams:msg-1")
        self.assertEqual(item.assignee.email, "engineer.a@example.com")
        self.assertEqual(item.service.name, "Cloudflare")
        self.assertIn("[REDACTED]", item.description)

    def test_skips_duplicate_source_id(self):
        from app.services.member_intake import import_member_package

        first = import_member_package(self.db, self.package())
        second = import_member_package(self.db, self.package())

        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["skipped"], 1)
        self.assertEqual(self.db.query(WorkItem).count(), 1)

    def test_attaches_new_message_from_same_teams_thread_for_review(self):
        from app.services.member_intake import import_member_package

        first = import_member_package(self.db, self.package())
        second = import_member_package(self.db, self.package(
            source_id="msg-2",
            title="Requester confirmation",
            body_excerpt="The DNS issue is resolved, thank you.",
            status_hint="Open",
        ))

        self.assertEqual(first["imported"], 1)
        self.assertEqual(second["imported"], 0)
        self.assertEqual(second["evidence_attached"], 1)
        self.assertEqual(second["review"], 1)
        self.assertEqual(self.db.query(WorkItem).count(), 1)
        self.assertEqual(self.db.query(WorkItemEvidence).count(), 2)
        self.assertEqual(self.db.query(AIReview).count(), 1)

        duplicate_reply = import_member_package(self.db, self.package(
            source_id="msg-2",
            title="Requester confirmation",
            body_excerpt="The DNS issue is resolved, thank you.",
        ))
        self.assertEqual(duplicate_reply["skipped"], 1)
        self.assertEqual(self.db.query(WorkItemEvidence).count(), 2)

    def test_marks_missing_service_for_review(self):
        from app.services.member_intake import import_member_package

        result = import_member_package(self.db, self.package(service_hint="UnknownService"))

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["review"], 1)
        item = self.db.query(WorkItem).one()
        self.assertIn("Needs review: unknown service", item.notes)
        self.assertEqual(self.db.query(AIReview).count(), 1)

    def test_imports_service_alias_with_confidence_note(self):
        from app.services.member_intake import import_member_package

        result = import_member_package(self.db, self.package(service_hint="dns"))

        self.assertEqual(result["low_confidence"], 0)
        item = self.db.query(WorkItem).one()
        self.assertEqual(item.service.name, "Cloudflare")
        self.assertIn("Confidence: assignee=1.00, service=0.85", item.notes)

    def test_helper_fallback_assignee_is_low_confidence(self):
        from app.services.member_intake import import_member_package

        pkg = self.package(assignee_email="", assignee_name="")
        result = import_member_package(self.db, pkg)

        self.assertEqual(result["low_confidence"], 1)
        item = self.db.query(WorkItem).one()
        self.assertEqual(item.assignee.email, "engineer.a@example.com")
        self.assertIn("assignee=0.70", item.notes)
        self.assertIn("Needs review: low assignee confidence", item.notes)

    def test_package_intake_route_is_registered(self):
        from app.routers.intake import router

        paths = {route.path for route in router.routes}

        self.assertIn("/api/intake/package", paths)

    def test_resolves_service_alias_with_confidence(self):
        from app.services.intake_rules import resolve_service_alias

        service_name, confidence, ambiguous = resolve_service_alias("please check k8s ingress")

        self.assertEqual(service_name, "Kubernetes")
        self.assertEqual(confidence, 0.85)
        self.assertFalse(ambiguous)

    def test_resolves_identity_alias_with_confidence(self):
        from app.services.intake_rules import resolve_identity_alias

        identity = resolve_identity_alias(
            None,
            "A Nguyen",
            None,
            None,
            aliases={"engineer.a@example.com": ["A Nguyen"]},
        )

        self.assertEqual(identity["email"], "engineer.a@example.com")
        self.assertEqual(identity["name"], "A Nguyen")
        self.assertEqual(identity["confidence"], 0.85)


    def test_handles_race_condition_on_source_id(self):
        from app.services.member_intake import import_member_package

        existing = WorkItem(title="Existing", source_id="Teams:race-import")
        self.db.add(existing)
        self.db.flush()

        pkg = self.package(source_id="race-import")
        result = import_member_package(self.db, pkg)

        self.assertEqual(result["imported"], 0)
        self.assertEqual(result["skipped"], 1)


if __name__ == "__main__":
    unittest.main()
