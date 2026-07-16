"""Tests for config loading and load-time validation of fingering forms.

Forms are hand-authored TABs in the fixed example key A (root on the
form's anchor string: low E fret 5 for root_low_e, A string fret 12 for
root_low_a); the loader is the validator, so broken-TAB cases here are
the guard against typos in hand-authored configs.
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

# A known-good A-string-root scale config (major scale 2nd finger form,
# root = A string fret 12).
VALID_A_ROOT_SCALE_FORM = {
    "id": "test-a-root-scale-form",
    "scale": "major_scale",
    "name": "Test A-root Scale Form",
    "starting_finger": 2,
    "anchor": "root_low_a",
    "example_key": "A",
    "tab": {
        "E": [], "A": [12, 14], "D": [11, 12, 14],
        "G": [11, 13, 14], "B": [12, 14], "e": [10, 12, 14],
    },
}

# A known-good arpeggio config with 1-note strings (A major arpeggio,
# 1st finger form — arpeggios use finger-form labels like scales).
VALID_ARPEGGIO_FORM = {
    "id": "test-arpeggio-form",
    "scale": "major_arpeggio",
    "name": "Test Arpeggio Form",
    "starting_finger": 1,
    "anchor": "root_low_e",
    "example_key": "A",
    "tab": {
        "E": [5], "A": [4, 7], "D": [7], "G": [6], "B": [5], "e": [5],
    },
}

# Shipped configs: the E-string-root and A-string-root finger forms of the
# major and natural minor scales, the five seventh-chord arpeggios in 1st
# and 2nd finger forms (hand-authored TABs derived from the same-finger
# major-scale forms), and the five CAGED boxes of each pentatonic scale.
EXPECTED_FORM_COUNTS = {"scale": 12, "arpeggio": 10, "pentatonic": 10}
EXPECTED_FORM_IDS = {
    "major-pentatonic-c-shape",
    "major-pentatonic-a-shape",
    "major-pentatonic-g-shape",
    "major-pentatonic-e-shape",
    "major-pentatonic-d-shape",
    "minor-pentatonic-c-shape",
    "minor-pentatonic-a-shape",
    "minor-pentatonic-g-shape",
    "minor-pentatonic-e-shape",
    "minor-pentatonic-d-shape",
    "major-scale-e-root-1st-finger-form",
    "major-scale-e-root-2nd-finger-form",
    "major-scale-e-root-4th-finger-form",
    "major-scale-a-root-1st-finger-form",
    "major-scale-a-root-2nd-finger-form",
    "major-scale-a-root-4th-finger-form",
    "natural-minor-scale-e-root-1st-finger-form",
    "natural-minor-scale-e-root-2nd-finger-form",
    "natural-minor-scale-e-root-4th-finger-form",
    "natural-minor-scale-a-root-1st-finger-form",
    "natural-minor-scale-a-root-2nd-finger-form",
    "natural-minor-scale-a-root-4th-finger-form",
    "major7-arpeggio-e-root-1st-finger-form",
    "dominant7-arpeggio-e-root-1st-finger-form",
    "minor7-arpeggio-e-root-1st-finger-form",
    "minor7b5-arpeggio-e-root-1st-finger-form",
    "diminished7-arpeggio-e-root-1st-finger-form",
    "major7-arpeggio-e-root-2nd-finger-form",
    "dominant7-arpeggio-e-root-2nd-finger-form",
    "minor7-arpeggio-e-root-2nd-finger-form",
    "minor7b5-arpeggio-e-root-2nd-finger-form",
    "diminished7-arpeggio-e-root-2nd-finger-form",
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
    def test_32_configs_load_and_validate(self):
        fingerings = theory.load_fingerings()
        self.assertEqual(len(fingerings), 32)

    def test_count_by_category(self):
        """3 E-root + 3 A-root finger forms for each of the major and
        natural minor scales + 5 seventh-chord arpeggios in 1st and 2nd
        finger forms + 2 pentatonic scales x 5 CAGED boxes."""
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

    def test_labels_unique_and_valid_per_scale(self):
        """CAGED shapes / starting fingers are valid and never repeat
        within one (scale, anchor) group; the shipped major-scale forms
        are fingers 1, 2, 4 per root string and each seventh-chord
        arpeggio ships fingers 1, 2 (E-root only). display_label stays
        unique within each scale — it's the only label the player sees."""
        by_scale = {}
        by_group = {}
        for form in theory.load_fingerings().values():
            by_scale.setdefault(form["scale"], []).append(form)
            key = (form["scale"], form["anchor"])
            by_group.setdefault(key, []).append(form)
        for scale_id, forms in by_scale.items():
            labels = [f["display_label"] for f in forms]
            self.assertEqual(len(labels), len(set(labels)), scale_id)
        for (scale_id, anchor), forms in by_group.items():
            category = forms[0]["category"]
            if category == "pentatonic":
                shapes = [f["caged_shape"] for f in forms]
                self.assertEqual(len(shapes), len(set(shapes)), scale_id)
                for shape in shapes:
                    self.assertIn(shape, theory.CAGED_SHAPES, scale_id)
            elif category == "arpeggio":
                self.assertEqual(anchor, "root_low_e", scale_id)
                self.assertEqual(
                    sorted(f["starting_finger"] for f in forms),
                    [1, 2], scale_id)
            else:
                self.assertEqual(
                    sorted(f["starting_finger"] for f in forms),
                    [1, 2, 4], (scale_id, anchor))

    def test_1st_finger_maj7_and_dom7_arpeggios_skip_the_high_e_string(self):
        for form_id in ("major7-arpeggio-e-root-1st-finger-form",
                        "dominant7-arpeggio-e-root-1st-finger-form"):
            with self.subTest(form=form_id):
                form = theory.load_fingerings()[form_id]
                self.assertEqual(form["category"], "arpeggio")
                self.assertEqual(form["display_label"],
                                 "1st Finger Form (E-root)")
                self.assertEqual(form["tab"]["e"], [])
                self.assertEqual(form["offsets"][1], [])

    def test_shipped_form_fields_and_labels(self):
        """caged_shape XOR starting_finger; display_label per category;
        TAB in the fixed example key with derived offsets."""
        for form in theory.load_fingerings().values():
            self.assertIsInstance(form["name"], str)
            self.assertIn(form["anchor"], theory.ANCHOR_STRATEGIES)
            self.assertEqual(set(form["tab"]), set(theory.TAB_STRINGS))
            self.assertEqual(set(form["offsets"]), {1, 2, 3, 4, 5, 6})
            self.assertIn(form["category"], theory.CATEGORIES)
            root_label = {"root_low_e": "E", "root_low_a": "A",
                          "root_low_d": "D", "root_low_g": "G"}[form["anchor"]]
            if form["category"] == "pentatonic":
                self.assertIn(form["caged_shape"], theory.CAGED_SHAPES)
                self.assertIsNone(form["starting_finger"])
                self.assertEqual(form["display_label"],
                                 f"{form['caged_shape']} Shape")
            else:
                self.assertIsNone(form["caged_shape"])
                self.assertIn(form["starting_finger"], (1, 2, 3, 4))
                self.assertEqual(
                    form["display_label"],
                    f"{theory.ordinal(form['starting_finger'])} Finger Form "
                    f"({root_label}-root)",
                )

    def test_offsets_derived_from_tab(self):
        """offset = authored fret - example-key anchor fret (A -> 5 on the
        low E string, A -> 12 on the A string)."""
        for form in theory.load_fingerings().values():
            anchor = theory.anchor_fret(theory.EXAMPLE_KEY, form["anchor"])
            for label, string in theory.TAB_STRINGS.items():
                self.assertEqual(
                    form["offsets"][string],
                    [f - anchor for f in form["tab"][label]],
                )

    def test_display_labels_literal_examples(self):
        fingerings = theory.load_fingerings()
        self.assertEqual(
            fingerings["major-scale-e-root-1st-finger-form"]["display_label"],
            "1st Finger Form (E-root)")
        self.assertEqual(
            fingerings["major-scale-e-root-2nd-finger-form"]["display_label"],
            "2nd Finger Form (E-root)")
        self.assertEqual(
            fingerings["major-scale-e-root-4th-finger-form"]["display_label"],
            "4th Finger Form (E-root)")
        self.assertEqual(
            fingerings["major-scale-a-root-1st-finger-form"]["display_label"],
            "1st Finger Form (A-root)")
        self.assertEqual(
            fingerings["major-scale-a-root-2nd-finger-form"]["display_label"],
            "2nd Finger Form (A-root)")
        self.assertEqual(
            fingerings["major-scale-a-root-4th-finger-form"]["display_label"],
            "4th Finger Form (A-root)")
        self.assertEqual(
            fingerings["minor-pentatonic-e-shape"]["display_label"],
            "E Shape")
        self.assertEqual(
            fingerings["major-pentatonic-g-shape"]["display_label"],
            "G Shape")

    def test_each_pentatonic_scale_ships_all_five_caged_boxes(self):
        by_scale = {}
        for form in theory.load_fingerings().values():
            if form["category"] == "pentatonic":
                by_scale.setdefault(form["scale"], []).append(form)
        self.assertEqual(
            set(by_scale), {"major_pentatonic", "minor_pentatonic"})
        for scale_id, forms in by_scale.items():
            self.assertEqual(sorted(f["caged_shape"] for f in forms),
                             sorted(theory.CAGED_SHAPES), scale_id)

    # Each CAGED box anchors on the string carrying its root (the loader
    # enforces that the root sits on the anchor string; this pins WHICH
    # string that is for the shipped boxes).
    EXPECTED_BOX_ANCHORS = {
        "E": "root_low_e", "D": "root_low_d",
        "C": "root_low_a", "A": "root_low_a", "G": "root_low_g",
    }

    def test_shipped_pentatonic_boxes_anchor_on_their_root_string(self):
        for form in theory.load_fingerings().values():
            if form["category"] != "pentatonic":
                continue
            with self.subTest(form=form["id"]):
                self.assertEqual(
                    form["anchor"],
                    self.EXPECTED_BOX_ANCHORS[form["caged_shape"]])

    def test_shipped_a_root_forms_authored_at_the_12th_position(self):
        """The A-root TABs are authored with the root at A-string fret 12
        and leave the low E string silent."""
        fingerings = theory.load_fingerings()
        for form_id in ("major-scale-a-root-1st-finger-form",
                        "major-scale-a-root-2nd-finger-form",
                        "major-scale-a-root-4th-finger-form",
                        "natural-minor-scale-a-root-1st-finger-form",
                        "natural-minor-scale-a-root-2nd-finger-form",
                        "natural-minor-scale-a-root-4th-finger-form"):
            with self.subTest(form=form_id):
                form = fingerings[form_id]
                self.assertEqual(form["anchor"], "root_low_a")
                self.assertIn(12, form["tab"]["A"])
                self.assertEqual(form["tab"]["E"], [])

    # The six natural-minor finger forms, pinned note-for-note to their
    # source ("A minor scale, six different scale forms", Shalfi's Lesson
    # Materials) — the TAB is hand-authored convention, so any drift from
    # the source is a regression even if it still validates musically.
    EXPECTED_MINOR_SCALE_TABS = {
        "natural-minor-scale-e-root-1st-finger-form": {
            "E": [5, 7, 8], "A": [5, 7, 8], "D": [5, 7, 9],
            "G": [5, 7, 9], "B": [6, 8, 10], "e": [],
        },
        "natural-minor-scale-e-root-2nd-finger-form": {
            "E": [5, 7], "A": [3, 5, 7], "D": [3, 5, 7],
            "G": [4, 5, 7], "B": [5, 6], "e": [3, 5],
        },
        "natural-minor-scale-e-root-4th-finger-form": {
            "E": [5], "A": [2, 3, 5], "D": [2, 3, 5],
            "G": [2, 4, 5], "B": [3, 5, 6], "e": [3, 5],
        },
        "natural-minor-scale-a-root-1st-finger-form": {
            "E": [], "A": [12, 14, 15], "D": [12, 14, 15],
            "G": [12, 14, 16], "B": [13, 15, 17], "e": [13, 15, 17],
        },
        "natural-minor-scale-a-root-2nd-finger-form": {
            "E": [], "A": [12, 14], "D": [10, 12, 14],
            "G": [10, 12, 14], "B": [12, 13], "e": [10, 12, 13],
        },
        "natural-minor-scale-a-root-4th-finger-form": {
            "E": [], "A": [12], "D": [9, 10, 12],
            "G": [9, 10, 12], "B": [10, 12, 13], "e": [10, 12],
        },
    }

    def test_natural_minor_tabs_match_the_source_note_for_note(self):
        fingerings = theory.load_fingerings()
        for form_id, tab in self.EXPECTED_MINOR_SCALE_TABS.items():
            with self.subTest(form=form_id):
                form = fingerings[form_id]
                self.assertEqual(form["scale"], "natural_minor_scale")
                self.assertEqual(form["tab"], tab)


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
        self.assertEqual(form["display_label"], "2nd Finger Form (E-root)")
        self.assertEqual(form["offsets"][5], [-1, 0, 2])

    def test_valid_a_root_scale_config_loads(self):
        """A-root forms anchor at A-string fret 12 in the example key, so
        offsets are relative to 12 and the silent low E derives to []."""
        fingerings = load_temp(VALID_A_ROOT_SCALE_FORM)
        form = fingerings["test-a-root-scale-form"]
        self.assertEqual(form["category"], "scale")
        self.assertEqual(form["anchor"], "root_low_a")
        self.assertEqual(form["display_label"], "2nd Finger Form (A-root)")
        self.assertEqual(form["offsets"][6], [])
        self.assertEqual(form["offsets"][5], [0, 2])
        self.assertEqual(form["offsets"][4], [-1, 0, 2])
        self.assertEqual(form["offsets"][1], [-2, 0, 2])

    def test_pentatonic_may_play_below_the_root(self):
        """CAGED boxes span the whole position: low-E fret 3 (G) sounds
        below the root A but is fine for a pentatonic form."""
        ok = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": [3, 5, 8]}}
        fingerings = load_temp(ok)
        self.assertEqual(fingerings["test-form"]["tab"]["E"], [3, 5, 8])

    def test_a_root_pentatonic_with_low_e_notes_below_root_loads(self):
        """An A-string-anchored CAGED box still plays the low E string,
        below the root in pitch — the finger-form rule must not apply."""
        ok = {
            "id": "test-a-root-pent",
            "scale": "minor_pentatonic",
            "name": "Test A-root Pentatonic",
            "caged_shape": "G",
            "anchor": "root_low_a",
            "example_key": "A",
            "tab": {
                "E": [8, 10], "A": [10, 12], "D": [10, 12],
                "G": [9, 12], "B": [10, 13], "e": [8, 10],
            },
        }
        fingerings = load_temp(ok)
        form = fingerings["test-a-root-pent"]
        self.assertEqual(form["tab"]["E"], [8, 10])
        self.assertEqual(form["offsets"][6], [-4, -2])

    def test_valid_arpeggio_config_with_1_note_strings_loads(self):
        fingerings = load_temp(VALID_ARPEGGIO_FORM)
        form = fingerings["test-arpeggio-form"]
        self.assertEqual(form["category"], "arpeggio")
        self.assertIsNone(form["caged_shape"])
        self.assertEqual(form["starting_finger"], 1)
        self.assertEqual(form["display_label"], "1st Finger Form (E-root)")
        self.assertEqual(form["tab"]["E"], [5])
        self.assertEqual(form["tab"]["D"], [7])


class BrokenConfigTests(SimpleTestCase):
    """Deliberately broken configs must raise clear ConfigErrors."""

    def load_broken(self, *forms):
        with tempfile.TemporaryDirectory() as tmp:
            write_forms(tmp, *forms)
            theory.load_fingerings(tmp)  # expected to raise

    def test_overlong_id_rejected(self):
        """Every loadable id must fit the AttemptLog.form_id column."""
        bad = {**VALID_FORM, "id": "x" * (theory.FORM_ID_MAX_LENGTH + 1)}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn(str(theory.FORM_ID_MAX_LENGTH), str(ctx.exception))

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
        """'Start on the root' (finger forms): low-E fret 2 (F#) is in
        A major but sounds below the root A."""
        bad = {**VALID_SCALE_FORM,
               "tab": {**VALID_SCALE_FORM["tab"], "E": [2, 5, 7]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("below the low root", msg)
        self.assertIn("fret 2", msg)

    def test_note_below_a_string_root_rejected(self):
        """For root_low_a finger forms the root is A-string fret 12; a
        low-E note (fret 12 = E, in scale) still sounds below it."""
        bad = {**VALID_A_ROOT_SCALE_FORM,
               "tab": {**VALID_A_ROOT_SCALE_FORM["tab"], "E": [12]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        msg = str(ctx.exception)
        self.assertIn("below the low root", msg)
        self.assertIn("A-string fret 12", msg)

    def test_root_missing_from_low_e_rejected(self):
        """The low-E root (fret 5 in A) must be in the TAB."""
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": [8]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("root", str(ctx.exception))
        self.assertIn("string E", str(ctx.exception))

    def test_root_missing_from_a_string_rejected(self):
        """A root_low_a form must carry the root on the A string (fret 12
        in the example key)."""
        bad = {**VALID_A_ROOT_SCALE_FORM,
               "tab": {**VALID_A_ROOT_SCALE_FORM["tab"], "A": [14]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("root", str(ctx.exception))
        self.assertIn("string A", str(ctx.exception))

    def test_wrong_example_key_rejected(self):
        for bad_key in ("C", "a", "", None, 5):
            with self.subTest(example_key=bad_key):
                with self.assertRaises(theory.ConfigError) as ctx:
                    self.load_broken({**VALID_FORM, "example_key": bad_key})
                self.assertIn("example_key", str(ctx.exception))

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

    def test_caged_shape_forbidden_for_arpeggio_rejected(self):
        bad = {**VALID_ARPEGGIO_FORM, "caged_shape": "E"}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("caged_shape", str(ctx.exception))
        self.assertIn("forbidden", str(ctx.exception))

    def test_starting_finger_missing_for_arpeggio_rejected(self):
        form = dict(VALID_ARPEGGIO_FORM)
        del form["starting_finger"]
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(form)
        self.assertIn("starting_finger", str(ctx.exception))

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
        """Every string label must be present (an explicit [] marks a
        skipped string; a missing label is a typo)."""
        tab = dict(VALID_FORM["tab"])
        del tab["E"]
        with self.assertRaises(theory.ConfigError):
            self.load_broken({**VALID_FORM, "tab": tab})

    def test_empty_high_e_list_allowed(self):
        """A form may skip a string with an explicit [] (e.g. the maj7
        arpeggio E shape plays nothing on high e)."""
        ok = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "e": []}}
        fingerings = load_temp(ok)
        form = fingerings["test-form"]
        self.assertEqual(form["tab"]["e"], [])
        self.assertEqual(form["offsets"][1], [])

    def test_empty_low_e_list_rejected_root_must_be_present(self):
        """An empty low E can never hold the root, so it still fails."""
        bad = {**VALID_FORM, "tab": {**VALID_FORM["tab"], "E": []}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("root", str(ctx.exception))

    def test_all_strings_empty_rejected(self):
        bad = {**VALID_FORM,
               "tab": {label: [] for label in VALID_FORM["tab"]}}
        with self.assertRaises(theory.ConfigError) as ctx:
            self.load_broken(bad)
        self.assertIn("no notes", str(ctx.exception))

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
