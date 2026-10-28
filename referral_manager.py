"""Referral-code workflows kept separate from the Streamlit interface."""

from __future__ import annotations

import re

import database


def normalize_referral_code(code: str) -> str:
    normalized = code.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]+(?:-[A-Z0-9]+)*", normalized):
        raise ValueError("Use letters, numbers, or single hyphens for a referral code.")
    return normalized


def validate_referral_code(code: str, db_path=database.DEFAULT_DB_PATH) -> bool:
    normalized = normalize_referral_code(code)
    codes = database.get_referral_codes(db_path)
    return normalized in codes["code"].str.upper().tolist()


def create_code(code: str, ambassador_label: str, db_path=database.DEFAULT_DB_PATH) -> None:
    database.create_referral_code(normalize_referral_code(code), ambassador_label, db_path)