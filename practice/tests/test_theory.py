"""Exhaustive tests for the music theory engine (practice/theory.py).

The shipped configs are pruned to the 3 E-root major-scale forms, but the
engine must stay viable for all 41 generated forms. Tests that exercise
pentatonic/arpeggio/natural-minor forms therefore run against a temp dir
populated by scripts/generate_fingerings.py (never against the live
configs dir, which the generator would delete-and-rewrite).
"""

import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from practice import theory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR = REPO_ROOT / "scripts" / "generate_fingerings.py"

# Module-level temp dir holding all 41 generator-produced forms.
_generated_tmp = None
GENERATED_DIR = None


def setUpModule():
    global _generated_tmp, GENERATED_DIR
    _generated_tmp = tempfile.TemporaryDirectory()
    GENERATED_DIR = Path(_generated_tmp.name)
    subprocess.run(
        [sys.executable, str(GENERATOR), "-o", str(GENERATED_DIR)],
        check=True, capture_output=True, text=True, cwd=REPO_ROOT,
    )


def tearDownModule():
    _generated_tmp.cleanup()


# Expected root fret on the low E string for every key (E maps to 12, not 0).
EXPECTED_ROOT_FRETS = {
    "C": 8, "C#": 9, "D": 10, "D#": 11, "E": 12, "F": 1,
    "F#": 2, "G": 3, "G#": 4, "A": 5, "A#": 6, "B": 7,
}

# All 9 shipped scales: id -> (name, intervals, category).
EXPECTED_SCALES = {
    "major_pentatonic": ("Major Pentatonic", [0, 2, 4, 7, 9], "pentatonic"),
    "minor_pentatonic": ("Minor Pentatonic", [0, 3, 5, 7, 10], "pentatonic"),
    "major_arpeggio": ("Major Arpeggio", [0, 4, 7], "arpeggio"),
    "minor_arpeggio": ("Minor Arpeggio", [0, 3, 7], "arpeggio"),
    "major7_arpeggio": ("Major 7 Arpeggio", [0, 4, 7, 11], "arpeggio"),
    "minor7_arpeggio": ("Minor 7 Arpeggio", [0, 3, 7, 10], "arpeggio"),
    "dominant7_arpeggio": ("Dominant 7 Arpeggio", [0, 4, 7, 10], "arpeggio"),
    "major_scale": ("Major Scale", [0, 2, 4, 5, 7, 9, 11], "scale"),
    "natural_minor_scale":
        ("Natural Minor Scale", [0, 2, 3, 5, 7, 8, 10], "scale"),
}


def frets_by_string(notes):
    """{string: sorted [frets]} from a resolve_form() note list."""
    frets = {}
    for n in notes:
        frets.setdefault(n["string"], []).append(n["fret"])
    return {s: sorted(fs) for s, fs in frets.items()}


def normalised_anchor(key, form):
    """Independent recomputation of the octave-normalised anchor fret."""
    anchor = theory.anchor_fret(key, form["anchor"])
    min_fret = anchor + min(o for offs in form["offsets"].values()
                            for o in offs)
    while min_fret < 1:
        anchor += 12
        min_fret += 12
    while min_fret > 12:
        anchor -= 12
        min_fret -= 12
    return anchor


class NoteNameTests(SimpleTestCase):
    def test_all_pitch_classes(self):
        expected = ["C", "C#", "D", "D#", "E", "F",
                    "F#", "G", "G#", "A", "A#", "B"]
        for pc in range(12):
            with self.subTest(pc=pc):
                self.assertEqual(theory.note_name(pc), expected[pc])

    def test_wraps_mod_12(self):
        self.assertEqual(theory.note_name(12), "C")
        self.assertEqual(theory.note_name(21), "A")

    def test_invalid_type_raises(self):
        for bad in ("A", 4.5, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    theory.note_name(bad)


class OrdinalTests(SimpleTestCase):
    def test_ordinals(self):
        cases = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th",
                 11: "11th", 12: "12th", 13: "13th", 21: "21st",
                 22: "22nd", 23: "23rd", 111: "111th"}
        for n, text in cases.items():
            with self.subTest(n=n):
                self.assertEqual(theory.ordinal(n), text)

    def test_invalid_type_raises(self):
        for bad in ("2", 2.0, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    theory.ordinal(bad)


class KeyTests(SimpleTestCase):
    def test_all_keys_map_to_pitch_classes(self):
        for pc, key in enumerate(theory.NOTE_NAMES):
            with self.subTest(key=key):
                self.assertEqual(theory.key_to_pc(key), pc)

    def test_unknown_key_raises(self):
        for bad in ("H", "Bb", "", "a", None, 5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    theory.key_to_pc(bad)


class RootFretTests(SimpleTestCase):
    def test_root_fret_low_e_all_12_keys(self):
        """Every key, including the E -> 12 (not 0) edge case."""
        self.assertEqual(set(EXPECTED_ROOT_FRETS), set(theory.KEYS))
        for key, fret in EXPECTED_ROOT_FRETS.items():
            with self.subTest(key=key):
                self.assertEqual(theory.root_fret_low_e(key), fret)

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            theory.root_fret_low_e("X")

    def test_anchor_fret_root_low_e_matches(self):
        for key in theory.KEYS:
            self.assertEqual(theory.anchor_fret(key, "root_low_e"),
                             theory.root_fret_low_e(key))

    def test_unknown_anchor_strategy_raises(self):
        with self.assertRaises(ValueError):
            theory.anchor_fret("A", "caged")


class ScaleIntervalTests(SimpleTestCase):
    def test_all_9_scales_literal(self):
        scales = theory.load_scales()
        self.assertEqual(set(scales), set(EXPECTED_SCALES))
        for scale_id, (name, intervals, category) in EXPECTED_SCALES.items():
            with self.subTest(scale=scale_id):
                self.assertEqual(scales[scale_id]["name"], name)
                self.assertEqual(scales[scale_id]["intervals"], intervals)
                self.assertEqual(scales[scale_id]["category"], category)

    def test_scale_names(self):
        self.assertEqual(
            sorted(theory.scale_names()),
            sorted(name for name, _, _ in EXPECTED_SCALES.values()),
        )


class ResolveFormExhaustiveTests(SimpleTestCase):
    """Every generated form x all 12 keys, every note verified
    independently. Covers the 3 shipped forms too (byte-identical copies
    are in the generated set) plus the 38 pruned-but-still-viable forms."""

    def test_every_form_every_key(self):
        fingerings = theory.load_fingerings(GENERATED_DIR)
        scales = theory.load_scales()
        self.assertEqual(len(fingerings), 41)
        # The pruned shipped set is a strict subset of the generated set.
        self.assertLess(set(theory.load_fingerings()), set(fingerings))
        for form_id, form in fingerings.items():
            intervals = set(scales[form["scale"]]["intervals"])
            all_offsets = [o for offs in form["offsets"].values() for o in offs]
            n_declared = len(all_offsets)
            for key in theory.KEYS:
                with self.subTest(form=form_id, key=key):
                    root_pc = theory.key_to_pc(key)
                    anchor = normalised_anchor(key, form)
                    window_start, notes = theory.resolve_form(
                        form_id, key, GENERATED_DIR)

                    # Window position and width; octave normalisation:
                    # the lowest fret of every form in every key is in
                    # [1, 12] and window_start == that lowest fret.
                    self.assertEqual(window_start, anchor + min(all_offsets))
                    self.assertEqual(window_start,
                                     min(n["fret"] for n in notes))
                    self.assertGreaterEqual(window_start, 1)
                    self.assertLessEqual(window_start, 12)
                    self.assertEqual(len(notes), n_declared)

                    # Completeness AND soundness: returned (string, fret) set
                    # equals the brute-force derivation from the offsets.
                    expected_cells = {
                        (s, anchor + o)
                        for s, offs in form["offsets"].items()
                        for o in offs
                    }
                    got_cells = {(n["string"], n["fret"]) for n in notes}
                    self.assertEqual(got_cells, expected_cells)

                    # Every scale interval appears somewhere (form
                    # completeness survives resolution).
                    seen_intervals = {(n["pitch_class"] - root_pc) % 12
                                      for n in notes}
                    self.assertEqual(seen_intervals, intervals)

                    saw_root = False
                    for n in notes:
                        # Exact dict shape.
                        self.assertEqual(
                            set(n),
                            {"string", "fret", "pitch_class",
                             "note_name", "is_root"},
                        )
                        # Strings 1-6 only.
                        self.assertIn(n["string"], (1, 2, 3, 4, 5, 6))
                        # Frets always >= 1: no open strings, ever.
                        self.assertGreaterEqual(n["fret"], 1)
                        # Recompute the pitch class from tuning + fret.
                        pc = (theory.STANDARD_TUNING[n["string"]]
                              + n["fret"]) % 12
                        self.assertEqual(n["pitch_class"], pc)
                        # Every note belongs to the scale.
                        self.assertIn((pc - root_pc) % 12, intervals)
                        # Note name matches the pitch class.
                        self.assertEqual(n["note_name"], theory.NOTE_NAMES[pc])
                        # is_root iff interval 0.
                        self.assertEqual(n["is_root"], pc == root_pc)
                        saw_root = saw_root or n["is_root"]
                        # Fret inside the 6-fret display window.
                        self.assertGreaterEqual(n["fret"], window_start)
                        self.assertLessEqual(
                            n["fret"], window_start + theory.WINDOW_SIZE - 1)
                    self.assertTrue(saw_root,
                                    "every form must contain the root")

    def test_notes_ordered_low_string_first(self):
        _, notes = theory.resolve_form(
            "minor-pentatonic-e-shape", "A", GENERATED_DIR)
        order = [(n["string"], n["fret"]) for n in notes]
        self.assertEqual(
            order, sorted(order, key=lambda sf: (-sf[0], sf[1])))


class OctaveNormalisationTests(SimpleTestCase):
    """The whole form shifts by octaves until its lowest fret is in [1, 12].

    Open strings (fret 0) are never allowed; high-offset shapes render low
    on the neck instead of past fret 12.
    """

    maxDiff = None

    def test_up_shift_f_major_pent_e_shape(self):
        # F anchors at fret 1; min offset -1 gives raw min fret 0, so the
        # whole form shifts UP an octave: frets 12-15.
        window_start, notes = theory.resolve_form(
            "major-pentatonic-e-shape", "F", GENERATED_DIR)
        self.assertEqual(window_start, 12)
        self.assertEqual(frets_by_string(notes), {
            6: [13, 15], 5: [12, 15], 4: [12, 15],
            3: [12, 14], 2: [13, 15], 1: [13, 15],
        })

    def test_down_shift_a_minor_pent_g_shape(self):
        # G-shape offsets are 6:[10,12] 5:[10,12] 4:[9,12] 3:[9,12]
        # 2:[10,12] 1:[10,12]; A anchors at fret 5, raw min fret 14, so the
        # whole form shifts DOWN an octave to frets 2-5.
        window_start, notes = theory.resolve_form(
            "minor-pentatonic-g-shape", "A", GENERATED_DIR)
        self.assertEqual(window_start, 2)
        self.assertEqual(frets_by_string(notes), {
            6: [3, 5], 5: [3, 5], 4: [2, 5],
            3: [2, 5], 2: [3, 5], 1: [3, 5],
        })

    def test_down_shift_c_major_pent_g_shape(self):
        # C anchors at fret 8; G-shape offsets 9..12 give raw frets 17-20,
        # normalised down to 5-8 (the same physical box as A minor pent E
        # shape — C major is A minor's relative major).
        window_start, notes = theory.resolve_form(
            "major-pentatonic-g-shape", "C", GENERATED_DIR)
        self.assertEqual(window_start, 5)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 8], 5: [5, 7], 4: [5, 7],
            3: [5, 7], 2: [5, 8], 1: [5, 8],
        })

    def test_no_shift_when_min_fret_already_in_range(self):
        # F minor pent E shape: anchor 1, min offset 0 -> stays at fret 1.
        window_start, _ = theory.resolve_form(
            "minor-pentatonic-e-shape", "F", GENERATED_DIR)
        self.assertEqual(window_start, 1)

    def test_min_fret_in_1_to_12_for_every_form_and_key(self):
        for form_id in theory.load_fingerings(GENERATED_DIR):
            for key in theory.KEYS:
                with self.subTest(form=form_id, key=key):
                    window_start, notes = theory.resolve_form(
                        form_id, key, GENERATED_DIR)
                    min_fret = min(n["fret"] for n in notes)
                    self.assertEqual(window_start, min_fret)
                    self.assertGreaterEqual(min_fret, 1)
                    self.assertLessEqual(min_fret, 12)


class HandVerifiedFixtureTests(SimpleTestCase):
    """Complete hand-written expected outputs, compared exactly."""

    maxDiff = None

    def test_a_minor_pentatonic_e_shape(self):
        # A minor pentatonic = A C D E G (pcs 9, 0, 2, 4, 7). Anchor fret 5.
        # Classic box: 5-8 / 5-7 / 5-7 / 5-7 / 5-8 / 5-8, roots at
        # string 6 fret 5, string 4 fret 7, string 1 fret 5.
        window_start, notes = theory.resolve_form(
            "minor-pentatonic-e-shape", "A", GENERATED_DIR)
        self.assertEqual(window_start, 5)
        expected = [
            {"string": 6, "fret": 5, "pitch_class": 9, "note_name": "A", "is_root": True},
            {"string": 6, "fret": 8, "pitch_class": 0, "note_name": "C", "is_root": False},
            {"string": 5, "fret": 5, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 5, "fret": 7, "pitch_class": 4, "note_name": "E", "is_root": False},
            {"string": 4, "fret": 5, "pitch_class": 7, "note_name": "G", "is_root": False},
            {"string": 4, "fret": 7, "pitch_class": 9, "note_name": "A", "is_root": True},
            {"string": 3, "fret": 5, "pitch_class": 0, "note_name": "C", "is_root": False},
            {"string": 3, "fret": 7, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 2, "fret": 5, "pitch_class": 4, "note_name": "E", "is_root": False},
            {"string": 2, "fret": 8, "pitch_class": 7, "note_name": "G", "is_root": False},
            {"string": 1, "fret": 5, "pitch_class": 9, "note_name": "A", "is_root": True},
            {"string": 1, "fret": 8, "pitch_class": 0, "note_name": "C", "is_root": False},
        ]
        self.assertEqual(notes, expected)

    def test_a_minor_pentatonic_e_shape_frets_per_string(self):
        """The exact per-string fret sets required by the spec."""
        _, notes = theory.resolve_form(
            "minor-pentatonic-e-shape", "A", GENERATED_DIR)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 8], 5: [5, 7], 4: [5, 7],
            3: [5, 7], 2: [5, 8], 1: [5, 8],
        })

    def test_c_major_arpeggio_e_shape_frets_per_string(self):
        """C major arpeggio E shape: anchor 8, spec-required fret table."""
        window_start, notes = theory.resolve_form(
            "major-arpeggio-e-shape", "C", GENERATED_DIR)
        self.assertEqual(window_start, 7)
        self.assertEqual(frets_by_string(notes), {
            6: [8], 5: [7, 10], 4: [10], 3: [9], 2: [8], 1: [8],
        })
        # C major arpeggio = C E G only.
        self.assertEqual({n["note_name"] for n in notes}, {"C", "E", "G"})

    def test_c_major_scale_2nd_finger_form_frets_per_string(self):
        """C major scale 2nd finger form: spec-required fret table."""
        window_start, notes = theory.resolve_form(
            "major-scale-2nd-finger-form", "C")
        self.assertEqual(window_start, 7)
        self.assertEqual(frets_by_string(notes), {
            6: [7, 8, 10], 5: [7, 8, 10], 4: [7, 9, 10],
            3: [7, 9, 10], 2: [8, 10], 1: [7, 8, 10],
        })
        # All 7 notes of C major, no accidentals.
        self.assertEqual({n["note_name"] for n in notes},
                         {"C", "D", "E", "F", "G", "A", "B"})

    def test_c_major_pentatonic_e_shape(self):
        # C major pentatonic = C D E G A (pcs 0, 2, 4, 7, 9). Anchor fret 8;
        # min offset -1 so the window starts at 7.
        window_start, notes = theory.resolve_form(
            "major-pentatonic-e-shape", "C", GENERATED_DIR)
        self.assertEqual(window_start, 7)
        expected = [
            {"string": 6, "fret": 8, "pitch_class": 0, "note_name": "C", "is_root": True},
            {"string": 6, "fret": 10, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 5, "fret": 7, "pitch_class": 4, "note_name": "E", "is_root": False},
            {"string": 5, "fret": 10, "pitch_class": 7, "note_name": "G", "is_root": False},
            {"string": 4, "fret": 7, "pitch_class": 9, "note_name": "A", "is_root": False},
            {"string": 4, "fret": 10, "pitch_class": 0, "note_name": "C", "is_root": True},
            {"string": 3, "fret": 7, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 3, "fret": 9, "pitch_class": 4, "note_name": "E", "is_root": False},
            {"string": 2, "fret": 8, "pitch_class": 7, "note_name": "G", "is_root": False},
            {"string": 2, "fret": 10, "pitch_class": 9, "note_name": "A", "is_root": False},
            {"string": 1, "fret": 8, "pitch_class": 0, "note_name": "C", "is_root": True},
            {"string": 1, "fret": 10, "pitch_class": 2, "note_name": "D", "is_root": False},
        ]
        self.assertEqual(notes, expected)

    def test_e_key_minor_pent_e_shape_at_fret_12(self):
        """Key E: min fret normalises to 12 (never 0 / open strings)."""
        window_start, notes = theory.resolve_form(
            "minor-pentatonic-e-shape", "E", GENERATED_DIR)
        self.assertEqual(window_start, 12)
        self.assertEqual(
            {n["fret"] for n in notes if n["string"] == 6}, {12, 15})


class ResolveFormErrorTests(SimpleTestCase):
    def test_unknown_form_raises(self):
        with self.assertRaises(ValueError):
            theory.resolve_form("no-such-form", "A")

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            theory.resolve_form("major-scale-1st-finger-form", "H")
