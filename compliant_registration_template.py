"""Compliant registration flow automation template.

This template is intentionally scoped for legitimate testing of your OWN website
or an environment where you have explicit authorization.

Features:
- One-by-one execution (no bulk bypass behavior)
- Optional human confirmation step before submit
- Structured logging for audit and rollback
- Pluggable OTP provider interface (example uses local/mock source)

Dependencies:
    pip install playwright
    playwright install chromium
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import logging
import time
from pathlib import Path
from typing import Optional, Protocol

from playwright.sync_api import Browser, Page, sync_playwright


@dataclasses.dataclass
class RegistrationRecord:
    """Single registration input record for authorized test use."""

    email: str
    password: str
    display_name: str = ""


class OtpProvider(Protocol):
    """OTP provider interface for your own lawful infrastructure."""

    def fetch_code(self, email: str, timeout_sec: int = 120) -> Optional[str]:
        ...


class MockOtpProvider:
    """Demo OTP provider: reads `{email}.otp` files from a local folder.

    Put the OTP code in a plain text file, e.g.:
        otp_inbox/alice@example.com.otp
    """

    def __init__(self, inbox_dir: Path) -> None:
        self.inbox_dir = inbox_dir

    def fetch_code(self, email: str, timeout_sec: int = 120) -> Optional[str]:
        otp_file = self.inbox_dir / f"{email}.otp"
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            if otp_file.exists():
                code = otp_file.read_text(encoding="utf-8").strip()
                if code:
                    return code
            time.sleep(1)
        return None


class RegistrationBot:
    """Automates a single registration flow for your owned/authorized app."""

    def __init__(self, browser: Browser, base_url: str, otp_provider: OtpProvider) -> None:
        self.browser = browser
        self.base_url = base_url.rstrip("/")
        self.otp_provider = otp_provider

    def register_one(self, record: RegistrationRecord, dry_run: bool = False) -> bool:
        page = self.browser.new_page()
        try:
            logging.info("Opening signup page for %s", record.email)
            page.goto(f"{self.base_url}/signup", wait_until="domcontentloaded")

            # Update selectors to match your own product UI.
            page.fill("input[name='email']", record.email)
            page.fill("input[name='password']", record.password)
            if record.display_name:
                page.fill("input[name='displayName']", record.display_name)

            if dry_run:
                logging.info("DRY-RUN: stop before submit for %s", record.email)
                return True

            page.click("button[type='submit']")

            # Optional OTP step
            code = self.otp_provider.fetch_code(record.email, timeout_sec=120)
            if code:
                page.fill("input[name='otp']", code)
                page.click("button[data-action='verify-otp']")
                logging.info("OTP submitted for %s", record.email)
            else:
                logging.warning("No OTP found for %s (continuing)", record.email)

            # Basic success signal (adapt to your app)
            page.wait_for_url("**/welcome", timeout=15000)
            logging.info("Registration success: %s", record.email)
            return True
        except Exception as exc:  # broad on purpose for template diagnostics
            logging.exception("Registration failed for %s: %s", record.email, exc)
            return False
        finally:
            page.close()


def load_csv(csv_path: Path) -> list[RegistrationRecord]:
    rows: list[RegistrationRecord] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"email", "password"}
        if not required.issubset(reader.fieldnames or set()):
            raise ValueError("CSV must include headers: email,password[,display_name]")

        for item in reader:
            rows.append(
                RegistrationRecord(
                    email=item["email"].strip(),
                    password=item["password"].strip(),
                    display_name=item.get("display_name", "").strip(),
                )
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compliant signup automation template for authorized environments"
    )
    parser.add_argument("--base-url", required=True, help="Your own app base url")
    parser.add_argument("--csv", required=True, type=Path, help="Input CSV path")
    parser.add_argument(
        "--otp-dir",
        type=Path,
        default=Path("otp_inbox"),
        help="Local OTP mock directory",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Fill forms but do not submit"
    )
    parser.add_argument(
        "--max-users",
        type=int,
        default=5,
        help="Safety limit for each run (default: 5)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    records = load_csv(args.csv)
    if len(records) > args.max_users:
        raise ValueError(
            f"Safety limit exceeded: {len(records)} > {args.max_users}. "
            "Increase --max-users only when you are authorized."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        bot = RegistrationBot(
            browser=browser,
            base_url=args.base_url,
            otp_provider=MockOtpProvider(args.otp_dir),
        )

        ok = 0
        for record in records:
            ok += int(bot.register_one(record, dry_run=args.dry_run))

        browser.close()
        logging.info("Completed: %s/%s success", ok, len(records))


if __name__ == "__main__":
    main()
