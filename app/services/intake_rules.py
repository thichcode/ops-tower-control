import re
from typing import Any


CONFIDENCE_EXACT = 1.0
CONFIDENCE_ALIAS = 0.85
CONFIDENCE_FALLBACK = 0.7
CONFIDENCE_MISSING = 0.0
REVIEW_THRESHOLD = 0.8

SERVICE_ALIASES = {
    "Cloudflare": ["cloudflare", "cf", "dns", "waf"],
    "Kubernetes": ["kubernetes", "k8s", "pod", "ingress"],
    "Backup": ["backup", "veeam", "restore"],
    "ServiceDesk": ["servicedesk", "service desk", "sdp", "ticket"],
    "Zabbix": ["zabbix", "monitoring", "alert"],
    "GitLab": ["gitlab", "git", "repo", "pipeline", "ci"],
}

IDENTITY_ALIASES = {}


def resolve_service_alias(value: Any, aliases: dict[str, list[str]] | None = None) -> tuple[str | None, float, bool]:
    text = _normalize(value)
    if not text:
        return None, CONFIDENCE_MISSING, False

    matches = []
    for service_name, service_aliases in (aliases or SERVICE_ALIASES).items():
        for alias in service_aliases:
            normalized_alias = _normalize(alias)
            if normalized_alias and _contains_alias(text, normalized_alias):
                matches.append((service_name, len(normalized_alias)))

    if not matches:
        return None, CONFIDENCE_MISSING, False

    matches.sort(key=lambda item: item[1], reverse=True)
    best_length = matches[0][1]
    best = {service_name for service_name, length in matches if length == best_length}
    if len(best) > 1:
        return None, CONFIDENCE_MISSING, True
    return matches[0][0], CONFIDENCE_ALIAS, False


def resolve_identity_alias(
    email: Any,
    name: Any,
    fallback_email: Any,
    fallback_name: Any,
    aliases: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    normalized_email = (str(email).strip().lower() if email else "")
    if normalized_email:
        return {"email": normalized_email, "name": str(name).strip() if name else normalized_email.split("@")[0], "confidence": CONFIDENCE_EXACT}

    normalized_name = _normalize(name)
    if normalized_name:
        for canonical_email, names in (aliases or IDENTITY_ALIASES).items():
            for alias in names:
                if normalized_name == _normalize(alias):
                    return {"email": canonical_email, "name": str(name).strip(), "confidence": CONFIDENCE_ALIAS}

    normalized_fallback_email = (str(fallback_email).strip().lower() if fallback_email else "")
    if normalized_fallback_email:
        return {
            "email": normalized_fallback_email,
            "name": str(fallback_name).strip() if fallback_name else normalized_fallback_email.split("@")[0],
            "confidence": CONFIDENCE_FALLBACK,
        }

    return {"email": None, "name": str(name).strip() if name else None, "confidence": CONFIDENCE_MISSING}


def _normalize(value: Any) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _contains_alias(text: str, alias: str) -> bool:
    if " " in alias:
        return alias in text
    return re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", text) is not None
