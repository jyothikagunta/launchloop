"""SQLite persistence for LaunchLoop's local simulation."""

from __future__ import annotations

import csv
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = BASE_DIR / "launchloop.db"
INITIAL_PLANS = [
    ("College clubs and student ambassadors", 200, 0.0, False),
    ("WhatsApp and student communities", 150, 0.0, False),
    ("Peer referrals", 100, 0.0, False),
    ("Paid promotional experiment", 50, 1500.0, False),
    ("Contingency reserve", None, 500.0, True),
]
INITIAL_REFERRAL_CODES = [f"CAMPUS0{i}" for i in range(1, 6)]
INITIAL_VARIANTS = [
    ("A", "Join our free AI workshop and build your first AI project in 60 minutes."),
    ("B", "Final-year students: Build a working AI project in 60 minutes. Join our free beginner-friendly workshop."),
]


class DuplicateRegistrationError(ValueError):
    """Raised when an email is already registered."""


class InvalidReferralCodeError(ValueError):
    """Raised when a supplied referral code is not registered."""


@contextmanager
def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with foreign keys enabled and safe cleanup."""
    connection = sqlite3.connect(str(db_path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create tables and insert the initial plans, variants, and codes once."""
    with get_connection(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                college TEXT NOT NULL,
                channel TEXT NOT NULL,
                referral_code TEXT,
                variant TEXT,
                registered_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual'
            );
            CREATE TABLE IF NOT EXISTS referral_codes (
                code TEXT PRIMARY KEY COLLATE NOCASE,
                ambassador_label TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiment_variants (
                variant TEXT PRIMARY KEY,
                message TEXT NOT NULL,
                people_reached INTEGER NOT NULL DEFAULT 0 CHECK (people_reached >= 0),
                clicks INTEGER NOT NULL DEFAULT 0 CHECK (clicks >= 0),
                registrations INTEGER NOT NULL DEFAULT 0 CHECK (registrations >= 0),
                is_simulated INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS campaign_plans (
                channel TEXT PRIMARY KEY,
                registration_target INTEGER,
                planned_budget REAL NOT NULL DEFAULT 0 CHECK (planned_budget >= 0),
                is_reserve INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS simulation_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value REAL NOT NULL DEFAULT 0 CHECK (setting_value >= 0)
            );
            CREATE INDEX IF NOT EXISTS idx_registrations_channel ON registrations(channel);
            CREATE INDEX IF NOT EXISTS idx_registrations_date ON registrations(registered_at);
            CREATE INDEX IF NOT EXISTS idx_registrations_referral ON registrations(referral_code);
            """
        )
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        connection.executemany(
            "INSERT OR IGNORE INTO referral_codes(code, ambassador_label, created_at) VALUES (?, ?, ?)",
            [(code, f"Student ambassador {code[-2:]}", now) for code in INITIAL_REFERRAL_CODES],
        )
        connection.executemany(
            "INSERT OR IGNORE INTO experiment_variants(variant, message) VALUES (?, ?)",
            INITIAL_VARIANTS,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO campaign_plans(channel, registration_target, planned_budget, is_reserve) VALUES (?, ?, ?, ?)",
            INITIAL_PLANS,
        )
        connection.execute(
            "INSERT OR IGNORE INTO simulation_settings(setting_key, setting_value) VALUES ('simulated_spend', 0)"
        )


def get_simulated_spend(db_path: str | Path = DEFAULT_DB_PATH) -> float:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT setting_value FROM simulation_settings WHERE setting_key = 'simulated_spend'"
        ).fetchone()
        return float(row[0]) if row else 0.0


def save_simulated_spend(amount: float, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    if amount < 0:
        raise ValueError("Simulated spend cannot be negative.")
    with get_connection(db_path) as connection:
        connection.execute(
            "UPDATE simulation_settings SET setting_value = ? WHERE setting_key = 'simulated_spend'",
            (float(amount),),
        )


def add_registration(
    student_name: str,
    email: str,
    college: str,
    channel: str,
    referral_code: str | None = None,
    variant: str | None = None,
    registered_at: str | None = None,
    source: str = "manual",
    db_path: str | Path = DEFAULT_DB_PATH,
) -> int:
    """Add one simulated registration, enforcing unique email and valid code."""
    normalized_code = referral_code.strip().upper() if referral_code and referral_code.strip() else None
    timestamp = registered_at or datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        with get_connection(db_path) as connection:
            if normalized_code:
                valid = connection.execute(
                    "SELECT 1 FROM referral_codes WHERE code = ? COLLATE NOCASE", (normalized_code,)
                ).fetchone()
                if not valid:
                    raise InvalidReferralCodeError(f"Referral code {normalized_code} is not active.")
            cursor = connection.execute(
                """INSERT INTO registrations
                   (student_name, email, college, channel, referral_code, variant, registered_at, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (student_name.strip(), email.strip().lower(), college.strip(), channel.strip(), normalized_code,
                 variant.strip().upper() if variant and variant.strip() else None, timestamp, source),
            )
            return int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        if "registrations.email" in str(exc).lower() or "unique constraint failed: registrations.email" in str(exc).lower():
            raise DuplicateRegistrationError("This email is already registered.") from exc
        raise


def get_registrations(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    """Return registrations ordered newest first as a DataFrame."""
    with get_connection(db_path) as connection:
        return pd.read_sql_query(
            """SELECT id AS registration_id, student_name, email, college, channel,
                      referral_code, variant, registered_at, source
               FROM registrations ORDER BY registered_at DESC, id DESC""",
            connection,
        )


def get_referral_codes(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as connection:
        return pd.read_sql_query(
            "SELECT code, ambassador_label, created_at FROM referral_codes ORDER BY code", connection
        )


def create_referral_code(code: str, ambassador_label: str, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    normalized = code.strip().upper()
    if not normalized or not normalized.replace("-", "").isalnum():
        raise ValueError("Use letters, numbers, or hyphens for a referral code.")
    try:
        with get_connection(db_path) as connection:
            connection.execute(
                "INSERT INTO referral_codes(code, ambassador_label, created_at) VALUES (?, ?, ?)",
                (normalized, ambassador_label.strip() or normalized, datetime.now().astimezone().isoformat(timespec="seconds")),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError(f"Referral code {normalized} already exists.") from exc


def get_experiment_variants(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as connection:
        return pd.read_sql_query("SELECT * FROM experiment_variants ORDER BY variant", connection)


def update_experiment_variant(
    variant: str, people_reached: int, clicks: int, registrations: int, db_path: str | Path = DEFAULT_DB_PATH
) -> None:
    if min(people_reached, clicks, registrations) < 0:
        raise ValueError("Experiment values cannot be negative.")
    if clicks > people_reached:
        raise ValueError("Clicks cannot exceed people reached.")
    if registrations > clicks:
        raise ValueError("Registrations cannot exceed clicks.")
    with get_connection(db_path) as connection:
        cursor = connection.execute(
            """UPDATE experiment_variants SET people_reached = ?, clicks = ?, registrations = ?, is_simulated = 1
               WHERE variant = ?""",
            (people_reached, clicks, registrations, variant.strip().upper()),
        )
        if cursor.rowcount == 0:
            raise ValueError("Choose a known experiment variant.")


def get_campaign_plans(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    with get_connection(db_path) as connection:
        return pd.read_sql_query(
            "SELECT channel, registration_target, planned_budget, is_reserve FROM campaign_plans ORDER BY rowid",
            connection,
        )


def save_campaign_plans(plans: pd.DataFrame, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Validate and atomically replace editable campaign planning values."""
    required = {"channel", "registration_target", "planned_budget", "is_reserve"}
    if not required.issubset(plans.columns):
        raise ValueError("Campaign plan is missing required columns.")
    rows = []
    for row in plans.to_dict(orient="records"):
        reserve = row["is_reserve"]
        if pd.isna(reserve):
            reserve = False
        elif isinstance(reserve, str) or reserve not in (0, 1, False, True):
            raise ValueError("Reserve flags must be Boolean or 0/1 values.")
        else:
            reserve = bool(reserve)

        target_value = row["registration_target"]
        if reserve:
            target = None
        else:
            try:
                numeric_target = float(target_value)
            except (TypeError, ValueError):
                raise ValueError("Registration targets must be nonnegative integers.") from None
            if not math.isfinite(numeric_target) or numeric_target < 0 or not numeric_target.is_integer():
                raise ValueError("Registration targets must be nonnegative integers.")
            target = int(numeric_target)
        try:
            budget = float(row["planned_budget"])
        except (TypeError, ValueError):
            raise ValueError("Budgets must be nonnegative numbers.") from None
        if not math.isfinite(budget) or budget < 0:
            raise ValueError("Targets and budgets must be nonnegative.")
        rows.append((target, budget, row["channel"]))
    with get_connection(db_path) as connection:
        connection.executemany(
            "UPDATE campaign_plans SET registration_target = ?, planned_budget = ? WHERE channel = ?", rows
        )


def load_sample_registrations(csv_path: str | Path | None = None, db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Load synthetic CSV records idempotently; return the number inserted."""
    path = Path(csv_path) if csv_path else BASE_DIR / "sample_data" / "sample_registrations.csv"
    if not path.exists():
        raise FileNotFoundError(f"Synthetic sample file not found: {path}")
    inserted = 0
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            try:
                add_registration(
                    row["student_name"], row["email"], row["college"], row["channel"],
                    row.get("referral_code") or None, row.get("variant") or None,
                    row.get("registered_at") or None, source="sample", db_path=db_path,
                )
                inserted += 1
            except DuplicateRegistrationError:
                continue
    return inserted


def reset_sample_registrations(db_path: str | Path = DEFAULT_DB_PATH) -> int:
    """Delete only seeded sample rows, preserving manually added simulations."""
    with get_connection(db_path) as connection:
        cursor = connection.execute("DELETE FROM registrations WHERE source = 'sample'")
        return cursor.rowcount