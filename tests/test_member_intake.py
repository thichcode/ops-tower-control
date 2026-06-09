import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Service, User, WorkItem


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

    def test_marks_missing_service_for_review(self):
        from app.services.member_intake import import_member_package

        result = import_member_package(self.db, self.package(service_hint="UnknownService"))

        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["review"], 1)
        item = self.db.query(WorkItem).one()
        self.assertIn("Needs review: unknown service", item.notes)

    def test_package_intake_route_is_registered(self):
        from app.routers.intake import router

        paths = {route.path for route in router.routes}

        self.assertIn("/api/intake/package", paths)


if __name__ == "__main__":
    unittest.main()
