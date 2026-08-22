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

# Expected root fret on the A string for every key (A maps to 12, not 0).
EXPECTED_ROOT_FRETS_LOW_A = {
    "C": 3, "C#": 4, "D": 5, "D#": 6, "E": 7, "F": 8,
    "F#": 9, "G": 10, "G#": 11, "A": 12, "A#": 1, "B": 2,
}

# Expected root fret on the D string for every key (D maps to 12, not 0).
EXPECTED_ROOT_FRETS_LOW_D = {
    "C": 10, "C#": 11, "D": 12, "D#": 1, "E": 2, "F": 3,
    "F#": 4, "G": 5, "G#": 6, "A": 7, "A#": 8, "B": 9,
}

# Expected root fret on the G string for every key (G maps to 12, not 0).
EXPECTED_ROOT_FRETS_LOW_G = {
    "C": 5, "C#": 6, "D": 7, "D#": 8, "E": 9, "F": 10,
    "F#": 11, "G": 12, "G#": 1, "A": 2, "A#": 3, "B": 4,
}

# All 11 shipped scales: id -> (name, intervals, category).
EXPECTED_SCALES = {
    "major_pentatonic": ("Major Pentatonic", [0, 2, 4, 7, 9], "pentatonic"),
    "minor_pentatonic": ("Minor Pentatonic", [0, 3, 5, 7, 10], "pentatonic"),
    "major_arpeggio": ("Major Arpeggio", [0, 4, 7], "arpeggio"),
    "minor_arpeggio": ("Minor Arpeggio", [0, 3, 7], "arpeggio"),
    "major7_arpeggio": ("Major 7 Arpeggio", [0, 4, 7, 11], "arpeggio"),
    "minor7_arpeggio": ("Minor 7 Arpeggio", [0, 3, 7, 10], "arpeggio"),
    "dominant7_arpeggio": ("Dominant 7 Arpeggio", [0, 4, 7, 10], "arpeggio"),
    "minor7b5_arpeggio":
        ("Minor 7b5 Arpeggio", [0, 3, 6, 10], "arpeggio"),
    "diminished7_arpeggio":
        ("Diminished 7 Arpeggio", [0, 3, 6, 9], "arpeggio"),
    "major_scale": ("Major Scale", [0, 2, 4, 5, 7, 9, 11], "scale"),
    "natural_minor_scale":
        ("Natural Minor Scale", [0, 2, 3, 5, 7, 8, 10], "scale"),
}

# Chord Inv. scales: one entry per (chord type, inversion) — a fully
# separate concept from the *_arpeggio scales above (see EXPECTED_SCALES).
_CHORD_TYPES = {
    "major7_chord": ("Major 7", [0, 4, 7, 11]),
    "minor7_chord": ("Minor 7", [0, 3, 7, 10]),
    "dominant7_chord": ("Dominant 7", [0, 4, 7, 10]),
    "minor7b5_chord": ("Minor 7b5", [0, 3, 6, 10]),
    "diminished7_chord": ("Diminished 7", [0, 3, 6, 9]),
}
_INVERSION_SUFFIXES = {0: "0th", 1: "1st", 2: "2nd", 3: "3rd"}
EXPECTED_CHORD_SCALES = {}
for _prefix, (_name, _intervals) in _CHORD_TYPES.items():
    for _n, _ord in _INVERSION_SUFFIXES.items():
        _label = "Root Position" if _n == 0 else f"{_ord} Inversion"
        EXPECTED_CHORD_SCALES[f"{_prefix}_{_ord}_inv"] = (
            f"{_name} — {_label}", _intervals, "chord", _n,
        )


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

    def test_all_flat_keys_map_to_pitch_classes(self):
        expected = {"Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10}
        self.assertEqual(set(theory.FLAT_KEYS), set(expected))
        for key, pc in expected.items():
            with self.subTest(key=key):
                self.assertEqual(theory.key_to_pc(key), pc)

    def test_enharmonic_maps_are_consistent(self):
        """SHARP_TO_FLAT / FLAT_TO_SHARP are inverse bijections over the 5
        accidental pitch classes, and each pair shares a pitch class."""
        self.assertEqual(len(theory.SHARP_TO_FLAT), 5)
        self.assertEqual(
            {theory.FLAT_TO_SHARP[f]: f for f in theory.FLAT_TO_SHARP},
            theory.SHARP_TO_FLAT,
        )
        for sharp, flat in theory.SHARP_TO_FLAT.items():
            with self.subTest(sharp=sharp, flat=flat):
                self.assertEqual(theory.key_to_pc(sharp),
                                 theory.key_to_pc(flat))
                self.assertIn(sharp, theory.KEYS)
                self.assertNotIn(flat, theory.KEYS)

    def test_valid_keys_is_sharps_plus_flats(self):
        self.assertEqual(theory.VALID_KEYS,
                         theory.KEYS + theory.FLAT_KEYS)
        self.assertEqual(len(theory.VALID_KEYS), 17)

    def test_unknown_key_raises(self):
        # 'Cb'/'E#' are real spellings but not offered as keys; 'Bbb' is a
        # double flat. All must be rejected as keys.
        for bad in ("H", "Cb", "E#", "Bbb", "", "a", "bb", None, 5):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    theory.key_to_pc(bad)


class NoteNameParsingTests(SimpleTestCase):
    def test_parse_note_name(self):
        cases = {
            "C": ("C", 0), "G": ("G", 0),
            "C#": ("C", 1), "F#": ("F", 1), "E#": ("E", 1),
            "Gb": ("G", -1), "Cb": ("C", -1), "Fb": ("F", -1),
            "F##": ("F", 2), "Bbb": ("B", -2),
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(theory.parse_note_name(name), expected)

    def test_parse_invalid_raises(self):
        for bad in ("", "H", "c", "B#b", "Cx", "#", "b", None, 3, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    theory.parse_note_name(bad)

    def test_note_name_to_pc_all_spellings(self):
        cases = {
            # naturals
            "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
            # sharps
            "C#": 1, "D#": 3, "F#": 6, "G#": 8, "A#": 10,
            # flats
            "Db": 1, "Eb": 3, "Gb": 6, "Ab": 8, "Bb": 10,
            # enharmonic edge spellings (wrap both ways round the octave)
            "Cb": 11, "Fb": 4, "E#": 5, "B#": 0,
            # double accidentals
            "F##": 7, "Bbb": 9, "Cbb": 10, "B##": 1,
        }
        for name, pc in cases.items():
            with self.subTest(name=name):
                self.assertEqual(theory.note_name_to_pc(name), pc)


class SpellingTests(SimpleTestCase):
    """Diatonic spelling of scales — pc -> name maps per key."""

    MAJOR = [0, 2, 4, 5, 7, 9, 11]

    # Every flat key's major scale, spelled exactly (Gb includes Cb).
    EXPECTED_FLAT_MAJOR = {
        "Db": ["Db", "Eb", "F", "Gb", "Ab", "Bb", "C"],
        "Eb": ["Eb", "F", "G", "Ab", "Bb", "C", "D"],
        "Gb": ["Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"],
        "Ab": ["Ab", "Bb", "C", "Db", "Eb", "F", "G"],
        "Bb": ["Bb", "C", "D", "Eb", "F", "G", "A"],
    }

    def test_flat_major_scales_spelled_exactly(self):
        for key, names in self.EXPECTED_FLAT_MAJOR.items():
            with self.subTest(key=key):
                root_pc = theory.key_to_pc(key)
                spelling = theory.spell_scale(key, self.MAJOR)
                got = [spelling[(root_pc + i) % 12] for i in self.MAJOR]
                self.assertEqual(got, names)

    def test_spelled_names_keep_their_pitch_classes(self):
        """Round-trip: every spelled name maps back to its pitch class."""
        for key in theory.VALID_KEYS:
            with self.subTest(key=key):
                for pc, name in theory.spell_scale(key, self.MAJOR).items():
                    self.assertEqual(theory.note_name_to_pc(name), pc)

    def test_seven_distinct_letters_per_major_key(self):
        """Diatonic spelling uses each letter exactly once."""
        for key in theory.VALID_KEYS:
            with self.subTest(key=key):
                letters = [name[0] for name
                           in theory.spell_scale(key, self.MAJOR).values()]
                self.assertEqual(sorted(letters), sorted("ABCDEFG"))

    def test_sharp_key_spelling_examples(self):
        # A major, the example key: no surprises.
        self.assertEqual(
            sorted(theory.spell_scale("A", self.MAJOR).values()),
            sorted(["A", "B", "C#", "D", "E", "F#", "G#"]),
        )
        # F# major spelled from F# uses E# (the chromatic table can't).
        self.assertIn("E#", theory.spell_scale("F#", self.MAJOR).values())

    def test_spell_interval_tritone_is_diminished_fifth(self):
        self.assertEqual(theory.spell_interval("Bb", 6), "Fb")
        self.assertEqual(theory.spell_interval("C", 6), "Gb")

    def test_spell_interval_wraps_mod_12(self):
        self.assertEqual(theory.spell_interval("Gb", 5),
                         theory.spell_interval("Gb", 17))

    def test_spell_interval_invalid_interval_raises(self):
        for bad in ("2", 2.0, None, True):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    theory.spell_interval("Gb", bad)


class AnchorFretTests(SimpleTestCase):
    def test_root_low_e_all_12_keys(self):
        """Every key, including the E -> 12 (not 0) edge case."""
        self.assertEqual(set(EXPECTED_ROOT_FRETS), set(theory.KEYS))
        for key, fret in EXPECTED_ROOT_FRETS.items():
            with self.subTest(key=key):
                self.assertEqual(theory.anchor_fret(key, "root_low_e"), fret)

    def test_root_low_a_all_12_keys(self):
        """Every key, including the A -> 12 (not 0) edge case."""
        self.assertEqual(set(EXPECTED_ROOT_FRETS_LOW_A), set(theory.KEYS))
        for key, fret in EXPECTED_ROOT_FRETS_LOW_A.items():
            with self.subTest(key=key):
                self.assertEqual(theory.anchor_fret(key, "root_low_a"), fret)

    def test_flat_keys_match_sharp_equivalents(self):
        for anchor in theory.ANCHOR_STRATEGIES:
            for sharp, flat in theory.SHARP_TO_FLAT.items():
                with self.subTest(anchor=anchor, sharp=sharp, flat=flat):
                    self.assertEqual(theory.anchor_fret(flat, anchor),
                                     theory.anchor_fret(sharp, anchor))

    def test_unknown_key_raises(self):
        for anchor in theory.ANCHOR_STRATEGIES:
            with self.subTest(anchor=anchor):
                with self.assertRaises(ValueError):
                    theory.anchor_fret("X", anchor)

    def test_anchor_fret_root_low_d_all_12_keys(self):
        """Every key, including the D -> 12 (not 0) edge case (the D-shape
        CAGED boxes anchor on the D string)."""
        self.assertEqual(set(EXPECTED_ROOT_FRETS_LOW_D), set(theory.KEYS))
        for key, fret in EXPECTED_ROOT_FRETS_LOW_D.items():
            with self.subTest(key=key):
                self.assertEqual(theory.anchor_fret(key, "root_low_d"), fret)

    def test_anchor_fret_root_low_g_all_12_keys(self):
        """Every key, including the G -> 12 (not 0) edge case (the G-shape
        CAGED boxes anchor on the G string)."""
        self.assertEqual(set(EXPECTED_ROOT_FRETS_LOW_G), set(theory.KEYS))
        for key, fret in EXPECTED_ROOT_FRETS_LOW_G.items():
            with self.subTest(key=key):
                self.assertEqual(theory.anchor_fret(key, "root_low_g"), fret)

    def test_unknown_anchor_strategy_raises(self):
        with self.assertRaises(ValueError):
            theory.anchor_fret("A", "caged")


class ScaleIntervalTests(SimpleTestCase):
    def test_all_scales_literal(self):
        scales = theory.load_scales()
        expected = {**EXPECTED_SCALES,
                    **{k: v[:3] for k, v in EXPECTED_CHORD_SCALES.items()}}
        self.assertEqual(set(scales), set(expected))
        for scale_id, (name, intervals, category) in expected.items():
            with self.subTest(scale=scale_id):
                self.assertEqual(scales[scale_id]["name"], name)
                self.assertEqual(scales[scale_id]["intervals"], intervals)
                self.assertEqual(scales[scale_id]["category"], category)

    def test_chord_scales_carry_inversion(self):
        scales = theory.load_scales()
        for scale_id, (_, _, _, inversion) in EXPECTED_CHORD_SCALES.items():
            with self.subTest(scale=scale_id):
                self.assertEqual(scales[scale_id]["inversion"], inversion)
                self.assertIn(scales[scale_id]["menu_group"], theory.MENU_GROUPS)

    def test_scale_names(self):
        expected_names = (
            [name for name, _, _ in EXPECTED_SCALES.values()]
            + [name for name, _, _, _ in EXPECTED_CHORD_SCALES.values()]
        )
        self.assertEqual(sorted(theory.scale_names()), sorted(expected_names))


class TabRoundTripTests(SimpleTestCase):
    """Resolving any form in the example key must reproduce its authored TAB
    verbatim — the diagrams are built FROM the TAB, never the reverse."""

    def test_example_key_resolution_reproduces_authored_tab(self):
        for form_id, form in theory.load_fingerings().items():
            with self.subTest(form=form_id):
                _, notes = theory.resolve_form(form_id, theory.EXAMPLE_KEY)
                expected = {
                    theory.TAB_STRINGS[label]: frets
                    for label, frets in form["tab"].items()
                    if frets  # skipped strings produce no notes
                }
                self.assertEqual(frets_by_string(notes), expected)

    def test_no_note_sounds_below_the_low_root(self):
        """Scale/arpeggio only. CAGED boxes and chord forms are exempt."""
        for form_id, form in theory.load_fingerings().items():
            if form["category"] in theory.CAGED_CATEGORIES:
                continue
            if form["category"] == "chord":
                continue
            with self.subTest(form=form_id):
                root_string = theory.ANCHOR_ROOT_STRINGS[form["anchor"]]
                root_abs = (theory.STRING_BASE_SEMITONES[root_string]
                            + theory.anchor_fret(theory.EXAMPLE_KEY,
                                                 form["anchor"]))
                for label, frets in form["tab"].items():
                    string = theory.TAB_STRINGS[label]
                    base = theory.STRING_BASE_SEMITONES[string]
                    for fret in frets:
                        self.assertGreaterEqual(base + fret, root_abs)


class ARootFormLiteralTests(SimpleTestCase):
    """The A-string-root major-scale forms against the hand-verified TABs
    from the source PDF ('A major scale, six different scale forms')."""

    maxDiff = None

    def test_a_root_1st_finger_form_in_a_matches_the_pdf(self):
        window_start, notes = theory.resolve_form(
            "major-scale-a-root-1st-finger-form", "A")
        self.assertEqual(window_start, 12)
        self.assertEqual(frets_by_string(notes), {
            5: [12, 14, 16], 4: [12, 14, 16], 3: [13, 14, 16],
            2: [14, 15, 17], 1: [14, 16, 17],
        })

    def test_a_root_2nd_finger_form_in_a_matches_the_pdf(self):
        window_start, notes = theory.resolve_form(
            "major-scale-a-root-2nd-finger-form", "A")
        self.assertEqual(window_start, 10)
        self.assertEqual(frets_by_string(notes), {
            5: [12, 14], 4: [11, 12, 14], 3: [11, 13, 14],
            2: [12, 14], 1: [10, 12, 14],
        })

    def test_a_root_4th_finger_form_in_a_matches_the_pdf(self):
        window_start, notes = theory.resolve_form(
            "major-scale-a-root-4th-finger-form", "A")
        self.assertEqual(window_start, 9)
        self.assertEqual(frets_by_string(notes), {
            5: [12], 4: [9, 11, 12], 3: [9, 11],
            2: [9, 10, 12], 1: [9, 10, 12],
        })

    def test_a_root_forms_never_touch_the_low_e_string(self):
        for form_id in ("major-scale-a-root-1st-finger-form",
                        "major-scale-a-root-2nd-finger-form",
                        "major-scale-a-root-4th-finger-form"):
            for key in theory.KEYS:
                with self.subTest(form=form_id, key=key):
                    _, notes = theory.resolve_form(form_id, key)
                    self.assertNotIn(6, {n["string"] for n in notes})

    def test_up_shift_b_key_4th_finger_a_root_form(self):
        # B anchors at A-string fret 2; min offset -3 gives raw min fret
        # -1, so the whole form shifts UP an octave (anchor 14).
        window_start, notes = theory.resolve_form(
            "major-scale-a-root-4th-finger-form", "B")
        self.assertEqual(window_start, 11)
        self.assertEqual(frets_by_string(notes), {
            5: [14], 4: [11, 13, 14], 3: [11, 13],
            2: [11, 12, 14], 1: [11, 12, 14],
        })

    def test_no_shift_e_key_1st_finger_a_root_form(self):
        # E anchors at A-string fret 7; offsets 0..5 keep frets 7-12.
        window_start, notes = theory.resolve_form(
            "major-scale-a-root-1st-finger-form", "E")
        self.assertEqual(window_start, 7)
        self.assertEqual(frets_by_string(notes), {
            5: [7, 9, 11], 4: [7, 9, 11], 3: [8, 9, 11],
            2: [9, 10, 12], 1: [9, 11, 12],
        })


class ResolveFormExhaustiveTests(SimpleTestCase):
    """Every shipped form x all 12 keys, every note verified independently."""

    def test_every_form_every_key(self):
        fingerings = theory.load_fingerings()
        scales = theory.load_scales()
        self.assertEqual(len(fingerings), 80)
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
    for valid forms: the authored TAB must contain the root on its anchor
    string, so the minimum offset is always <= 0 and anchor + min_offset
    <= 12.)
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
        """Three-notes-per-string from the root."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-1st-finger-form", "A")
        self.assertEqual(window_start, 5)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 7, 9], 5: [5, 7, 9], 4: [6, 7, 9],
            3: [6, 7, 9], 2: [7, 9, 10], 1: [7, 9, 10],
        })

    def test_a_major_2nd_finger_form_frets_per_string(self):
        """Position form: E[5,7], A[4,5,7], …"""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-2nd-finger-form", "A")
        self.assertEqual(window_start, 4)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 7], 5: [4, 5, 7], 4: [4, 6, 7],
            3: [4, 6, 7], 2: [5, 7], 1: [4, 5],
        })

    def test_a_minor_pentatonic_e_shape_ground_truth(self):
        """The classic minor pentatonic box 1 in A, frets per string:
        E[5,8], A[5,7], D[5,7], G[5,7], B[5,8], e[5,8]."""
        window_start, notes = theory.resolve_form(
            "minor-pentatonic-e-shape", "A")
        self.assertEqual(window_start, 5)
        self.assertEqual(frets_by_string(notes), {
            6: [5, 8], 5: [5, 7], 4: [5, 7],
            3: [5, 7], 2: [5, 8], 1: [5, 8],
        })
        self.assertEqual({n["note_name"] for n in notes},
                         {"A", "C", "D", "E", "G"})

    def test_c_minor_pentatonic_g_shape_frets_per_string(self):
        """The wrap-around box: G-shape anchored on the G-string root
        (fret 5 in C), one box below C's root-position E shape."""
        window_start, notes = theory.resolve_form(
            "minor-pentatonic-g-shape", "C")
        self.assertEqual(window_start, 5)
        self.assertEqual(frets_by_string(notes), {
            6: [6, 8], 5: [6, 8], 4: [5, 8],
            3: [5, 8], 2: [6, 8], 1: [6, 8],
        })
        self.assertEqual({n["note_name"] for n in notes},
                         {"C", "D#", "F", "G", "A#"})

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


class FlatKeyResolveTests(SimpleTestCase):
    """resolve_form in every flat key, for every shipped form.

    A flat key must produce the *identical* fretboard (same strings, frets,
    pitch classes, roots) as its sharp equivalent — only the note names
    change, and they change to the correct diatonic flat spelling.
    """

    maxDiff = None

    # Full major-scale spellings per flat key (Gb includes Cb, never B).
    EXPECTED_MAJOR_NAMES = {
        "Db": {"Db", "Eb", "F", "Gb", "Ab", "Bb", "C"},
        "Eb": {"Eb", "F", "G", "Ab", "Bb", "C", "D"},
        "Gb": {"Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"},
        "Ab": {"Ab", "Bb", "C", "Db", "Eb", "F", "G"},
        "Bb": {"Bb", "C", "D", "Eb", "F", "G", "A"},
    }

    def test_every_form_every_flat_key(self):
        scales = theory.load_scales()
        for form_id, form in theory.load_fingerings().items():
            intervals = scales[form["scale"]]["intervals"]
            for flat, sharp in theory.FLAT_TO_SHARP.items():
                with self.subTest(form=form_id, key=flat):
                    sharp_start, sharp_notes = theory.resolve_form(
                        form_id, sharp)
                    flat_start, flat_notes = theory.resolve_form(
                        form_id, flat)

                    # Same window, same physical notes.
                    self.assertEqual(flat_start, sharp_start)
                    strip = lambda ns: [
                        {k: v for k, v in n.items() if k != "note_name"}
                        for n in ns
                    ]
                    self.assertEqual(strip(flat_notes), strip(sharp_notes))

                    # Forms are complete (every interval appears — enforced
                    # at load time), so the name set is exactly the scale's
                    # diatonic spelling in the flat key.
                    self.assertEqual(
                        {n["note_name"] for n in flat_notes},
                        set(theory.spell_scale(flat, intervals).values()),
                    )
                    # Spelling is internally consistent: every name maps
                    # back to its own pitch class.
                    for n in flat_notes:
                        self.assertEqual(
                            theory.note_name_to_pc(n["note_name"]),
                            n["pitch_class"],
                        )
                        self.assertEqual(
                            n["is_root"],
                            n["pitch_class"] == theory.key_to_pc(flat),
                        )

    def test_flat_major_forms_spell_the_expected_names(self):
        """Literal spellings for the major-scale forms in every flat key."""
        for form_id, form in theory.load_fingerings().items():
            if form["scale"] != "major_scale":
                continue
            for flat, names in self.EXPECTED_MAJOR_NAMES.items():
                with self.subTest(form=form_id, key=flat):
                    _, notes = theory.resolve_form(form_id, flat)
                    self.assertEqual({n["note_name"] for n in notes}, names)

    def test_gb_major_spells_cb_not_b(self):
        """The pitch class 11 note in Gb major must be Cb."""
        for form_id, form in theory.load_fingerings().items():
            if form["scale"] != "major_scale":
                continue
            with self.subTest(form=form_id):
                _, notes = theory.resolve_form(form_id, "Gb")
                pc11 = {n["note_name"] for n in notes
                        if n["pitch_class"] == 11}
                self.assertEqual(pc11, {"Cb"})

    def test_sharp_keys_still_use_sharp_chromatic_names(self):
        """The 50% sharp presentation is byte-identical to the old output."""
        for form_id in theory.load_fingerings():
            for key in theory.KEYS:
                with self.subTest(form=form_id, key=key):
                    _, notes = theory.resolve_form(form_id, key)
                    for n in notes:
                        self.assertEqual(
                            n["note_name"],
                            theory.NOTE_NAMES[n["pitch_class"]],
                        )

    def test_bb_major_4th_finger_form_ground_truth(self):
        """Hand-checked fixture: Bb major, 4th finger form — the A#
        fixture's fretboard with flat spellings (anchor fret 6)."""
        window_start, notes = theory.resolve_form(
            "major-scale-e-root-4th-finger-form", "Bb")
        self.assertEqual(window_start, 2)
        expected = [
            {"string": 6, "fret": 6, "pitch_class": 10, "note_name": "Bb", "is_root": True},
            {"string": 5, "fret": 3, "pitch_class": 0, "note_name": "C", "is_root": False},
            {"string": 5, "fret": 5, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 5, "fret": 6, "pitch_class": 3, "note_name": "Eb", "is_root": False},
            {"string": 4, "fret": 3, "pitch_class": 5, "note_name": "F", "is_root": False},
            {"string": 4, "fret": 5, "pitch_class": 7, "note_name": "G", "is_root": False},
            {"string": 3, "fret": 2, "pitch_class": 9, "note_name": "A", "is_root": False},
            {"string": 3, "fret": 3, "pitch_class": 10, "note_name": "Bb", "is_root": True},
            {"string": 3, "fret": 5, "pitch_class": 0, "note_name": "C", "is_root": False},
            {"string": 2, "fret": 3, "pitch_class": 2, "note_name": "D", "is_root": False},
            {"string": 2, "fret": 4, "pitch_class": 3, "note_name": "Eb", "is_root": False},
            {"string": 2, "fret": 6, "pitch_class": 5, "note_name": "F", "is_root": False},
            {"string": 1, "fret": 3, "pitch_class": 7, "note_name": "G", "is_root": False},
            {"string": 1, "fret": 5, "pitch_class": 9, "note_name": "A", "is_root": False},
            {"string": 1, "fret": 6, "pitch_class": 10, "note_name": "Bb", "is_root": True},
        ]
        self.assertEqual(notes, expected)


class ResolveFormErrorTests(SimpleTestCase):
    def test_unknown_form_raises(self):
        with self.assertRaises(ValueError):
            theory.resolve_form("no-such-form", "A")

    def test_unknown_key_raises(self):
        with self.assertRaises(ValueError):
            theory.resolve_form("major-scale-e-root-1st-finger-form", "H")
