"""Pure, reusable growth metric calculations."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


def registration_total(registrations: pd.DataFrame) -> int:
    return 0 if registrations is None else int(len(registrations))


def registrations_by_channel(registrations: pd.DataFrame) -> pd.DataFrame:
    if registrations is None or registrations.empty or "channel" not in registrations:
        return pd.DataFrame(columns=["channel", "registrations"])
    return (registrations["channel"].fillna("Unknown").replace("", "Unknown")
            .value_counts().rename_axis("channel").reset_index(name="registrations"))


def registrations_by_day(registrations: pd.DataFrame, start_date: Any = None, end_date: Any = None) -> pd.DataFrame:
    if registrations is None or registrations.empty or "registered_at" not in registrations:
        return pd.DataFrame(columns=["day", "registrations"])
    parsed = pd.to_datetime(registrations["registered_at"], errors="coerce", utc=True).dt.tz_convert(None)
    data = pd.DataFrame({"day": parsed.dt.date}).dropna()
    if start_date is not None:
        data = data[data["day"] >= pd.Timestamp(start_date).date()]
    if end_date is not None:
        data = data[data["day"] <= pd.Timestamp(end_date).date()]
    if data.empty:
        return pd.DataFrame(columns=["day", "registrations"])
    return data.groupby("day", as_index=False).size().rename(columns={"size": "registrations"})


def referral_contribution(registrations: pd.DataFrame, referral_codes: pd.DataFrame) -> pd.DataFrame:
    codes = referral_codes[["code", "ambassador_label"]].copy() if referral_codes is not None and not referral_codes.empty else pd.DataFrame(columns=["code", "ambassador_label"])
    if registrations is None or registrations.empty or "referral_code" not in registrations:
        codes["registrations"] = 0
    else:
        counts = registrations["referral_code"].dropna().astype(str).str.upper().value_counts()
        codes["registrations"] = codes["code"].str.upper().map(counts).fillna(0).astype(int)
    total = registration_total(registrations)
    codes["contribution_pct"] = (codes["registrations"] / total * 100).round(2) if total else 0.0
    return codes.sort_values(["registrations", "code"], ascending=[False, True]).reset_index(drop=True)


def percentage_of_target(total: int, target: int) -> float:
    return round(max(0, total) / target * 100, 2) if target > 0 else 0.0


def remaining_registrations(total: int, target: int) -> int:
    return max(0, target - total)


def click_through_rate(clicks: int, reach: int) -> float:
    return round(clicks / reach * 100, 2) if reach > 0 else 0.0


def click_to_registration_rate(registrations: int, clicks: int) -> float:
    return round(registrations / clicks * 100, 2) if clicks > 0 else 0.0


def cost_per_registration(spend: float, registrations: int) -> float | None:
    return round(spend / registrations, 2) if registrations > 0 else None


def campaign_plan_totals(plans: pd.DataFrame) -> tuple[int, float, float]:
    """Return registration target, total budget, and reserve budget safely."""
    if plans is None or plans.empty:
        return 0, 0.0, 0.0
    required = {"is_reserve", "registration_target", "planned_budget"}
    if not required.issubset(plans.columns):
        raise ValueError("Campaign plan is missing required columns.")

    def normalize_reserve(value: Any) -> bool:
        if pd.isna(value):
            return False
        if not isinstance(value, str) and value in (0, 1, False, True):
            return bool(value)
        raise ValueError("Reserve flags must be Boolean or 0/1 values.")

    reserve_mask = plans["is_reserve"].map(normalize_reserve).astype(bool)
    raw_targets = plans["registration_target"]
    raw_budgets = plans["planned_budget"]
    target_values = pd.to_numeric(raw_targets, errors="coerce")
    budget_values = pd.to_numeric(raw_budgets, errors="coerce")
    if (raw_targets.notna() & target_values.isna()).any():
        raise ValueError("Registration targets must be numeric integers.")
    if (raw_budgets.notna() & budget_values.isna()).any():
        raise ValueError("Budgets must be numeric values.")
    target_values = target_values.fillna(0)
    budget_values = budget_values.fillna(0)
    targets = target_values.loc[~reserve_mask]
    if any(not math.isfinite(float(value)) or value < 0 or not float(value).is_integer() for value in targets):
        raise ValueError("Registration targets must be nonnegative integers.")
    if any(not math.isfinite(float(value)) or value < 0 for value in budget_values):
        raise ValueError("Budgets must be nonnegative finite numbers.")
    total_target = int(targets.sum())
    total_budget = float(budget_values.sum())
    reserve_budget = float(budget_values.loc[reserve_mask].sum())
    return total_target, total_budget, reserve_budget