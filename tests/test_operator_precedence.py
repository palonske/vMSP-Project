"""
Tests for the operator precedence fix in path parameter validation.

The bug was:
    if not party_id == partner.party_id and country_code == partner.country_code:

Due to operator precedence, this evaluated as:
    (not (party_id == partner.party_id)) and (country_code == partner.country_code)

Which meant:
- If party_id matched but country_code didn't, no error was raised (WRONG!)
- Only if party_id didn't match AND country_code matched, an error was raised

The fix wraps the condition in parentheses:
    if not (party_id == partner.party_id and country_code == partner.country_code):

This correctly raises an error when EITHER field doesn't match.
"""

import pytest


class MockPartner:
    """Mock PartnerProfile for testing."""
    def __init__(self, party_id: str, country_code: str):
        self.party_id = party_id
        self.country_code = country_code


def check_path_params_old(party_id: str, country_code: str, partner: MockPartner) -> bool:
    """
    OLD (buggy) implementation.
    Returns True if validation passes (should proceed), False if should raise error.
    """
    # Bug: operator precedence causes this to evaluate incorrectly
    if not party_id == partner.party_id and country_code == partner.country_code:
        return False  # Would raise error
    return True  # Would proceed


def check_path_params_fixed(party_id: str, country_code: str, partner: MockPartner) -> bool:
    """
    FIXED implementation with proper parentheses.
    Returns True if validation passes (should proceed), False if should raise error.
    """
    if not (party_id == partner.party_id and country_code == partner.country_code):
        return False  # Would raise error
    return True  # Would proceed


class TestOperatorPrecedenceFix:
    """Test cases demonstrating the operator precedence bug and its fix."""

    @pytest.fixture
    def partner(self):
        """Create a mock partner with known credentials."""
        return MockPartner(party_id="ABC", country_code="US")

    def test_both_match_should_pass(self, partner):
        """When both party_id and country_code match, validation should pass."""
        # Both old and new should pass
        assert check_path_params_old("ABC", "US", partner) is True
        assert check_path_params_fixed("ABC", "US", partner) is True

    def test_neither_match_should_fail(self, partner):
        """When neither party_id nor country_code match, validation should fail."""
        # Old (buggy) would incorrectly pass, new should fail
        assert check_path_params_old("XYZ", "DE", partner) is True  # BUG!
        assert check_path_params_fixed("XYZ", "DE", partner) is False  # CORRECT

    def test_only_party_id_matches_should_fail(self, partner):
        """When only party_id matches (country_code wrong), validation should fail."""
        # Old (buggy) would incorrectly pass, new should fail
        assert check_path_params_old("ABC", "DE", partner) is True  # BUG!
        assert check_path_params_fixed("ABC", "DE", partner) is False  # CORRECT

    def test_only_country_code_matches_should_fail(self, partner):
        """When only country_code matches (party_id wrong), validation should fail."""
        # Both should fail (but for the wrong reason in old code)
        assert check_path_params_old("XYZ", "US", partner) is False
        assert check_path_params_fixed("XYZ", "US", partner) is False

    def test_bug_demonstration(self, partner):
        """
        This test explicitly demonstrates the bug:
        With the old code, an attacker could access another party's resources
        by using their own party_id but a wrong country_code.
        """
        attacker_party_id = "ABC"  # Matches partner's party_id
        wrong_country_code = "DE"   # Does NOT match partner's country_code

        # OLD CODE: Would allow the request (security vulnerability!)
        old_result = check_path_params_old(attacker_party_id, wrong_country_code, partner)
        assert old_result is True, "Bug: old code incorrectly allows mismatched country_code"

        # FIXED CODE: Correctly blocks the request
        fixed_result = check_path_params_fixed(attacker_party_id, wrong_country_code, partner)
        assert fixed_result is False, "Fixed code correctly blocks mismatched country_code"


class TestBooleanLogicExplanation:
    """
    Educational tests explaining why the bug occurred.

    Python operator precedence (relevant here):
    1. Comparison operators (==, !=, <, >, etc.)
    2. not
    3. and
    4. or

    So `not A and B` is parsed as `(not A) and B`, NOT as `not (A and B)`
    """

    def test_operator_precedence_demonstration(self):
        """Show how Python parses the buggy expression."""
        A = True  # party_id == partner.party_id
        B = False  # country_code == partner.country_code

        # How Python parses: not A and B
        buggy_parsing = (not A) and B  # = False and False = False

        # What we intended: not (A and B)
        intended_parsing = not (A and B)  # = not (True and False) = not False = True

        assert buggy_parsing != intended_parsing, "Parsing differs - this is the bug"

    def test_all_combinations(self):
        """Test all boolean combinations to show the difference."""
        results = []

        for A in [True, False]:  # party_id match
            for B in [True, False]:  # country_code match
                buggy = (not A) and B
                fixed = not (A and B)
                results.append({
                    'party_match': A,
                    'country_match': B,
                    'buggy_raises_error': buggy,
                    'fixed_raises_error': fixed,
                    'same_behavior': buggy == fixed
                })

        # Find cases where behavior differs
        different = [r for r in results if not r['same_behavior']]

        # There are TWO cases where behavior differs:
        # 1. party_match=True, country_match=False (old passes, new errors)
        # 2. party_match=False, country_match=False (old passes, new errors)
        assert len(different) == 2
        # Both cases have country_match=False
        assert all(d['country_match'] is False for d in different)
