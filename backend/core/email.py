# backend/core/email.py
"""
---
name: email
description: "Email sender abstraction for auth flows: dev mode logs links to stdout/outbox file; production placeholder for SMTP integration"
type: core
target:
  layer: backend
  domain: email
spec_doc: null
test_file: null
functions:
  - name: EmailSender
    line: 17
    purpose: "Abstract base class defining email sender interface"
  - name: EmailSender.send_reset_email
    line: 21
    purpose: "Send password reset email"
  - name: EmailSender.send_invite_email
    line: 26
    purpose: "Send user invitation email"
  - name: EmailSender.send_verification_email
    line: 31
    purpose: "Send email verification email"
  - name: DevEmailSender
    line: 36
    purpose: "Dev implementation: logs links to stdout and optional outbox file"
  - name: DevEmailSender.send_reset_email
    line: 53
    purpose: "Log/record reset link (only visible if AUTH_DEV_EXPOSE_RESET_LINK=true)"
  - name: DevEmailSender.send_invite_email
    line: 60
    purpose: "Log/record invite link"
  - name: DevEmailSender.send_verification_email
    line: 67
    purpose: "Log/record verification link"
  - name: get_email_sender
    line: 75
    purpose: "Factory: return appropriate EmailSender based on environment"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime


def _log_with_time(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


class EmailSender(ABC):
    """Base email sender abstraction."""

    @abstractmethod
    async def send_reset_email(self, email: str, reset_link: str) -> None:
        """Send password reset email."""
        pass

    @abstractmethod
    async def send_invite_email(self, email: str, invite_link: str) -> None:
        """Send user invitation email."""
        pass

    @abstractmethod
    async def send_verification_email(self, email: str, verify_link: str) -> None:
        """Send email verification email."""
        pass


class DevEmailSender(EmailSender):
    """Development email sender — writes links to log and optional outbox file."""

    def __init__(self):
        self.outbox_file = os.getenv("AUTH_DEV_RESET_LINK_FILE", "")
        self.expose_links = os.getenv("AUTH_DEV_EXPOSE_RESET_LINK", "false").lower() in ("true", "1", "yes")

    def _write_to_outbox(self, subject: str, email: str, link: str):
        """Write link to outbox file if configured."""
        if not self.outbox_file:
            return
        try:
            with open(self.outbox_file, "a") as f:
                f.write(f"[{datetime.now().isoformat()}] {subject} | {email} | {link}\n")
        except Exception as e:
            _log_with_time(f"[DevEmail] Failed to write to outbox file: {e}")

    async def send_reset_email(self, email: str, reset_link: str) -> None:
        if self.expose_links:
            _log_with_time(f"[DevEmail] Password Reset for {email}: {reset_link}")
            self._write_to_outbox("PASSWORD_RESET", email, reset_link)
        else:
            _log_with_time(f"[DevEmail] Password reset email queued for {email} (link hidden, set AUTH_DEV_EXPOSE_RESET_LINK=true to see)")

    async def send_invite_email(self, email: str, invite_link: str) -> None:
        if self.expose_links:
            _log_with_time(f"[DevEmail] Invite for {email}: {invite_link}")
            self._write_to_outbox("INVITE", email, invite_link)
        else:
            _log_with_time(f"[DevEmail] Invite email queued for {email} (link hidden, set AUTH_DEV_EXPOSE_RESET_LINK=true to see)")

    async def send_verification_email(self, email: str, verify_link: str) -> None:
        if self.expose_links:
            _log_with_time(f"[DevEmail] Email Verification for {email}: {verify_link}")
            self._write_to_outbox("EMAIL_VERIFY", email, verify_link)
        else:
            _log_with_time(f"[DevEmail] Verification email queued for {email} (link hidden, set AUTH_DEV_EXPOSE_RESET_LINK=true to see)")


def get_email_sender() -> EmailSender:
    """Factory: return appropriate email sender based on environment.

    For now, always returns DevEmailSender.
    When SMTP is configured in the future, this will return SmtpEmailSender.
    """
    # Future: check SMTP_HOST env and return SmtpEmailSender if configured
    return DevEmailSender()
