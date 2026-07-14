"""Exhaustive tests for the music theory engine (practice/theory.py).

Fingering forms are hand-authored TABs in the fixed example key A (the
source of truth — convention can't be derived from interval math), so the
tests here verify the engine against the shipped forms plus hand-written
expected outputs, including Fraser's verified 4th-finger-form TAB.
"""

from django.test import SimpleTestCase

from practice import theory

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


class TabRoundTripTests(SimpleTestCase):
    """Resolving any form in the example key must reproduce its authored TAB
    verbatim — the diagrams are built FROM the TAB, never the reverse."""

    def test_example_key_resolution_reproduces_authored_tab(self):
        for form_id, form in theory.load_fingerings().items():
            with self.subTest(form=form_id):
                self.assertEqual(form["example_key"], theory.EXAMPLE_KEY)
                _, notes = theory.resolve_form(form_id, theory.EXAMPLE_KEY)
                expected = {
                    theory.TAB_STRINGS[label]: frets
                    for label, frets in form["tab"].items()
                }
                self.assertEqual(frets_by_string(notes), expected)

    def test_no_note_sounds_below_the_low_root(self):
        """'Start on the root' convention, re-checked post-load."""
        for form_id, form in theory.load_fingerings().items():
            with self.subTest(form=form_id):
                root_abs = 5  # low E fret 5 = A, the example-key root
                for label, frets in form["tab"].items():
                    string = theory.TAB_STRINGS[label]
                    base = theory.STRING_BASE_SEMITONES[string]
                    for fret in frets:
                        self.assertGreaterEqual(base + fret, root_abs)


class ResolveFormExhaustiveTests(SimpleTestCase):
    """Every shipped form x all 12 keys, every note verified independently."""

    def test_every_form_every_key(self):
        fingerings = theory.load_fingerings()
        scales = theory.load_scales()
        self.assertEqual(len(fingerings), 3)
        for form_id, form in fingerings.items():
            intervals = set(scales[form["scale"]]["intervals"])
            all_offsets = [o for offs in form["offsets"].values() for o in offs]
            n_declared = len(all_offsets)
            for key in theory.KEYS:
                with self.subTest(form=form_id, key=key):
                    root_pc = theory.key_to_pc(key)
                    anchor = normalised_anchor(key, form)
                    window_start, notes = theory.resolve_form(form_id, key)

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
        """Ascending play order: string 6 first, frets ascending — the TAB
        renderer relies on this ordering."""
        for form_id in theory.load_fingerings():
            with self.subTest(form=form_id):
                _, notes = theory.resolve_form(form_id, "A")
                order = [(n["string"], n["fret"]) for n in notes]
                self.assertEqual(
                    order, sorted(order, key=lambda sf: (-sf[0], sf[1])))


class OctaveNormalisationTests(SimpleTestCase):
    """The whole form shifts by octaves until its lowest fret is in [1, 12].

    Open strings (fret 0) are never allowed. (A downward shift can't occur
    for valid forms any more: the authored TAB must contain the low-E root,
    so the minimum offset is always <= 0 and anchor + min_offset <= 12.)
    """

    maxDiff = None

    def test_up_shift_f_major_4th_finger_form(self):
        # F anchors at fret 1; min offset -4 gives raw min fret -3, so the
        # whole form shifts UP an octave (anchor 13): frets 9-13.
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-4th-finger-form", "F")
        self.assertEqual(window_start, 9)
        self.assertEqual(frets_by_string(notes), {
            6: [13], 5: [10, 12, 13], 4: [10, 12],
            3: [9, 10, 12], 2: [10, 11, 13], 1: [10, 12, 13],
        })

    def test_e_key_1st_finger_form_anchors_at_12(self):
        """Key E: anchor normalises to 12, never 0 / open strings."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-1st-finger-form", "E")
        self.assertEqual(window_start, 12)
        self.assertEqual(
            {n["fret"] for n in notes if n["string"] == 6}, {12, 14, 16})

    def test_no_shift_when_min_fret_already_in_range(self):
        # A anchors at fret 5; the 4th finger form reaches down to fret 1
        # (G string) — still >= 1, so no shift.
        window_start, _ = theory.resolve_form(
            "major-scale-e-root-4th-finger-form", "A")
        self.assertEqual(window_start, 1)

    def test_min_fret_in_1_to_12_for_every_form_and_key(self):
        for form_id in theory.load_fingerings():
            for key in theory.KEYS:
                with self.subTest(form=form_id, key=key):
                    window_start, notes = theory.resolve_form(form_id, key)
                    min_fret = min(n["fret"] for n in notes)
                    self.assertEqual(window_start, min_fret)
                    self.assertGreaterEqual(min_fret, 1)
                    self.assertLessEqual(min_fret, 12)


class HandVerifiedFixtureTests(SimpleTestCase):
    """Complete hand-written expected outputs, compared exactly."""

    maxDiff = None

    def test_a_major_4th_finger_form_ground_truth(self):
        """Fraser's verified conventional TAB, note for note:
        E[5], A[2,4,5], D[2,4], G[1,2,4], B[2,3,5], e[2,4,5]."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-4th-finger-form", "A")
        self.assertEqual(window_start, 1)
        expected = [
            {"string": 6, "fret": 5, "pitch_class": 9, "note_name": "A", "is_root": True},
            {"string": 5, "fret": 2, "pitch_class": 11, "note_name": "B", "is_root": False},
            {"string": 5, "fret": 4, "pitch_class": 1, "note_name": "C#", "is_root": False},
            {"string": 5, "fret": 5, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 4, "fret": 2, "pitch_class": 4, "note_name": "E", "is_root": False},
            {"string": 4, "fret": 4, "pitch_class": 6, "note_name": "F#", "is_root": False},
            {"string": 3, "fret": 1, "pitch_class": 8, "note_name": "G#", "is_root": False},
            {"string": 3, "fret": 2, "pitch_class": 9, "note_name": "A", "is_root": True},
            {"string": 3, "fret": 4, "pitch_class": 11, "note_name": "B", "is_root": False},
            {"string": 2, "fret": 2, "pitch_class": 1, "note_name": "C#", "is_root": False},
            {"string": 2, "fret": 3, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 2, "fret": 5, "pitch_class": 4, "note_name": "E", "is_root": False},
            {"string": 1, "fret": 2, "pitch_class": 6, "note_name": "F#", "is_root": False},
            {"string": 1, "fret": 4, "pitch_class": 8, "note_name": "G#", "is_root": False},
            {"string": 1, "fret": 5, "pitch_class": 9, "note_name": "A", "is_root": True},
        ]
        self.assertEqual(notes, expected)

    def test_a_major_1st_finger_form_frets_per_string(self):
        """Three-notes-per-string from the root (DRAFT form)."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-1st-finger-form", "A")
        self.assertEqual(window_start, 5)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 7, 9], 5: [5, 7, 9], 4: [6, 7, 9],
            3: [6, 7, 9], 2: [7, 9, 10], 1: [7, 9, 10],
        })

    def test_a_major_2nd_finger_form_frets_per_string(self):
        """Position form: E[5,7], A[4,5,7], … (DRAFT form)."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-2nd-finger-form", "A")
        self.assertEqual(window_start, 4)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 7], 5: [4, 5, 7], 4: [4, 6, 7],
            3: [4, 6, 7], 2: [5, 7], 1: [4, 5],
        })

    def test_c_major_2nd_finger_form_frets_per_string(self):
        """Transposition: same shape anchored at C (fret 8)."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-2nd-finger-form", "C")
        self.assertEqual(window_start, 7)
        self.assertEqual(frets_by_string(notes), {
            6: [8, 10], 5: [7, 8, 10], 4: [7, 9, 10],
            3: [7, 9, 10], 2: [8, 10], 1: [7, 8],
        })
        # All 7 notes of C major, no accidentals.
        self.assertEqual({n["note_name"] for n in notes},
                         {"C", "D", "E", "F", "G", "A", "B"})


class ResolveFormErrorTests(SimpleTestCase):
    def test_unknown_form_raises(self):
        with self.assertRaises(ValueError):
            theory.resolve_form("no-such-form", "A")

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            theory.resolve_form("major-scale-e-root-1st-finger-form", "H")
