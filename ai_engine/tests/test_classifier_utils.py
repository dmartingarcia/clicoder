"""
Tests for pure utility functions in classifier.py and baseline_dict.py.
No model weights or spaCy needed — only tests deterministic logic.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── Add ai_engine root to import path ────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from baseline_dict import DictClassifier, _strip_accents, build_pattern

from classifier import _extract_chapter, load_code_descriptions

# =============================================================================
# _extract_chapter
# =============================================================================


class TestExtractChapter:
    def test_uppercase_letter(self):
        assert _extract_chapter("I10") == "IX"

    def test_lowercase_letter_is_normalised(self):
        assert _extract_chapter("i10") == "IX"

    def test_j_codes(self):
        assert _extract_chapter("J45.0") == "X"

    def test_e_codes(self):
        assert _extract_chapter("E11") == "IV"

    def test_z_codes(self):
        assert _extract_chapter("Z00") == "XXI"

    def test_s_and_t_both_map_to_xix(self):
        assert _extract_chapter("S72.0") == "XIX"
        assert _extract_chapter("T14.0") == "XIX"

    def test_v_w_x_y_map_to_xx(self):
        for letter in ("V", "W", "X", "Y"):
            assert _extract_chapter(f"{letter}01") == "XX"

    def test_unknown_letter_returns_none(self):
        assert _extract_chapter("U999") is None

    def test_empty_string_returns_none(self):
        assert _extract_chapter("") is None


# =============================================================================
# load_code_descriptions
# =============================================================================


class TestLoadCodeDescriptions:
    def test_loads_valid_json(self, tmp_path):
        data = {"I10": "Hipertensión esencial", "J45.0": "Asma alérgica"}
        (tmp_path / "code_descriptions.json").write_text(json.dumps(data), encoding="utf-8")

        result = load_code_descriptions(str(tmp_path))
        assert result["I10"] == "Hipertensión esencial"
        assert result["J45.0"] == "Asma alérgica"

    def test_returns_empty_dict_when_file_missing(self, tmp_path):
        result = load_code_descriptions(str(tmp_path))
        assert result == {}

    def test_returns_empty_dict_on_invalid_json(self, tmp_path):
        (tmp_path / "code_descriptions.json").write_text("not valid json", encoding="utf-8")
        result = load_code_descriptions(str(tmp_path))
        assert result == {}


# =============================================================================
# _strip_accents
# =============================================================================


class TestStripAccents:
    def test_removes_tilde(self):
        assert _strip_accents("hipertensión") == "hipertension"

    def test_removes_acute_accent(self):
        assert _strip_accents("cardíaca") == "cardiaca"

    def test_leaves_plain_text_unchanged(self):
        assert _strip_accents("diabetes") == "diabetes"

    def test_handles_uppercase_accented(self):
        assert _strip_accents("Ángel") == "Angel"

    def test_empty_string(self):
        assert _strip_accents("") == ""


# =============================================================================
# build_pattern
# =============================================================================


class TestBuildPattern:
    def test_matches_whole_word(self):
        pat = build_pattern("hipertension")
        assert pat.search("paciente con hipertension severa")

    def test_does_not_match_substring(self):
        pat = build_pattern("hiper")
        assert not pat.search("hipertension")

    def test_case_sensitive_by_default(self):
        pat = build_pattern("asma")
        assert not pat.search("ASMA")

    def test_returns_compiled_pattern(self):
        pat = build_pattern("diabetes")
        assert hasattr(pat, "search")

    def test_escapes_special_chars(self):
        pat = build_pattern("i10.0")
        # The dot is escaped so it doesn't match 'i10X0'
        assert not pat.search("i10X0")


# =============================================================================
# DictClassifier
# =============================================================================


class TestDictClassifier:
    @pytest.fixture
    def patterns_file(self, tmp_path):
        """A minimal patterns JSON: I10 → 'hipertension', J45 → 'asma'."""
        data = {
            "I10": ["hipertension", "tension arterial alta"],
            "J45": ["asma", "broncoespasmo"],
        }
        p = tmp_path / "patterns.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return str(p)

    @pytest.fixture
    def clf(self, patterns_file):
        return DictClassifier(patterns_file)

    def test_loads_patterns(self, clf):
        assert "I10" in clf._patterns
        assert "J45" in clf._patterns

    def test_predict_returns_match(self, clf):
        # Patch lemmatize to return the text unchanged (avoids spaCy dependency)
        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("paciente con hipertension severa")

        codes = [r["code"] for r in results]
        assert "I10" in codes

    def test_predict_no_match_returns_empty(self, clf):
        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("fractura de femur")

        assert results == []

    def test_predict_confidence_is_1(self, clf):
        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("asma bronquial severa")

        assert all(r["confidence"] == 1.0 for r in results)

    def test_predict_includes_matched_terms(self, clf):
        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("asma y broncoespasmo")

        j45 = next(r for r in results if r["code"] == "J45")
        assert len(j45["matched_terms"]) >= 1
        assert all(t in ["asma", "broncoespasmo"] for t in j45["matched_terms"])

    def test_predict_limits_matched_terms_to_3(self, tmp_path):
        data = {"X99": ["uno", "dos", "tres", "cuatro", "cinco"]}
        p = tmp_path / "big.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        clf = DictClassifier(str(p))

        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("uno dos tres cuatro cinco")

        assert len(results[0]["matched_terms"]) <= 3

    def test_predict_results_sorted_by_code(self, clf):
        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("hipertension y asma")

        codes = [r["code"] for r in results]
        assert codes == sorted(codes)

    def test_predict_multiple_codes(self, clf):
        with patch("baseline_dict.lemmatize", side_effect=lambda t: t.lower()):
            results = clf.predict("hipertension y asma")

        codes = [r["code"] for r in results]
        assert "I10" in codes
        assert "J45" in codes
