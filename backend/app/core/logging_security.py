"""Redact credentials and common identifiers before log records reach handlers."""

import logging
import re


def redact_log_text(text: str, secrets: tuple[str, ...] = ()) -> str:
    for secret in sorted((value for value in secrets if value and len(value) >= 8), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(postgres(?:ql)?(?:\+\w+)?://)[^\s]+", r"\1[REDACTED]", text)
    text = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^\s/:@]+:[^\s@]+@", r"\1[REDACTED]@", text)
    text = re.sub(r"AIza[\w-]{25,}", "[REDACTED]", text)
    text = re.sub(r"eyJ[\w-]+\.[\w-]+\.[\w-]+", "[REDACTED]", text)
    text = re.sub(r"(?i)\bBearer\s+[^\s,;]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)((?:authorization|password|api[_-]?key|jwt[_-]?secret|csrf[_-]?token|x-csrf-token)\s*[=:]\s*)(?:Bearer\s+)?[^\s,;]+", r"\1[REDACTED]", text)
    text = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL REDACTED]", text)
    text = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN REDACTED]", text)
    return text


def install_log_redaction(settings) -> None:
    """Use a record factory so application and third-party handlers receive safe text."""
    previous = logging.getLogRecordFactory()
    if getattr(previous, "_claimwise_redaction", False):
        return
    configured = tuple(value for value in (
        settings.database_url, settings.gemini_api_key, settings.jwt_secret,
        settings.supabase_key, settings.supabase_service_role_key,
    ) if isinstance(value, str))

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        record.msg = redact_log_text(record.getMessage(), configured)
        record.args = ()
        if record.exc_info:
            # Exception values can include SQL parameters or entire private documents.
            record.exc_text = f"[{record.exc_info[0].__name__}: details withheld]"
            record.exc_info = None
        return record

    factory._claimwise_redaction = True
    logging.setLogRecordFactory(factory)
