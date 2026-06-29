"""Tests for pure dataset helpers in lora_manager.py — sorting, tag
extraction, caption parsing, and keyword validation."""

import lora_manager as lm


# ── natural_sort_key ───────────────────────────────────────────

class TestNaturalSortKey:
    def test_natural_order(self):
        items = ["img10", "img2", "img1"]
        sorted_items = sorted(items, key=lm.natural_sort_key)
        assert sorted_items == ["img1", "img2", "img10"]

    def test_case_insensitive(self):
        assert lm.natural_sort_key("IMG2") == lm.natural_sort_key("img2")

    def test_mixed_alpha_numeric(self):
        items = ["file20.txt", "file3.txt", "file100.txt"]
        sorted_items = sorted(items, key=lm.natural_sort_key)
        assert sorted_items == ["file3.txt", "file20.txt", "file100.txt"]

    def test_non_string_input(self):
        key = lm.natural_sort_key(123)
        assert isinstance(key, list)

    def test_empty_string(self):
        key = lm.natural_sort_key("")
        assert isinstance(key, list)


# ── extract_all_tags ───────────────────────────────────────────

class TestExtractAllTags:
    def test_basic_extraction(self):
        dataset = [
            {"caption": "red hair, blue eyes"},
            {"caption": "blue eyes, smile"},
        ]
        result = lm.extract_all_tags(dataset)
        tags = result.split("|")
        assert "red hair" in tags
        assert "blue eyes" in tags
        assert "smile" in tags

    def test_deduplication(self):
        dataset = [
            {"caption": "cat, dog"},
            {"caption": "cat, bird"},
        ]
        result = lm.extract_all_tags(dataset)
        tags = result.split("|")
        assert tags.count("cat") == 1

    def test_sorted_alphabetically(self):
        dataset = [{"caption": "zebra, apple, mango"}]
        tags = lm.extract_all_tags(dataset).split("|")
        assert tags == sorted(tags)

    def test_empty_dataset(self):
        assert lm.extract_all_tags([]) == ""

    def test_strips_whitespace(self):
        dataset = [{"caption": "  spaced  ,  trimmed  "}]
        tags = lm.extract_all_tags(dataset).split("|")
        assert "spaced" in tags
        assert "trimmed" in tags


# ── _caption_tags ──────────────────────────────────────────────

class TestCaptionTags:
    def test_basic_split(self):
        assert lm._caption_tags("a, b, c") == ["a", "b", "c"]

    def test_strips_quotes(self):
        assert lm._caption_tags('"quoted", "normal"') == ["quoted", "normal"]

    def test_empty_string(self):
        assert lm._caption_tags("") == []

    def test_none(self):
        assert lm._caption_tags(None) == []

    def test_whitespace_only_entries_removed(self):
        assert lm._caption_tags("a,  , b") == ["a", "b"]

    def test_strips_extra_whitespace(self):
        assert lm._caption_tags("a   b,  c  ") == ["a b", "c"]


# ── _is_valid_keyword ──────────────────────────────────────────

class TestIsValidKeyword:
    def test_valid_short_tag(self):
        assert lm._is_valid_keyword("blue hair") is True

    def test_empty(self):
        assert lm._is_valid_keyword("") is False

    def test_single_char(self):
        assert lm._is_valid_keyword("x") is False

    def test_too_many_words(self):
        assert lm._is_valid_keyword("one two three four five six seven") is False

    def test_too_long(self):
        assert lm._is_valid_keyword("a" * 51) is False

    def test_phrase_hint_english(self):
        assert lm._is_valid_keyword("the image shows a girl") is False

    def test_phrase_hint_french(self):
        assert lm._is_valid_keyword("il y a un chat") is False

    def test_ends_with_period(self):
        assert lm._is_valid_keyword("a cat.") is False

    def test_valid_concept(self):
        assert lm._is_valid_keyword("pup play mask") is True


# ── _looks_like_trigger ────────────────────────────────────────

class TestLooksLikeTrigger:
    def test_alphanumeric_trigger(self):
        assert lm._looks_like_trigger("D4lle") is True

    def test_underscore_trigger(self):
        assert lm._looks_like_trigger("my_character") is True

    def test_pure_word_no(self):
        assert lm._looks_like_trigger("blonde") is False

    def test_has_space(self):
        assert lm._looks_like_trigger("two words") is False

    def test_too_short(self):
        assert lm._looks_like_trigger("ab") is False

    def test_empty(self):
        assert lm._looks_like_trigger("") is False

    def test_number_letter(self):
        assert lm._looks_like_trigger("3dge") is True


# ── _normalize_tag_for_dedup ───────────────────────────────────

class TestNormalizeTagForDedup:
    def test_lowercase(self):
        assert lm._normalize_tag_for_dedup("HELLO") == "hello"

    def test_strip_punctuation(self):
        assert lm._normalize_tag_for_dedup("dal-l-e") == "dalle"

    def test_leetspeak(self):
        assert lm._normalize_tag_for_dedup("d4lle") == "dalle"

    def test_plural_es(self):
        assert lm._normalize_tag_for_dedup("buses") == "bus"

    def test_plural_ies(self):
        assert lm._normalize_tag_for_dedup("berries") == "berry"

    def test_plural_s(self):
        assert lm._normalize_tag_for_dedup("cats") == "cat"

    def test_double_ss_not_stripped(self):
        assert lm._normalize_tag_for_dedup("glass") == "glass"


# ── _are_orthographic_variants ─────────────────────────────────

class TestAreOrthographicVariants:
    def test_identical_after_normalization(self):
        assert lm._are_orthographic_variants("D4lle", "Dall-e") is True

    def test_completely_different(self):
        assert lm._are_orthographic_variants("cat", "elephant") is False

    def test_empty(self):
        assert lm._are_orthographic_variants("", "test") is False

    def test_same_word(self):
        assert lm._are_orthographic_variants("hello", "Hello") is True


# ── _deduplicate_recipe ────────────────────────────────────────

class TestDeduplicateRecipe:
    def test_empty(self):
        assert lm._deduplicate_recipe([]) == []

    def test_exact_duplicates(self):
        result = lm._deduplicate_recipe(["cat", "cat", "cat"])
        assert result == ["cat"]

    def test_case_insensitive_dedup(self):
        result = lm._deduplicate_recipe(["Cat", "cat"])
        assert len(result) == 1

    def test_orthographic_variants_merged(self):
        result = lm._deduplicate_recipe(["D4lle", "Dall-e"])
        assert len(result) == 1

    def test_unrelated_tags_kept(self):
        result = lm._deduplicate_recipe(["cat", "dog", "bird"])
        assert len(result) == 3

    def test_freq_lookup_prefers_frequent(self):
        result = lm._deduplicate_recipe(
            ["rare", "frequent"],
            freq_lookup={"rare": 1, "frequent": 10}
        )
        assert "frequent" in result


# ── _safe_folder_name ──────────────────────────────────────────

class TestSafeFolderName:
    def test_strips_invalid_chars(self):
        assert lm._safe_folder_name('file<>:name') == "file_name"

    def test_collapses_spaces(self):
        assert lm._safe_folder_name("multi   space") == "multi space"

    def test_strips_trailing_dots(self):
        result = lm._safe_folder_name("folder...")
        assert not result.endswith(".")

    def test_empty_returns_dataset(self):
        assert lm._safe_folder_name("") == "dataset"

    def test_none_returns_dataset(self):
        assert lm._safe_folder_name(None) == "dataset"


# ── _format_export_suffix ──────────────────────────────────────

class TestFormatExportSuffix:
    def test_placeholder_pattern(self):
        assert lm._format_export_suffix("-v{n}", 3) == "-v3"

    def test_x_pattern(self):
        result = lm._format_export_suffix("-Sx", 2)
        assert "2" in result
        assert "S" in result

    def test_empty_defaults(self):
        result = lm._format_export_suffix("", 1)
        assert "1" in result

    def test_none_defaults(self):
        result = lm._format_export_suffix(None, 1)
        assert "1" in result

    def test_no_placeholder_no_x(self):
        result = lm._format_export_suffix("-final", 5)
        assert result == "-final5"