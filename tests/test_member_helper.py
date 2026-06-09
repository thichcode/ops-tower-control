import json
import tempfile
import unittest
from pathlib import Path


class MemberHelperTest(unittest.TestCase):
    def test_builds_package_from_items(self):
        from tools.member_helper import build_package

        data = {
            "items": [
                {
                    "source": "Teams",
                    "source_id": "msg-1",
                    "created_at": "2026-06-09T08:30:00Z",
                    "sender_name": "Requester A",
                    "assignee_name": "Engineer A",
                    "title": "Restore Cloudflare DNS",
                    "body_excerpt": "Restore Cloudflare DNS token=secret-value [DONE]",
                    "service_hint": "Cloudflare",
                }
            ]
        }

        package = build_package(data, "Engineer A", "engineer.a@example.com", previewed=True)

        self.assertEqual(package["schema_version"], "1.0")
        self.assertEqual(package["collector"]["member_email"], "engineer.a@example.com")
        self.assertTrue(package["privacy"]["previewed_by_member"])
        self.assertEqual(package["items"][0]["assignee_email"], "engineer.a@example.com")
        self.assertIn("[REDACTED]", package["items"][0]["body_excerpt"])

    def test_builds_package_from_power_automate_value(self):
        from tools.member_helper import build_package

        data = {
            "value": [
                {
                    "id": "msg-1",
                    "channelId": "channel-1",
                    "conversationId": "thread-1",
                    "createdDateTime": "2026-06-09T08:30:00Z",
                    "from": {"user": {"displayName": "Engineer A", "userPrincipalName": "engineer.a@example.com"}},
                    "body": {"content": "Fix Cloudflare DNS [DONE]", "contentType": "html"},
                    "subject": None,
                }
            ]
        }

        package = build_package(data, "Engineer A", "engineer.a@example.com", previewed=False)

        self.assertEqual(package["items"][0]["source"], "Teams")
        self.assertEqual(package["items"][0]["source_id"], "msg-1")
        self.assertEqual(package["items"][0]["thread_id"], "thread-1")
        self.assertEqual(package["items"][0]["status_hint"], "Done")

    def test_writes_package_file(self):
        from tools.member_helper import write_package

        package = {"schema_version": "1.0", "items": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "package.json"
            write_package(package, output)

            written = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(written, package)


if __name__ == "__main__":
    unittest.main()
