"""Tests for contact_sheets.py — numeric helpers, color parsing,
and choice validation."""

import contact_sheets as cs


# ── _safe_int ──────────────────────────────────────────────────

class TestSafeInt:
    def test_valid_int(self):
        assert cs._safe_int(42, 0) == 42

    def test_string_int(self):
        assert cs._safe_int("42", 0) == 42

    def test_float_string(self):
        assert cs._safe_int("42.9", 0) == 42

    def test_invalid_uses_default(self):
        assert cs._safe_int("abc", 99) == 99

    def test_none_uses_default(self):
        assert cs._safe_int(None, 99) == 99

    def test_clamps_to_min(self):
        assert cs._safe_int(-10, 0, min_value=0) == 0

    def test_clamps_to_max(self):
        assert cs._safe_int(999, 0, max_value=100) == 100

    def test_clamps_both(self):
        assert cs._safe_int(50, 0, min_value=10, max_value=40) == 40


# ── _safe_float ────────────────────────────────────────────────

class TestSafeFloat:
    def test_valid_float(self):
        assert cs._safe_float(3.14, 0.0) == 3.14

    def test_string_float(self):
        assert cs._safe_float("3.14", 0.0) == 3.14

    def test_int_string(self):
        assert cs._safe_float("42", 0.0) == 42.0

    def test_invalid_uses_default(self):
        assert cs._safe_float("abc", 99.0) == 99.0

    def test_none_uses_default(self):
        assert cs._safe_float(None, 99.0) == 99.0

    def test_clamps_to_min(self):
        assert cs._safe_float(-5.0, 0.0, min_value=0.0) == 0.0

    def test_clamps_to_max(self):
        assert cs._safe_float(200.0, 0.0, max_value=100.0) == 100.0


# ── _normalize_hex_color ───────────────────────────────────────

class TestNormalizeHexColor:
    def test_valid_hex_with_hash(self):
        assert cs._normalize_hex_color("#ff0000") == "#ff0000"

    def test_valid_hex_without_hash(self):
        result = cs._normalize_hex_color("ff0000")
        assert result.startswith("#")

    def test_empty_uses_default(self):
        assert cs._normalize_hex_color("") == "#00ff00"

    def test_none_uses_default(self):
        assert cs._normalize_hex_color(None) == "#00ff00"

    def test_invalid_uses_default(self):
        assert cs._normalize_hex_color("not-a-color") == "#00ff00"


# ── _hex_to_rgb ────────────────────────────────────────────────

class TestHexToRgb:
    def test_red(self):
        assert cs._hex_to_rgb("#ff0000") == (255, 0, 0)

    def test_green(self):
        assert cs._hex_to_rgb("#00ff00") == (0, 255, 0)

    def test_blue(self):
        assert cs._hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_white(self):
        assert cs._hex_to_rgb("#ffffff") == (255, 255, 255)

    def test_black(self):
        assert cs._hex_to_rgb("#000000") == (0, 0, 0)


# ── _localized_choice ──────────────────────────────────────────

class TestLocalizedChoice:
    def test_returns_tuple(self):
        result = cs._localized_choice("Label", "value")
        assert isinstance(result, tuple)

    def test_label_first(self):
        result = cs._localized_choice("Label", "value")
        assert result[0] == "Label"

    def test_value_second(self):
        result = cs._localized_choice("Label", "value")
        assert result[1] == "value"


# ── _valid_choice_value ────────────────────────────────────────

class TestValidChoiceValue:
    def test_valid_value(self):
        assert cs._valid_choice_value("a", ["a", "b", "c"], "a") == "a"

    def test_invalid_uses_default(self):
        assert cs._valid_choice_value("z", ["a", "b", "c"], "a") == "a"

    def test_none_uses_default(self):
        assert cs._valid_choice_value(None, ["a", "b", "c"], "b") == "b"

    def test_empty_uses_default(self):
        assert cs._valid_choice_value("", ["a", "b", "c"], "c") == "c"


# ── CONTACT_SHEET_DEFAULTS ─────────────────────────────────────

class TestContactSheetDefaults:
    def test_has_expected_keys(self):
        expected = {"output_width", "images_per_row", "spacing", "margin",
                     "background", "export_format", "quality"}
        assert expected.issubset(cs.CONTACT_SHEET_DEFAULTS.keys())

    def test_quality_in_valid_range(self):
        assert 1 <= cs.CONTACT_SHEET_DEFAULTS["quality"] <= 100

    def test_background_starts_with_hash(self):
        assert cs.CONTACT_SHEET_DEFAULTS["background"].startswith("#")