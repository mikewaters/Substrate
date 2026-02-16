"""Tests for catalog.search.intent module."""

import pytest

from catalog.search.intent import classify_intent


class TestClassifyIntent:
    """Tests for the rule-based intent classifier."""

    def test_quoted_double_navigational(self) -> None:
        """Double-quoted query is navigational."""
        assert classify_intent('"Project Plan Q4"') == "navigational"

    def test_quoted_single_navigational(self) -> None:
        """Single-quoted query is navigational."""
        assert classify_intent("'Meeting Notes'") == "navigational"

    def test_jira_style_navigational(self) -> None:
        """JIRA-style identifier is navigational."""
        assert classify_intent("PROJ-1234") == "navigational"

    def test_jira_style_with_text(self) -> None:
        """JIRA-style within short query is navigational."""
        assert classify_intent("fix PROJ-456") == "navigational"

    def test_camelcase_navigational(self) -> None:
        """CamelCase short query is navigational."""
        assert classify_intent("MyDocument") == "navigational"

    def test_camelcase_two_tokens(self) -> None:
        """CamelCase in 2-token query is navigational."""
        assert classify_intent("find MyProject") == "navigational"

    def test_all_caps_short_navigational(self) -> None:
        """ALL_CAPS short token is navigational."""
        assert classify_intent("README") == "navigational"

    def test_all_caps_two_letter(self) -> None:
        """Two-letter ALL_CAPS is navigational."""
        assert classify_intent("AI") == "navigational"

    def test_single_letter_caps_not_navigational(self) -> None:
        """Single letter uppercase is too short to be navigational ALL_CAPS."""
        # len("A") < 2, so not ALL_CAPS navigational; falls through to informational
        assert classify_intent("A") == "informational"

    def test_path_like_navigational(self) -> None:
        """Path-like patterns are navigational."""
        assert classify_intent("src/components/Button.tsx") == "navigational"

    def test_file_extension_navigational(self) -> None:
        """File extension patterns are navigational."""
        assert classify_intent("config.yaml") == "navigational"
        assert classify_intent("notes.md") == "navigational"
        assert classify_intent("script.py") == "navigational"

    def test_long_lowercase_informational(self) -> None:
        """Long lowercase query is informational."""
        assert classify_intent("how does async work in python") == "informational"

    def test_medium_query_informational(self) -> None:
        """4+ token lowercase query is informational."""
        assert classify_intent("best practices for testing") == "informational"

    def test_question_informational(self) -> None:
        """Natural language question is informational."""
        assert classify_intent("what is retrieval augmented generation") == "informational"

    def test_long_with_caps_informational(self) -> None:
        """Long query with caps tokens is still informational (>3 tokens)."""
        assert classify_intent("how to use the ChatGPT API effectively") == "informational"

    def test_empty_string_informational(self) -> None:
        """Empty string returns informational."""
        assert classify_intent("") == "informational"

    def test_whitespace_only_informational(self) -> None:
        """Whitespace-only returns informational."""
        assert classify_intent("   ") == "informational"

    def test_three_lowercase_tokens_informational(self) -> None:
        """Three lowercase tokens without special patterns is informational."""
        assert classify_intent("machine learning basics") == "informational"

    def test_backslash_path_navigational(self) -> None:
        """Windows-style backslash path is navigational."""
        assert classify_intent("docs\\readme.txt") == "navigational"
