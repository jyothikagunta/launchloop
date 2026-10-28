import pytest

import campaign_generator


@pytest.mark.parametrize("audience", campaign_generator.AUDIENCES)
@pytest.mark.parametrize("channel", ["WhatsApp", "Email", "College club announcement", "Social media"])
@pytest.mark.parametrize("tone", ["Friendly", "Professional", "Energetic"])
@pytest.mark.parametrize("benefit", campaign_generator.BENEFITS)
def test_message_options_use_local_copy_and_safe_registration_placeholder(audience, channel, tone, benefit):
    message = campaign_generator.generate_message(
        audience, channel, tone, benefit, "Register for the workshop", seed=10
    )
    assert "Register for the workshop" in message
    assert "[REGISTRATION LINK]" in message
    assert "http://" not in message and "https://" not in message
    assert "placement guaranteed" not in message.lower()
    if channel == "Email":
        assert message.startswith("Subject:")