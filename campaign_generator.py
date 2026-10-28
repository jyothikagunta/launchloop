"""Template-based campaign copy generation with no external API dependency."""

from __future__ import annotations

import random

AUDIENCES = {
    "Final-year CSE students": "final-year computer science students",
    "AI/ML students": "students exploring AI and machine learning",
    "General engineering students": "engineering students curious about AI",
}
BENEFITS = {
    "Build your first AI project": "build your first AI project",
    "Learn practical AI skills": "explore practical AI skills",
    "Explore AI tools": "get familiar with useful AI tools",
}
PATTERNS = {
    "friendly": ["Curious about AI?", "Want to try something hands-on?", "A quick invite for your next learning session:"],
    "professional": ["You are invited to a free online workshop.", "Workshop invitation:", "Join a practical session designed for beginners."],
    "energetic": ["Ready to make something with AI?", "Your next hands-on hour starts here!", "Let's turn AI curiosity into a project."],
}


def generate_message(audience: str, channel: str, tone: str, benefit: str, call_to_action: str, seed: int | None = None) -> str:
    """Generate channel-specific copy from local templates."""
    rng = random.Random(seed)
    audience_text = AUDIENCES[audience]
    benefit_text = BENEFITS[benefit]
    opener = rng.choice(PATTERNS[tone.lower()])
    cta = call_to_action.strip() or "Save your spot"
    if channel == "Email":
        subject = f"Free AI workshop: {benefit_text.capitalize()} in 60 minutes"
        body = f"Hi {audience_text},\n\n{opener} Join our free online workshop, 'Build Your First AI Project in 60 Minutes.' You will have a focused session to {benefit_text}.\n\n{cta}: [REGISTRATION LINK]\n\nWe hope to see you there."
        return f"Subject: {subject}\n\n{body}"
    if channel == "WhatsApp":
        return f"{opener} Free online AI workshop for {audience_text}: 'Build Your First AI Project in 60 Minutes.' A chance to {benefit_text}. {cta}: [REGISTRATION LINK]"
    if channel == "College club announcement":
        return (f"FREE ONLINE WORKSHOP\nBuild Your First AI Project in 60 Minutes\n\nFor {audience_text}. {opener} Join the beginner-friendly session to {benefit_text}.\n\n{cta}: [REGISTRATION LINK]")
    return f"{opener}\n\n{audience_text}: join a free online workshop to {benefit_text} in 'Build Your First AI Project in 60 Minutes.'\n\n{cta}: [REGISTRATION LINK]"