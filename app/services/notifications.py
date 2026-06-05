import os
import requests
import json

TEAMS_DIGEST_WEBHOOK = os.getenv("TEAMS_DIGEST_WEBHOOK_URL", "")
TEAMS_ALERT_WEBHOOK = os.getenv("TEAMS_ALERT_WEBHOOK_URL", "")


def send_teams_card(webhook_url: str, title: str, summary: str, sections: list, color: str = "0078D7"):
    if not webhook_url:
        return {"error": "No webhook URL configured"}
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": color,
        "title": title,
        "summary": summary,
        "sections": sections,
    }
    try:
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}
