"""Shared SMS content helpers."""

from __future__ import annotations

import re

UNSUBSCRIBE_LINE_RE = re.compile(r"^to stop emails, click unsubscribe:\s*https?://\S+\s*$", re.IGNORECASE)
SIGNATURE_START_RE = re.compile(r"^(thanks|thank you|best|best regards|kind regards|regards|sincerely|cheers)[,!\s]*$", re.IGNORECASE)


def build_sms_from_email_content(*, subject: str, body: str, contact_first_name: str | None = None) -> str:
    first_name = (contact_first_name or "").strip()
    cleaned_body = _strip_email_body(body)
    cleaned_body = re.sub(r"\s+", " ", cleaned_body).strip()
    cleaned_subject = re.sub(r"\s+", " ", subject).strip()

    if not cleaned_body and cleaned_subject:
        cleaned_body = cleaned_subject

    if first_name and cleaned_body.lower().startswith("hi "):
        greeting = ""
    elif first_name:
        greeting = f"Hi {first_name}, "
    else:
        greeting = "Hi, "

    message = f"{greeting}{cleaned_body}".strip()
    if cleaned_subject and cleaned_subject.lower() not in cleaned_body.lower():
        message = f"{message} ({cleaned_subject})".strip()

    message = re.sub(r"\s+", " ", message).strip(" -")
    if len(message) <= 320:
        return message

    truncated = message[:317].rsplit(" ", 1)[0].strip()
    return f"{truncated}..."


def _strip_email_body(body: str) -> str:
    lines = []
    for raw_line in body.replace("\r", "").split("\n"):
        line = raw_line.strip()
        if not line or line == "---" or UNSUBSCRIBE_LINE_RE.match(line):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            continue
        lines.append(line)

    while lines and SIGNATURE_START_RE.match(lines[-1]):
        lines.pop()
    if lines and SIGNATURE_START_RE.match(lines[-1]):
        lines.pop()

    for index, line in enumerate(lines):
        if SIGNATURE_START_RE.match(line):
            lines = lines[:index]
            break

    return " ".join(lines).strip()
