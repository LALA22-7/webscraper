"""
Email Validator — 4-layer async validation pipeline

Layer 1: Format  (regex RFC 5322)
Layer 2: Disposable domain check (3000+ throwaway domains)
Layer 3: DNS MX record lookup (async, non-blocking)
Layer 4: SMTP RCPT TO ping (no email sent, just checks if mailbox exists)

Usage:
    validator = EmailValidator()
    result = await validator.validate("contact@somehotel.ch")
    # result.status -> "valid" | "risky" | "invalid" | "disposable"
    # result.score  -> 0-100
"""

import asyncio
import re
import socket
import smtplib
from dataclasses import dataclass, field
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# ── RFC 5322 simplified regex ───────────────────────────────────────────────
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*"
    r"\.[a-zA-Z]{2,}$"
)

# ── Known disposable / throwaway domains ───────────────────────────────────
# Extended list — these are the most common ones seen in scraping
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "tempmail.com", "throwam.com",
    "sharklasers.com", "guerrillamailblock.com", "grr.la", "guerrillamail.info",
    "guerrillamail.biz", "guerrillamail.de", "guerrillamail.net", "guerrillamail.org",
    "spam4.me", "trashmail.com", "trashmail.me", "trashmail.at", "trashmail.io",
    "trashmail.net", "trashmail.org", "trashmail.xyz", "yopmail.com",
    "yopmail.fr", "cool.fr.nf", "jetable.fr.nf", "nospam.ze.tc",
    "nomail.xl.cx", "mega.zik.dj", "speed.1s.fr", "courriel.fr.nf",
    "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf", "dispostable.com",
    "maildrop.cc", "mailnull.com", "spamgourmet.com", "spamgourmet.net",
    "spamgourmet.org", "jetable.net", "jetable.org", "jetable.pp.ua",
    "mail-temporaire.fr", "fakemail.net", "mailnew.com", "mailexpire.com",
    "discardmail.com", "discardmail.de", "spamhole.com", "spam.la",
    "baxomale.ht.cx", "mailzilla.org", "throwam.com", "tempinbox.com",
    "spamfree24.org", "spamfree24.de", "spamfree24.eu", "spamfree24.net",
    "spamfree24.info", "antichef.com", "antichef.net", "antireg.ru",
    "antispam.de", "antispammail.de", "armyspy.com", "cuvox.de",
    "dayrep.com", "einrot.com", "fleckens.hu", "gustr.com",
    "jourrapide.com", "rhyta.com", "superrito.com", "teleworm.us",
    "10minutemail.com", "10minutemail.net", "10minutemail.org", "temp-mail.org",
    "temp-mail.ru", "tempmail.net", "tempr.email", "discard.email",
    "mailhazard.com", "getnada.com", "inboxbear.com", "moakt.com",
    "spamex.com", "deadaddress.com", "mailnesia.com", "nowmymail.com",
    "0-mail.com", "0815.ru", "0815.su", "0clickemail.com",
}

# ── Role-based prefixes (lower quality but not invalid) ────────────────────
ROLE_BASED = {"info", "admin", "support", "help", "sales", "contact",
              "hello", "no-reply", "noreply", "webmaster", "postmaster",
              "abuse", "mail", "marketing", "press", "hr", "jobs", "careers"}


@dataclass
class EmailValidationResult:
    email: str
    status: str          # "valid" | "risky" | "invalid" | "disposable"
    score: int           # 0-100
    checks_passed: List[str] = field(default_factory=list)
    checks_failed: List[str] = field(default_factory=list)
    is_role_based: bool = False
    mx_records: List[str] = field(default_factory=list)
    error: Optional[str] = None


class EmailValidator:
    """
    Async 4-layer email validator.
    Instantiate once and reuse — DNS resolver is cached.
    """

    def __init__(self, smtp_timeout: float = 5.0, smtp_from: str = "verify@leadengine.io"):
        self.smtp_timeout = smtp_timeout
        self.smtp_from = smtp_from
        self._mx_cache: dict = {}

    # ── PUBLIC API ──────────────────────────────────────────────────────────

    async def validate(self, email: str) -> EmailValidationResult:
        result = EmailValidationResult(email=email, status="invalid", score=0)
        email = email.strip().lower()
        result.email = email

        # Layer 1: Format
        if not self._check_format(email):
            result.checks_failed.append("format")
            result.status = "invalid"
            result.score = 0
            return result
        result.checks_passed.append("format")
        result.score += 20

        local, domain = email.rsplit("@", 1)

        # Check role-based
        result.is_role_based = local.split("+")[0] in ROLE_BASED

        # Layer 2: Disposable domain
        if self._check_disposable(domain):
            result.checks_failed.append("disposable_check")
            result.status = "disposable"
            result.score = 5
            return result
        result.checks_passed.append("disposable_check")
        result.score += 20

        # Layer 3: DNS MX lookup
        mx_hosts = await self._get_mx_records(domain)
        if not mx_hosts:
            result.checks_failed.append("mx_record")
            result.status = "invalid"
            result.score += 0
            return result
        result.checks_passed.append("mx_record")
        result.mx_records = mx_hosts
        result.score += 30

        # Layer 4: SMTP RCPT TO check
        smtp_status = await self._smtp_check(email, mx_hosts[0])
        if smtp_status == "valid":
            result.checks_passed.append("smtp_ping")
            result.status = "valid"
            result.score += 30
        elif smtp_status == "catch_all":
            result.checks_passed.append("smtp_ping_catchall")
            result.status = "risky"
            result.score += 15
        elif smtp_status == "invalid":
            result.checks_failed.append("smtp_ping")
            result.status = "invalid"
            result.score = max(0, result.score - 20)
        else:
            # SMTP blocked/timeout — treat as risky, not invalid
            result.checks_passed.append("smtp_ping_skipped")
            result.status = "risky"
            result.score += 10

        return result

    async def validate_batch(self, emails: List[str], concurrency: int = 5) -> List[EmailValidationResult]:
        """Validate multiple emails concurrently."""
        sem = asyncio.Semaphore(concurrency)
        async def _validate_one(email):
            async with sem:
                return await self.validate(email)
        return await asyncio.gather(*[_validate_one(e) for e in emails])

    # ── LAYER 1: Format ─────────────────────────────────────────────────────

    def _check_format(self, email: str) -> bool:
        if not email or len(email) > 254 or "@" not in email:
            return False
        return bool(EMAIL_REGEX.match(email))

    # ── LAYER 2: Disposable ─────────────────────────────────────────────────

    def _check_disposable(self, domain: str) -> bool:
        if domain in DISPOSABLE_DOMAINS:
            return True
        # Try to also load the pip package if installed
        try:
            from disposable_email_domains import blocklist
            return domain in blocklist
        except ImportError:
            return False

    # ── LAYER 3: DNS MX ─────────────────────────────────────────────────────

    async def _get_mx_records(self, domain: str) -> List[str]:
        if domain in self._mx_cache:
            return self._mx_cache[domain]

        try:
            # Try aiodns first (fastest, non-blocking)
            import aiodns
            resolver = aiodns.DNSResolver()
            records = await resolver.query(domain, "MX")
            hosts = sorted([str(r.host).rstrip(".") for r in records], key=lambda x: x)
            self._mx_cache[domain] = hosts
            return hosts
        except ImportError:
            pass
        except Exception:
            pass

        # Fallback: synchronous DNS in thread pool (always works)
        try:
            loop = asyncio.get_event_loop()
            import dns.resolver as dns_resolver
            def _sync_lookup():
                answers = dns_resolver.resolve(domain, "MX")
                return sorted([str(r.exchange).rstrip(".") for r in answers])
            hosts = await loop.run_in_executor(None, _sync_lookup)
            self._mx_cache[domain] = hosts
            return hosts
        except ImportError:
            pass
        except Exception:
            pass

        # Last fallback: check if domain resolves at all
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, socket.gethostbyname, domain)
            # Domain resolves but no explicit MX — many small sites use domain as MX
            self._mx_cache[domain] = [domain]
            return [domain]
        except Exception:
            self._mx_cache[domain] = []
            return []

    # ── LAYER 4: SMTP RCPT TO ───────────────────────────────────────────────

    async def _smtp_check(self, email: str, mx_host: str) -> str:
        """
        Returns:
          "valid"    — mailbox exists
          "catch_all"— server accepts anything (can't verify individual mailbox)
          "invalid"  — mailbox does not exist (550 error)
          "blocked"  — server refused connection or timed out
        """
        loop = asyncio.get_event_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._smtp_check_sync, email, mx_host),
                timeout=self.smtp_timeout
            )
            return result
        except asyncio.TimeoutError:
            return "blocked"
        except Exception as e:
            logger.debug(f"SMTP check error for {email}: {e}")
            return "blocked"

    def _smtp_check_sync(self, email: str, mx_host: str) -> str:
        """Synchronous SMTP RCPT TO check — runs in thread pool."""
        fake_email = f"check_catch_all_{id(email)}@{email.split('@')[1]}"
        try:
            smtp = smtplib.SMTP(timeout=self.smtp_timeout)
            smtp.connect(mx_host, 25)
            smtp.helo("leadengine.io")
            smtp.mail(self.smtp_from)

            # First try a fake address to detect catch-all
            code, _ = smtp.rcpt(fake_email)
            if code == 250:
                smtp.quit()
                return "catch_all"

            # Now try the real address
            code, msg = smtp.rcpt(email)
            smtp.quit()
            if code == 250:
                return "valid"
            elif code in (550, 551, 552, 553, 554):
                return "invalid"
            else:
                return "catch_all"

        except smtplib.SMTPConnectError:
            return "blocked"
        except smtplib.SMTPServerDisconnected:
            return "blocked"
        except ConnectionRefusedError:
            return "blocked"
        except OSError:
            return "blocked"
        except Exception as e:
            logger.debug(f"SMTP sync error: {e}")
            return "blocked"
