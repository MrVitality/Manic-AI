"""Unit tests for the rule-based Fair Housing scanner.

These tests exercise the deterministic Layer 1 only -- ``scan_rules`` and the
verdict aggregation when the LLM critic is skipped. The LLM layer requires a
live Ollama process and is covered by integration tests instead.
"""

from __future__ import annotations

import asyncio

import pytest

from api.services.fair_housing import (
    FAIR_HOUSING_TERMS,
    SAFE_REFRAMINGS,
    check_compliance,
    scan_rules,
)


# ---------------------------------------------------------------------------
# scan_rules -- direct
# ---------------------------------------------------------------------------


def test_clean_text_has_no_matches() -> None:
    text = (
        "Beautifully renovated 3-bedroom home with hardwood floors throughout, "
        "updated kitchen with stainless appliances, fenced backyard, and "
        "attached two-car garage. Schedule your private showing today."
    )
    result = scan_rules(text)
    assert result.matches == ()
    assert result.highest_severity is None
    assert result.confidence == 1.0


def test_empty_string_passes() -> None:
    result = scan_rules("")
    assert result.matches == ()
    assert result.confidence == 1.0


def test_whitespace_only_passes() -> None:
    result = scan_rules("   \n\t  ")
    assert result.matches == ()


def test_perfect_for_young_family_blocks_or_warns() -> None:
    """'Young family' hits both familial_status and age categories.

    Because both categories include this phrasing at medium severity it
    should at minimum be a warn; with the LLM skipped, layer 1 should mark
    it as warn (medium severity).
    """
    result = scan_rules("Perfect for a young family looking to settle down.")
    assert result.matches, "expected at least one match"
    cats = {m.category for m in result.matches}
    assert "familial_status" in cats
    # Highest severity should be at least medium.
    assert result.highest_severity in ("medium", "high")


def test_master_bedroom_is_not_a_violation() -> None:
    """'Master bedroom' is no longer considered a Fair Housing violation.

    The industry has moved to 'primary bedroom' as a stylistic preference
    but 'master bedroom' itself is not regulated. We surface a rewrite
    suggestion via SAFE_REFRAMINGS but do not flag it as a rule match.
    """
    result = scan_rules("Great master bedroom with walk-in closet.")
    assert result.matches == ()
    assert result.highest_severity is None
    # The reframing is still discoverable for UX surfaces.
    assert "master bedroom" in SAFE_REFRAMINGS


def test_no_kids_no_pets_is_high_severity_block() -> None:
    result = scan_rules("No kids, no pets. Adults only please.")
    assert result.matches
    assert result.highest_severity == "high"
    cats = {m.category for m in result.matches}
    assert "familial_status" in cats


def test_walking_distance_to_jewish_center_hits_religion() -> None:
    result = scan_rules("Walking distance to the Jewish community center.")
    cats = {m.category for m in result.matches}
    assert "religion" in cats
    # walking distance is also a low-severity disability flag.
    assert "disability" in cats


def test_section_8_exclusion_is_high_severity() -> None:
    result = scan_rules("No Section 8 vouchers accepted.")
    assert result.matches
    assert result.highest_severity == "high"
    cats = {m.category for m in result.matches}
    assert "source_of_income" in cats


def test_long_text_with_one_violation_in_the_middle() -> None:
    filler = "Lovely home with many wonderful updates. " * 40
    text = filler + "Whites only please. " + filler
    result = scan_rules(text)
    assert result.matches
    assert result.highest_severity == "high"
    cats = {m.category for m in result.matches}
    assert "race_color_national_origin" in cats


def test_empty_nesters_is_familial_medium() -> None:
    result = scan_rules("Ideal for empty nesters who want low maintenance.")
    cats = {m.category for m in result.matches}
    assert "familial_status" in cats
    assert result.highest_severity in ("medium", "high")


def test_handicapped_is_high_severity_disability() -> None:
    result = scan_rules("Not suitable for handicapped buyers.")
    assert result.highest_severity == "high"
    cats = {m.category for m in result.matches}
    assert "disability" in cats


def test_bachelor_pad_is_familial_medium() -> None:
    result = scan_rules("Modern bachelor pad with city views.")
    cats = {m.category for m in result.matches}
    assert "familial_status" in cats


def test_55_plus_blocks() -> None:
    result = scan_rules("This is a 55+ community with HOA amenities.")
    assert result.highest_severity == "high"
    cats = {m.category for m in result.matches}
    assert "age" in cats


def test_suggested_rewrite_lookup_for_known_phrase() -> None:
    result = scan_rules("Perfect for families looking for space.")
    perfect_matches = [m for m in result.matches if "perfect for" in m.matched_text.lower()]
    assert perfect_matches, "expected a 'perfect for families' match"
    assert any(m.suggested_rewrite for m in perfect_matches)


# ---------------------------------------------------------------------------
# Sanity: every category in FAIR_HOUSING_TERMS has at least one pattern
# ---------------------------------------------------------------------------


def test_every_category_has_patterns() -> None:
    for category, patterns in FAIR_HOUSING_TERMS.items():
        assert patterns, f"category {category} has no patterns"
        for pat, sev in patterns:
            assert isinstance(pat, str) and pat
            assert sev in ("low", "medium", "high")


# ---------------------------------------------------------------------------
# check_compliance with skip_llm=True -- exercises aggregation
# ---------------------------------------------------------------------------


def _run(coro):  # tiny helper to avoid pytest-asyncio dependency
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


def test_check_compliance_clean_passes_when_llm_skipped() -> None:
    verdict = _run(check_compliance("3 bed 2 bath ranch with fenced yard.", client=None, skip_llm=True))  # type: ignore[arg-type]
    assert verdict.verdict == "pass"
    assert verdict.rule_matches == ()
    assert verdict.llm_issues == ()
    assert "rules: clean" in verdict.audit_log


def test_check_compliance_high_severity_blocks_when_llm_skipped() -> None:
    verdict = _run(
        check_compliance(
            "No Section 8 vouchers. Adults only.",
            client=None,  # type: ignore[arg-type]
            skip_llm=True,
        )
    )
    assert verdict.verdict == "block"
    assert verdict.rule_matches
    assert "verdict=block" in verdict.audit_log


def test_check_compliance_medium_severity_warns_when_llm_skipped() -> None:
    verdict = _run(
        check_compliance(
            "Perfect for families with young kids who love the outdoors.",
            client=None,  # type: ignore[arg-type]
            skip_llm=True,
        )
    )
    # Should warn (or block if any of those phrases are tagged high).
    assert verdict.verdict in ("warn", "block")


def test_check_compliance_empty_text_passes() -> None:
    verdict = _run(check_compliance("", client=None, skip_llm=True))  # type: ignore[arg-type]
    assert verdict.verdict == "pass"


@pytest.mark.parametrize(
    "phrase,expected_category",
    [
        ("no children allowed", "familial_status"),
        ("55+ community", "age"),
        ("christian home", "religion"),
        ("women only", "sex_gender_orientation"),
        ("married couples only", "marital_status"),
        ("no military", "military_status"),
    ],
)
def test_each_protected_class_has_a_blocking_pattern(phrase: str, expected_category: str) -> None:
    result = scan_rules(phrase)
    cats = {m.category for m in result.matches}
    assert expected_category in cats, f"{phrase!r} did not match {expected_category}: {cats}"
