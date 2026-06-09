import argparse
import json
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from app.services.intake_rules import resolve_service_alias
from app.services.member_intake import redact_text


STATUS_TAGS = {
    "[DONE]": "Done",
    "[XONG]": "Done",
    "[HOÀN THÀNH]": "Done",
    "[BLOCKED]": "Blocked",
    "[TẠM DỪNG]": "Blocked",
    "[VƯỚNG]": "Blocked",
    "[OPEN]": "Open",
    "[ĐANG LÀM]": "Open",
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self):
        return "".join(self.parts).strip()


def build_package(data: dict[str, Any], member_name: str, member_email: str, previewed: bool) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "collector": {
            "type": "local-helper",
            "version": "0.1.0",
            "member_name": member_name,
            "member_email": member_email,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        },
        "privacy": {
            "mode": "filtered",
            "ruleset_name": "default-work-evidence",
            "previewed_by_member": previewed,
            "redaction_enabled": True,
        },
        "items": _normalize_items(data, member_name, member_email),
    }


def write_package(package: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")


def send_package(package: dict[str, Any], url: str) -> str:
    body = json.dumps(package, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a privacy-filtered OpsDash member intake package")
    parser.add_argument("--input", required=True, help="Local JSON file with items[] or Power Automate value[]")
    parser.add_argument("--member-name", required=True)
    parser.add_argument("--member-email", required=True)
    parser.add_argument("--output")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--send-url")
    args = parser.parse_args(argv)

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    package = build_package(data, args.member_name, args.member_email, previewed=args.preview)

    if args.preview:
        print(f"Package preview: {len(package['items'])} items")
        for item in package["items"][:10]:
            print(f"- {item['source']} {item.get('created_at') or '-'}: {item['title']}")

    if args.output:
        write_package(package, Path(args.output))
        print(f"Wrote {args.output}")

    if args.send_url:
        print(send_package(package, args.send_url))

    if not args.output and not args.send_url and not args.preview:
        json.dump(package, sys.stdout, ensure_ascii=False, indent=2)
        print()

    return 0


def _normalize_items(data: dict[str, Any], member_name: str, member_email: str) -> list[dict[str, Any]]:
    if isinstance(data.get("items"), list):
        return [_normalize_item(item, member_name, member_email) for item in data["items"]]
    if isinstance(data.get("value"), list):
        return [_normalize_power_automate_message(message, member_name, member_email) for message in data["value"]]
    return []


def _normalize_item(item: dict[str, Any], member_name: str, member_email: str) -> dict[str, Any]:
    body = redact_text(item.get("body_excerpt") or item.get("description") or "")
    title = item.get("title") or _first_line(body)
    return {
        "source": item.get("source") or "Teams",
        "source_id": item.get("source_id"),
        "source_url": item.get("source_url"),
        "thread_id": item.get("thread_id"),
        "created_at": item.get("created_at"),
        "sender_name": item.get("sender_name"),
        "sender_email": item.get("sender_email"),
        "assignee_name": item.get("assignee_name") or member_name,
        "assignee_email": item.get("assignee_email") or member_email,
        "title": title,
        "body_excerpt": body,
        "service_hint": item.get("service_hint") or _detect_service(f"{title} {body}"),
        "status_hint": item.get("status_hint") or _detect_status(f"{title} {body}"),
        "estimate_hours": item.get("estimate_hours"),
        "privacy_labels": ["member-approved", "redacted"],
    }


def _normalize_power_automate_message(message: dict[str, Any], member_name: str, member_email: str) -> dict[str, Any]:
    user = (message.get("from") or {}).get("user") or {}
    body = message.get("body") or {}
    content = body.get("content") if isinstance(body, dict) else str(body)
    text = _strip_html(content or "")
    title = (message.get("subject") or _first_line(text))[:120]
    clean_body = redact_text(text)
    return {
        "source": "Teams",
        "source_id": message.get("id") or message.get("messageId"),
        "source_url": message.get("webUrl"),
        "thread_id": message.get("conversationId"),
        "created_at": message.get("createdDateTime"),
        "sender_name": user.get("displayName"),
        "sender_email": user.get("userPrincipalName"),
        "assignee_name": member_name,
        "assignee_email": member_email,
        "title": title,
        "body_excerpt": clean_body,
        "service_hint": _detect_service(f"{title} {clean_body}"),
        "status_hint": _detect_status(f"{title} {clean_body}"),
        "estimate_hours": None,
        "privacy_labels": ["member-approved", "redacted"],
    }


def _strip_html(value: str) -> str:
    if "<" not in value:
        return value.strip()
    extractor = _HTMLTextExtractor()
    extractor.feed(value)
    return extractor.get_text()


def _first_line(value: str) -> str:
    return value.splitlines()[0].strip() if value.strip() else "(no subject)"


def _detect_service(value: str) -> str | None:
    service_name, _confidence, ambiguous = resolve_service_alias(value)
    return service_name if not ambiguous else None


def _detect_status(value: str) -> str:
    upper = value.upper()
    for tag, status in STATUS_TAGS.items():
        if tag in upper:
            return status
    return "Open"


if __name__ == "__main__":
    raise SystemExit(main())
