"""Tests for config loading and load-time validation of fingering forms."""

import tempfile
from pathlib import Path

import yaml
from django.test import SimpleTestCase

from practice import theory

# A known-good CAGED fingering config used as the base for broken variants.
VALID_FORM = {
    "id": "test-form",
    "scale": "minor_pentatonic",
    "name": "Test Form",
    "caged_shape": "E",
    "anchor": "root_low_e",
    "offsets": {
        6: [0, 3], 5: [0, 2], 4: [0, 2],
        3: [0, 2], 2: [0, 3], 1: [0, 3],
    },
}

# A known-good scale-category config (major scale 2nd finger form).
VALID_SCALE_FORM = {
    "id": "test-scale-form",
    "scale": "major_scale",
    "name": "Test Scale Form",
    "starting_finger": 2,
    "anchor": "root_low_e",
    "offsets": {
        6: [-1, 0, 2], 5: [-1, 0, 2], 4: [-1, 1, 2],
        3: [-1, 1, 2], 2: [0, 2], 1: [-1, 0, 2],
    },
}

# A known-good arpeggio config with 1-note strings (major arpeggio E shape).
VALID_ARPEGGIO_FORM = {
    "id": "test-arpeggio-form",
    "scale": "major_arpeggio",
    "name": "Test Arpeggio Form",
    "caged_shape": "E",
    "anchor": "root_low_e",
    "offsets": {
        6: [0], 5: [-1, 2], 4: [2], 3: [1], 2: [0], 1: [0],
    },
}

# Shipped configs are pruned to the 3 E-root major-scale finger forms while
# they are manually validated; pentatonic/arpeggio/natural-minor forms can be
# regenerated with scripts/generate_fingerings.py (which restores all 41).
EXPECTED_FORM_COUNTS = {"scale": 3}
EXPECTED_FORM_IDS = {
    "major-scale-1st-finger-form",
    "major-scale-2nd-finger-form",
    "major-scale-4th-finger-form",
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
        """Only the 3 major-scale finger forms ship."""
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
        """caged_shape XOR starting_finger; display_label per category."""
        for form in theory.load_fingerings().values():
            self.assertIsInstance(form["name"], str)
            self.assertEqual(form["anchor"], "root_low_e")
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

    def test_display_labels_literal_examples(self):
        fingerings = theory.load_fingerings()
        self.assertEqual(
            fingerings["major-scale-1st-finger-form"]["display_label"],
            "1st Finger Form")
        self.assertEqual(
            fingerings["major-scale-2nd-finger-form"]["display_label"],
            "2nd Finger Form")
        self.assertEqual(
            fingerings["major-scale-4th-finger-form"]["display_label"],
            "4th Finger Form")


class ValidTempConfigTests(SimpleTestCase):
    """Sanity checks: the base fixtures themselves are valid."""

    def test_valid_caged_config_loads(self):
        fingerings = load_temp(VALID_FORM)
        form = fingerings["test-form"]
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

    def test_valid_arpeggio_config_with_1_note_strings_loads(self):
        fingerings = load_temp(VALID_ARPEGGIO_FORM)
        form = fingerings["test-arpeggio-form"]
        self.assertEqual(form["category"], "arpeggio")
        self.assertEqual(form["offsets"][6], [0])
        self.assertEqual(form["offsets"][4], [2])


class BrokenConfigTests(SimpleTestCase):
    """Deliberately broken configs must raise clear ConfigErrors."""

    def load_broken(self, *forms):
        with tempfile.TemporaryDirectory() as tmp:
            write_forms(tmp, *forms)
            theory.load_fingerings(tmp)  # expected to raise

    def test_out_of_scale_offset_rejected(self):
        # Offset 1 on string 4 gives interval 11, not in minor pentatonic.
        bad = {**VALID_FORM, "offsets": {**VALID_FORM["offsets"], 4: [0, 1]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("string 4", msg)
        self.assertIn("offset 1", msg)
        self.assertIn("form_0.yaml", msg)

    def test_incomplete_form_rejected_naming_missing_interval(self):
        # Remove every note carrying interval 10 (b7) from the minor pent
        # box: string 4 offset 0 and string 2 offset 3.
        bad = {**VALID_FORM,
               "offsets": {**VALID_FORM["offsets"], 4: [2], 2: [0]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("incomplete", msg)
        self.assertIn("10", msg)
        self.assertIn("minor_pentatonic", msg)

    def test_incomplete_scale_form_rejected(self):
        # Remove every note carrying interval 11 (the major 7th) from the
        # major-scale form: offset -1 on strings 6 and 1, offset 1 on
        # string 4. All strings keep >= 1 note, so only completeness fails.
        offsets = dict(VALID_SCALE_FORM["offsets"])
        offsets[6] = [0, 2]
        offsets[4] = [2]
        offsets[1] = [0, 2]
        bad = {**VALID_SCALE_FORM, "offsets": offsets}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("incomplete", msg)
        self.assertIn("11", msg)

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

    def test_bad_string_number_rejected(self):
        bad = {**VALID_FORM,
               "offsets": {**VALID_FORM["offsets"], 7: [0]}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_missing_string_rejected(self):
        """Every string key 1-6 must be present (with >= 1 note)."""
        offsets = dict(VALID_FORM["offsets"])
        del offsets[6]
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "offsets": offsets})

    def test_empty_string_note_list_rejected(self):
        bad = {**VALID_FORM, "offsets": {**VALID_FORM["offsets"], 6: []}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_span_over_six_frets_rejected(self):
        bad = {**VALID_FORM, "offsets": {**VALID_FORM["offsets"], 6: [0, 7]}}
        # (offset 7 on string 6 is interval 7, in-scale, so only the span
        # check can catch it)
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
        for field in ("id", "scale", "name", "anchor", "offsets"):
            form = dict(VALID_FORM)
            del form[field]
            with self.subTest(missing=field):
                with self.assertRaises(theory.ConfigError) as ctx:
                    self.load_broken(form)
                self.assertIn(field, str(ctx.exception))

    def test_empty_id_rejected(self):
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "id": "  "})

    def test_non_int_offsets_rejected(self):
        bad = {**VALID_FORM, "offsets": {**VALID_FORM["offsets"], 6: [0, "3"]}}
        with self.assertRaises(theory.ConfigError):
            self.load_broken(bad)

    def test_unknown_anchor_rejected(self):
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "anchor": "root_high_e"})

    def test_empty_dir_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(theory.ConfigError):
                theory.load_fingerings(tmp)
