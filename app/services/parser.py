import re
from typing import Optional
from decimal import Decimal

KNOWN_WORK_TYPES = {
    "incident", "request", "project", "audit", "consulting",
    "improvement", "poc", "meeting", "training", "vendor", "risk",
}


def parse_teams_command(command: str, db_services=None) -> dict:
    result = {
        "estimate_hours": None,
        "work_type": None,
        "service_hint": None,
        "title_suffix": None,
    }

    if not command or not command.startswith("/"):
        return result

    parts = command.strip().split()
    cmd = parts[0].lower() if parts else ""

    if cmd not in ("/task", "/done", "/block", "/risk"):
        return result

    result["command"] = cmd

    if cmd == "/task" and len(parts) > 1:
        tokens = parts[1:]
        remaining = []

        for token in tokens:
            lower = token.lower()

            hour_match = re.match(r"^(\d+(?:\.\d+)?)h?$", lower)
            if hour_match:
                result["estimate_hours"] = Decimal(str(hour_match.group(1)))
                continue

            if lower in KNOWN_WORK_TYPES:
                result["work_type"] = lower.capitalize()
                continue

            if db_services:
                for svc in db_services:
                    if lower == svc["name"].lower():
                        result["service_hint"] = svc
                        break

            if result["service_hint"] is None:
                remaining.append(token)

        if remaining:
            result["title_suffix"] = " ".join(remaining)

    return result
