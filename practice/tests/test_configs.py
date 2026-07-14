"""Tests for config loading and load-time validation of fingering forms.

Forms are hand-authored TABs in the fixed example key A (root = low E
fret 5); the loader is the validator, so broken-TAB cases here are the
guard against typos in hand-authored configs.
"""

import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase

from practice import theory

# A known-good CAGED fingering config used as the base for broken variants
# (the classic A minor pentatonic box 1).
VALID_FORM = {
    "id": "test-form",
    "scale": "minor_pentatonic",
    "name": "Test Form",
    "caged_shape": "E",
    "anchor": "root_low_e",
    "example_key": "A",
    "tab": {
        "E": [5, 8], "A": [5, 7], "D": [5, 7],
        "G": [5, 7], "B": [5, 8], "e": [5, 8],
    },
}

# A known-good scale-category config (major scale 2nd finger form).
VALID_SCALE_FORM = {
    "id": "test-scale-form",
    "scale": "major_scale",
    "name": "Test Scale Form",
    "starting_finger": 2,
    "anchor": "root_low_e",
    "example_key": "A",
    "tab": {
        "E": [5, 7], "A": [4, 5, 7], "D": [4, 6, 7],
        "G": [4, 6, 7], "B": [5, 7], "e": [4, 5, 7],
    },
}

# A known-good arpeggio config with 1-note strings (A major arpeggio,
# E shape).
VALID_ARPEGGIO_FORM = {
    "id": "test-arpeggio-form",
    "scale": "major_arpeggio",
    "name": "Test Arpeggio Form",
    "caged_shape": "E",
    "anchor": "root_low_e",
    "example_key": "A",
    "tab": {
        "E": [5], "A": [4, 7], "D": [7], "G": [6], "B": [5], "e": [5],
    },
}

# Shipped configs: the E-string-root major-scale finger forms (hand-authored
# TABs; A-string-root variants are planned, hence the e-root in the naming).
EXPECTED_FORM_COUNTS = {"scale": 3}
EXPECTED_FORM_IDS = {
    "major-scale-e-root-1st-finger-form",
    "major-scale-e-root-2nd-finger-form",
    "major-scale-e-root-4th-finger-form",
}


def write_forms(dirname, *forms):
    """Write each form dict as its own YAML file in dirname."""
    for i, form in enumerate(forms):
        path = Path(dirname) / f"form_{i}.yaml"
        with open(path, "w") as fh:
            yaml.safe_dump(form, fh)


def load_temp(*forms):
    with tempfile.TemporaryDirectory() as tmp:
        write_forms(tmp, *forms)
        return theory.load_fingerings(tmp)


class ShippedConfigTests(SimpleTestCase):
    def test_3_configs_load_and_validate(self):
        fingerings = theory.load_fingerings()
        self.assertEqual(len(fingerings), 3)

    def test_count_by_category(self):
        """Only the 3 E-root major-scale finger forms ship."""
        counts = {}
        for form in theory.load_fingerings().values():
            counts[form["category"]] = counts.get(form["category"], 0) + 1
        self.assertEqual(counts, EXPECTED_FORM_COUNTS)

    def test_exact_id_set(self):
        self.assertEqual(set(theory.load_fingerings()), EXPECTED_FORM_IDS)

    def test_shipped_forms_reference_known_scales(self):
        scales = theory.load_scales()
        for form in theory.load_fingerings().values():
            self.assertIn(form["scale"], scales)

    def test_five_shapes_per_caged_scale_three_forms_per_scale(self):
        by_scale = {}
        for form in theory.load_fingerings().values():
            by_scale.setdefault(form["scale"], []).append(form)
        for scale_id, forms in by_scale.items():
            category = forms[0]["category"]
            if category in ("pentatonic", "arpeggio"):
                self.assertEqual(
                    sorted(f["caged_shape"] for f in forms),
                    ["A", "C", "D", "E", "G"], scale_id)
            else:
                self.assertEqual(
                    sorted(f["starting_finger"] for f in forms),
                    [1, 2, 4], scale_id)

    def test_shipped_form_fields_and_labels(self):
        """caged_shape XOR starting_finger; display_label per category;
        TAB in the fixed example key with derived offsets."""
        for form in theory.load_fingerings().values():
            self.assertIsInstance(form["name"], str)
            self.assertEqual(form["anchor"], "root_low_e")
            self.assertEqual(form["example_key"], theory.EXAMPLE_KEY)
            self.assertEqual(set(form["tab"]), set(theory.TAB_STRINGS))
            self.assertEqual(set(form["offsets"]), {1, 2, 3, 4, 5, 6})
            self.assertIn(form["category"], theory.CATEGORIES)
            if form["category"] in ("pentatonic", "arpeggio"):
                self.assertIn(form["caged_shape"], theory.CAGED_SHAPES)
                self.assertIsNone(form["starting_finger"])
                self.assertEqual(form["display_label"],
                                 f"{form['caged_shape']} Shape")
            else:
                self.assertIsNone(form["caged_shape"])
                self.assertIn(form["starting_finger"], (1, 2, 3, 4))
                self.assertEqual(
                    form["display_label"],
                    f"{theory.ordinal(form['starting_finger'])} Finger Form",
                )

    def test_offsets_derived_from_tab(self):
        """offset = authored fret - example-key anchor fret (A -> 5)."""
        for form in theory.load_fingerings().values():
            for label, string in theory.TAB_STRINGS.items():
                self.assertEqual(
                    form["offsets"][string],
                    [f - 5 for f in form["tab"][label]],
                )

    def test_display_labels_literal_examples(self):
        fingerings = theory.load_fingerings()
        self.assertEqual(
            fingerings["major-scale-e-root-1st-finger-form"]["display_label"],
            "1st Finger Form")
        self.assertEqual(
            fingerings["major-scale-e-root-2nd-finger-form"]["display_label"],
            "2nd Finger Form")
        self.assertEqual(
            fingerings["major-scale-e-root-4th-finger-form"]["display_label"],
            "4th Finger Form")


class ValidTempConfigTests(SimpleTestCase):
    """Sanity checks: the base fixtures themselves are valid."""

    def test_valid_caged_config_loads(self):
        fingerings = load_temp(VALID_FORM)
        form = fingerings["test-form"]
        self.assertEqual(form["tab"]["E"], [5, 8])
        self.assertEqual(form["offsets"][6], [0, 3])
        self.assertEqual(form["category"], "pentatonic")
        self.assertEqual(form["caged_shape"], "E")
        self.assertIsNone(form["starting_finger"])
        self.assertEqual(form["display_label"], "E Shape")

    def test_valid_scale_config_loads(self):
        fingerings = load_temp(VALID_SCALE_FORM)
        form = fingerings["test-scale-form"]
        self.assertEqual(form["category"], "scale")
        self.assertIsNone(form["caged_shape"])
        self.assertEqual(form["starting_finger"], 2)
        self.assertEqual(form["display_label"], "2nd Finger Form")
        self.assertEqual(form["offsets"][5], [-1, 0, 2])

    def test_valid_arpeggio_config_with_1_note_strings_loads(self):
        fingerings = load_temp(VALID_ARPEGGIO_FORM)
        form = fingerings["test-arpeggio-form"]
        self.assertEqual(form["category"], "arpeggio")
        self.assertEqual(form["tab"]["E"], [5])
        self.assertEqual(form["tab"]["D"], [7])


class BrokenConfigTests(SimpleTestCase):
    """Deliberately broken configs must raise clear ConfigErrors."""

    def load_broken(self, *forms):
        with tempfile.TemporaryDirectory() as tmp:
            write_forms(tmp, *forms)
            theory.load_fingerings(tmp)  # expected to raise

    def test_out_of_scale_fret_rejected(self):
        # Fret 6 on the D string is G#, not in A minor pentatonic.
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "D": [5, 6]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("string D", msg)
        self.assertIn("fret 6", msg)
        self.assertIn("form_0.yaml", msg)

    def test_incomplete_form_rejected_naming_missing_interval(self):
        # Remove every note carrying interval 10 (b7, the note G) from the
        # minor pent box: D string fret 5 and B string fret 8.
        bad = {**VALID_FORM,
               "tab": {**VALID_FORM["tab"], "D": [7], "B": [5]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("incomplete", msg)
        self.assertIn("10", msg)
        self.assertIn("minor_pentatonic", msg)

    def test_incomplete_scale_form_rejected(self):
        # Remove every note carrying interval 11 (the major 7th, G#) from
        # the major-scale form: D string fret 6 and e string fret 4. All
        # strings keep >= 1 note, so only completeness fails.
        bad = {**VALID_SCALE_FORM,
               "tab": {**VALID_SCALE_FORM["tab"], "D": [4, 7], "e": [5, 7]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("incomplete", msg)
        self.assertIn("11", msg)

    def test_fret_zero_rejected(self):
        """Open strings don't transpose; frets must be >= 1."""
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "A": [0, 5, 7]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn(">= 1", str(ctx.exception))

    def test_note_below_low_root_rejected(self):
        """'Start on the root': low-E fret 3 (G) sounds below the root A."""
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": [3, 5, 8]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("below the low root", msg)
        self.assertIn("fret 3", msg)

    def test_root_missing_from_low_e_rejected(self):
        """The low-E root (fret 5 in A) must be in the TAB."""
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": [8]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("root", str(ctx.exception))
        self.assertIn("string E", str(ctx.exception))

    def test_wrong_example_key_rejected(self):
        for bad_key in ("C", "a", "", None, 5):
            with self.subTest(example_key=bad_key):
                with self.assertRaises(theory.ConfigError) as ctx:
                    self.load_broken({**VALID_FORM, "example_key": bad_key})
                self.assertIn("example_key", str(ctx.exception))

    def test_legacy_offsets_schema_rejected_with_hint(self):
        legacy = {k: v for k, v in VALID_FORM.items() if k != "tab"}
        legacy["offsets"] = {
            6: [0, 3], 5: [0, 2], 4: [0, 2], 3: [0, 2], 2: [0, 3], 1: [0, 3],
        }
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(legacy)
        msg = str(ctx.exception)
        self.assertIn("legacy", msg)
        self.assertIn("tab", msg)

    def test_caged_shape_missing_for_pentatonic_rejected(self):
        form = dict(VALID_FORM)
        del form["caged_shape"]
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(form)
        self.assertIn("caged_shape", str(ctx.exception))

    def test_caged_shape_invalid_letter_rejected(self):
        for bad_shape in ("X", "e", "", 5, None):
            with self.subTest(shape=bad_shape):
                with self.assertRaises(theory.ConfigError):
                    self.load_broken({**VALID_FORM, "caged_shape": bad_shape})

    def test_starting_finger_forbidden_for_pentatonic_rejected(self):
        bad = {**VALID_FORM, "starting_finger": 1}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("starting_finger", str(ctx.exception))
        self.assertIn("forbidden", str(ctx.exception))

    def test_starting_finger_missing_for_scale_rejected(self):
        form = dict(VALID_SCALE_FORM)
        del form["starting_finger"]
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(form)
        self.assertIn("starting_finger", str(ctx.exception))

    def test_starting_finger_out_of_range_rejected(self):
        for bad_finger in (0, 5, -1, "2", 2.0, True, None):
            with self.subTest(finger=bad_finger):
                with self.assertRaises(theory.ConfigError):
                    self.load_broken(
                        {**VALID_SCALE_FORM, "starting_finger": bad_finger})

    def test_caged_shape_forbidden_for_scale_rejected(self):
        bad = {**VALID_SCALE_FORM, "caged_shape": "E"}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("caged_shape", str(ctx.exception))
        self.assertIn("forbidden", str(ctx.exception))

    def test_bad_string_label_rejected(self):
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "C": [5]}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_numeric_string_keys_rejected(self):
        """The old numeric 6..1 string keys are not valid TAB labels."""
        bad = {**VALID_FORM,
               "tab": {i: frets for i, frets in
                       zip((6, 5, 4, 3, 2, 1), VALID_FORM["tab"].values())}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_missing_string_rejected(self):
        """Every string label must be present (with >= 1 note)."""
        tab = dict(VALID_FORM["tab"])
        del tab["E"]
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "tab": tab})

    def test_empty_string_note_list_rejected(self):
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": []}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_span_over_six_frets_rejected(self):
        # Fret 12 on the low E is E, in-scale for A minor pentatonic, so
        # only the span check can catch it.
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": [5, 12]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("span", str(ctx.exception))

    def test_unknown_scale_ref_rejected(self):
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken({**VALID_FORM, "scale": "does_not_exist"})
        self.assertIn("does_not_exist", str(ctx.exception))

    def test_duplicate_id_rejected(self):
        other = {**VALID_FORM, "name": "Same id, different file"}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(VALID_FORM, other)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_missing_required_fields_rejected(self):
        for field in ("id", "scale", "name", "anchor", "example_key", "tab"):
            form = dict(VALID_FORM)
            del form[field]
            with self.subTest(missing=field):
                with self.assertRaises(theory.ConfigError) as ctx:
                    self.load_broken(form)
                self.assertIn(field, str(ctx.exception))

    def test_empty_id_rejected(self):
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "id": "  "})

    def test_non_int_frets_rejected(self):
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "D": [5, "7"]}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_unknown_anchor_rejected(self):
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "anchor": "root_high_e"})

    def test_empty_dir_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(theory.ConfigError):
                theory.load_fingerings(tmp)
