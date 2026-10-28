import pandas as pd
import pytest

import database
import referral_manager


def test_initialize_and_registration_constraints(tmp_path):
    db_path = tmp_path / "test.db"
    database.initialize_database(db_path)
    database.initialize_database(db_path)
    assert len(database.get_referral_codes(db_path)) == 5
    registration_id = database.add_registration(
        "Demo Student", "demo@example.invalid", "Synthetic College", "Peer referrals",
        "campus01", db_path=db_path,
    )
    assert registration_id > 0
    with pytest.raises(database.DuplicateRegistrationError):
        database.add_registration("Other Demo", "DEMO@example.invalid", "Synthetic College", "Peer referrals", db_path=db_path)
    with pytest.raises(database.InvalidReferralCodeError):
        database.add_registration("Another Demo", "other@example.invalid", "Synthetic College", "Peer referrals", "INVALID", db_path=db_path)
    registrations = database.get_registrations(db_path)
    attributed = registrations[registrations["referral_code"] == "CAMPUS01"]
    assert len(attributed) == 1


def test_referral_code_validation_and_sample_idempotency(tmp_path):
    db_path = tmp_path / "test.db"
    database.initialize_database(db_path)
    assert referral_manager.validate_referral_code("campus05", db_path)
    assert not referral_manager.validate_referral_code("unknown", db_path)
    with pytest.raises(ValueError):
        referral_manager.create_code("bad code", "Test ambassador", db_path)
    referral_manager.create_code("CAMPUS-06", "Demo ambassador", db_path)
    with pytest.raises(ValueError, match="already exists"):
        referral_manager.create_code("campus-06", "Duplicate demo", db_path)
    first = database.load_sample_registrations(db_path=db_path)
    second = database.load_sample_registrations(db_path=db_path)
    assert first == 21
    assert second == 0
    assert len(database.get_registrations(db_path)) == 21
    assert database.reset_sample_registrations(db_path) == 21
    assert database.get_registrations(db_path).empty


def test_campaign_plan_persistence_and_spend(tmp_path):
    db_path = tmp_path / "test.db"
    database.initialize_database(db_path)
    plans = database.get_campaign_plans(db_path)
    assert plans["registration_target"].sum() == 500
    assert plans["planned_budget"].sum() == 2000
    database.save_simulated_spend(375, db_path)
    assert database.get_simulated_spend(db_path) == 375
    plans.loc[plans["channel"] == "Peer referrals", "registration_target"] = 99
    database.save_campaign_plans(plans, db_path)
    assert database.get_campaign_plans(db_path)["registration_target"].sum() == 499
    with pytest.raises(ValueError):
        database.save_campaign_plans(pd.DataFrame({"channel": ["Invalid"], "registration_target": [-1], "planned_budget": [0], "is_reserve": [False]}), db_path)
    plans.loc[plans["channel"] == "Peer referrals", "registration_target"] = 99.5
    with pytest.raises(ValueError, match="nonnegative integers"):
        database.save_campaign_plans(plans, db_path)


def test_experiment_metrics_validate_funnel_order(tmp_path):
    db_path = tmp_path / "test.db"
    database.initialize_database(db_path)
    database.update_experiment_variant("A", 100, 25, 5, db_path)
    variant = database.get_experiment_variants(db_path).set_index("variant").loc["A"]
    assert (variant["people_reached"], variant["clicks"], variant["registrations"]) == (100, 25, 5)
    with pytest.raises(ValueError, match="Clicks cannot exceed"):
        database.update_experiment_variant("A", 10, 11, 1, db_path)
    with pytest.raises(ValueError, match="Registrations cannot exceed"):
        database.update_experiment_variant("A", 10, 5, 6, db_path)