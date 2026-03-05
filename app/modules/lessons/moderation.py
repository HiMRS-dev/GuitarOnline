"""Baseline content moderation helpers for lesson reports."""

from __future__ import annotations

import re

from app.shared.exceptions import BusinessRuleException

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
HANDLE_RE = re.compile(r"@\w{3,}")
CONTACT_KEYWORDS = (
    "telegram",
    "whatsapp",
    "viber",
    "signal",
    "discord",
    "skype",
    "contact",
    "phone",
    "email",
    "mail",
    "dm me",
)
CONTACT_LINK_MARKERS = (
    "t.me/",
    "telegram.me/",
    "wa.me/",
    "whatsapp.com/",
    "discord.gg/",
    "skype:",
    "mailto:",
    "tel:",
)
CONTACT_BLOCK_MESSAGE = "Report contains restricted contact information"


def _contains_contact_pattern(text: str) -> bool:
    normalized = text.lower()
    if EMAIL_RE.search(text):
        return True
    if PHONE_RE.search(text):
        return True
    if HANDLE_RE.search(text):
        return True
    return any(keyword in normalized for keyword in CONTACT_KEYWORDS)


def validate_report_content(
    *,
    notes: str | None,
    homework: str | None,
    links: list[str] | None,
) -> None:
    """Reject report payload with obvious direct-contact details."""
    for value in (notes, homework):
        if value and _contains_contact_pattern(value):
            raise BusinessRuleException(CONTACT_BLOCK_MESSAGE)

    for link in links or []:
        normalized = str(link).strip().lower()
        if not normalized:
            continue
        if any(marker in normalized for marker in CONTACT_LINK_MARKERS):
            raise BusinessRuleException(CONTACT_BLOCK_MESSAGE)
