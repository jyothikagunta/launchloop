import pandas as pd

import growth_metrics as metrics


def test_empty_and_zero_denominator_metrics():
    empty = pd.DataFrame()
    assert metrics.registration_total(empty) == 0
    assert metrics.percentage_of_target(0, 500) == 0
    assert metrics.remaining_registrations(12, 10) == 0
    assert metrics.click_through_rate(0, 0) == 0
    assert metrics.click_to_registration_rate(0, 0) == 0
    assert metrics.cost_per_registration(25, 0) is None


def test_channel_and_referral_metrics():
    registrations = pd.DataFrame({
        "channel": ["Clubs", "Clubs", None],
        "referral_code": ["CAMPUS01", "CAMPUS01", None],
    })
    codes = pd.DataFrame({"code": ["CAMPUS01", "CAMPUS02"], "ambassador_label": ["One", "Two"]})
    assert metrics.registrations_by_channel(registrations).set_index("channel")["registrations"]["Clubs"] == 2
    referral = metrics.referral_contribution(registrations, codes).set_index("code")
    assert referral.loc["CAMPUS01", "registrations"] == 2
    assert referral.loc["CAMPUS01", "contribution_pct"] == 66.67


def test_rates():
    assert metrics.click_through_rate(2, 10) == 20
    assert metrics.click_to_registration_rate(1, 2) == 50


def test_campaign_plan_totals_with_boolean_and_integer_reserve_flags():
    plans = pd.DataFrame({
        "registration_target": [200, 150, 100, 50, None],
        "planned_budget": [0, 0, 0, 1500, 500],
        "is_reserve": [False, 0, False, 0, 1],
    })
    assert metrics.campaign_plan_totals(plans) == (500, 2000.0, 500.0)


def test_campaign_plan_totals_empty_and_missing_values():
    assert metrics.campaign_plan_totals(pd.DataFrame()) == (0, 0.0, 0.0)
    plans = pd.DataFrame({
        "registration_target": [None, None],
        "planned_budget": [None, None],
        "is_reserve": [None, True],
    })
    assert metrics.campaign_plan_totals(plans) == (0, 0.0, 0.0)


def test_campaign_plan_totals_reject_invalid_targets_and_budgets():
    plans = pd.DataFrame({
        "registration_target": [1.5],
        "planned_budget": [0],
        "is_reserve": [False],
    })
    try:
        metrics.campaign_plan_totals(plans)
    except ValueError as exc:
        assert "nonnegative integers" in str(exc)
    else:
        raise AssertionError("Fractional targets should be rejected.")

    plans["registration_target"] = [1]
    plans["planned_budget"] = [float("inf")]
    try:
        metrics.campaign_plan_totals(plans)
    except ValueError as exc:
        assert "finite" in str(exc)
    else:
        raise AssertionError("Infinite budgets should be rejected.")


def test_registrations_by_day_filters_dates_and_ignores_invalid_timestamps():
    registrations = pd.DataFrame({
        "registered_at": ["2026-10-25T10:00:00+00:00", "2026-10-26T10:00:00+00:00", "not-a-date"],
    })
    result = metrics.registrations_by_day(registrations, "2026-10-26", "2026-10-26")
    assert result.to_dict(orient="records") == [{"day": pd.Timestamp("2026-10-26").date(), "registrations": 1}]