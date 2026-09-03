"""Tests for the page and API endpoints."""

from unittest import mock

from django.test import TestCase

import random

from practice import theory

ROUND_KEYS = {"scale", "key", "direction", "form_id",
              "category", "display_label", "caged_shape", "starting_finger",
              "window_start", "notes"}
NOTE_KEYS = {"string", "fret", "pitch_class", "note_name", "is_root"}


class IndexPageTests(TestCase):
    def test_index_renders_start_screen(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="start-screen"', html)
        self.assertIn('aria-label="Timer length"', html)
        self.assertIn('id="start-btn"', html)
        # 7-string is still promised (hover hint on the disabled segment).
        self.assertIn('title="Coming soon"', html)
        # The title h1 is the click-to-menu hook wrapping the SVG wordmark.
        self.assertIn("<title>ScaleRunner</title>", html)
        self.assertIn('<h1 class="app-title" title="Back to menu">', html)
        self.assertIn('aria-label="ScaleRunner"', html)
        self.assertIn('role="img"', html)
        self.assertIn(">Scale</tspan>", html)
        self.assertIn(">Runner</tspan>", html)

    def test_index_has_round_header_hooks(self):
        """Round header slots + keyboard tip on the start menu."""
        html = self.client.get("/").content.decode()
        self.assertIn('id="round-label"', html)
        self.assertIn('id="round-direction"', html)
        self.assertIn("Tip: during a round", html)
        self.assertIn("for correct", html)
        self.assertIn("for incorrect", html)
        self.assertIn('id="tab"', html)

    def test_index_strings_segmented_control(self):
        """6 is the checked default; 7 is disabled with a soon badge."""
        html = self.client.get("/").content.decode()
        self.assertIn('role="radiogroup"', html)
        six = html.index('id="strings-6"')
        seven = html.index('id="strings-7"')
        self.assertIn('value="6"', html[six:six + 80])
        self.assertIn("checked", html[six:six + 80])
        self.assertIn('value="7"', html[seven:seven + 80])
        self.assertIn("disabled", html[seven:seven + 80])
        self.assertIn(">soon</span>", html)

    @staticmethod
    def playable_scale_ids():
        """Scale ids with >= 1 loaded fingering form — the only ones the
        exercise picker offers (major/minor arpeggio are config-defined
        but have no shipped fingering forms)."""
        return {form["scale"] for form in theory.load_fingerings().values()}

    def test_index_exercise_checkboxes_match_config(self):
        """One checkbox per playable non-chord scale; chord scales bundle
        one checkbox per menu_group instead (see the test below)."""
        html = self.client.get("/").content.decode()
        scales = theory.load_scales()
        playable = self.playable_scale_ids()
        non_chord = {s for s in playable if scales[s]["category"] != "chord"}
        chord_groups = {scales[s]["menu_group"] for s in playable
                        if scales[s]["category"] == "chord"}
        self.assertEqual(html.count('class="exercise-checkbox"'),
                         len(non_chord) + len(chord_groups))
        for scale_id in scales:
            if scales[scale_id]["category"] == "chord":
                continue
            with self.subTest(scale=scale_id):
                if scale_id in playable:
                    idx = html.index(f'value="{scale_id}"')
                    self.assertIn("checked", html[idx:idx + 60])
                else:
                    self.assertNotIn(f'value="{scale_id}"', html)

    def test_index_exercise_group_membership_and_order(self):
        """Scales group (pentatonic + scale categories) before Arpeggios;
        names in config order within each group."""
        html = self.client.get("/").content.decode()
        scales_at = html.index(">Scales</button>")
        arps_at = html.index(">Arpeggios</button>")
        self.assertLess(scales_at, arps_at)
        playable = self.playable_scale_ids()
        last = scales_at
        for scale_id, spec in theory.load_scales().items():
            if spec["category"] in ("arpeggio", "chord") or scale_id not in playable:
                continue
            at = html.index(f">{spec['name']}</span>")
            self.assertGreater(at, last, scale_id)
            self.assertLess(at, arps_at, scale_id)
            last = at
        last = arps_at
        for scale_id, spec in theory.load_scales().items():
            if spec["category"] != "arpeggio" or scale_id not in playable:
                continue
            at = html.index(
                f">{spec['name'].removesuffix(' Arpeggio')}</span>")
            self.assertGreater(at, last, scale_id)
            last = at

    def test_index_arpeggio_suffix_stripped(self):
        """Inside the Arpeggios group the redundant suffix is dropped
        ("Major 7 Arpeggio" renders as "Major 7"); Scales names stay full.
        Chord Inv. scales don't get an individual checkbox at all — they're
        bundled into one "Core Diatonic"/"Altered" checkbox per menu_group
        (see test_index_chord_scales_bundled_by_menu_group)."""
        html = self.client.get("/").content.decode()
        playable = self.playable_scale_ids()
        for scale_id, spec in theory.load_scales().items():
            if scale_id not in playable or spec["category"] == "chord":
                continue
            with self.subTest(scale=scale_id):
                if spec["category"] == "arpeggio":
                    stripped = spec["name"].removesuffix(" Arpeggio")
                    self.assertIn(f">{stripped}</span>", html)
                    self.assertNotIn(spec["name"], html)
                else:
                    self.assertIn(f">{spec['name']}</span>", html)

    def test_index_chord_scales_bundled_by_menu_group(self):
        """Chord Inv. has one checkbox per menu_group with playable
        content ("Core Diatonic", not one per chord type/inversion); its
        value is every playable scale id in that group, comma-joined —
        exactly what /api/round/?scales= already accepts."""
        html = self.client.get("/").content.decode()
        chord_inv_at = html.index(">Chord Inv.</button>")
        section_end = html.index('id="start-wrap"', chord_inv_at)
        section = html[chord_inv_at:section_end]
        self.assertIn(">Core Diatonic</span>", section)
        self.assertNotIn("Major 7 Chord", html)
        idx = section.index('value="')
        value = section[idx + 7:section.index('"', idx + 7)]
        ids = value.split(",")
        self.assertIn("major7_chord_0th_inv", ids)
        for scale_id in ids:
            self.assertEqual(
                theory.load_scales()[scale_id]["menu_group"], "core_diatonic")

    def test_index_exercise_hint_and_headings(self):
        html = self.client.get("/").content.decode()
        idx = html.index('id="exercise-hint"')
        self.assertIn("hidden", html[idx:idx + 120])  # hidden by default
        self.assertIn("Pick at least one exercise", html)
        self.assertIn(">Practice Exercises</span>", html)

    def test_index_panel_order(self):
        """Timer -> Strings -> Practice Exercises -> Start."""
        html = self.client.get("/").content.decode()
        order = [html.index('id="timer-1"'),
                 html.index('id="strings-6"'),
                 html.index("Practice Exercises"),
                 html.index('id="start-btn"')]
        self.assertEqual(order, sorted(order))


class ValidRoundMixin:
    """Full-schema validation of one /api/round/ payload, shared by the
    plain round tests and the ?scales= filter tests."""

    def assert_valid_round(self, data):
        fingerings = theory.load_fingerings()
        scales = theory.load_scales()

        self.assertEqual(set(data), ROUND_KEYS)
        self.assertIn(data["scale"], theory.scale_names())
        self.assertIn(data["key"], theory.VALID_KEYS)
        # Chord Inv. rounds carry no direction (all notes reveal at once).
        if data["category"] == "chord":
            self.assertIsNone(data["direction"])
        else:
            self.assertIn(data["direction"], theory.DIRECTIONS)
        self.assertIn(data["form_id"], fingerings)

        form = fingerings[data["form_id"]]
        self.assertEqual(data["scale"], scales[form["scale"]]["name"])

        # Category + display label + XOR-populated caged_shape /
        # starting_finger, consistent with the config.
        self.assertIn(data["category"], theory.CATEGORIES)
        self.assertEqual(data["category"], form["category"])
        self.assertEqual(data["display_label"], form["display_label"])
        self.assertEqual(data["caged_shape"], form["caged_shape"])
        self.assertEqual(data["starting_finger"], form["starting_finger"])
        if data["category"] == "pentatonic":
            self.assertIsInstance(data["caged_shape"], str)
            self.assertIn(data["caged_shape"], theory.CAGED_SHAPES)
            self.assertIsNone(data["starting_finger"])
            self.assertEqual(data["display_label"],
                             f"{data['caged_shape']} Shape")
        elif data["category"] == "chord":
            self.assertIsNone(data["caged_shape"])
            self.assertIsNone(data["starting_finger"])
            root_label = {"root_low_e": "E", "root_low_a": "A",
                          "root_low_d": "D"}[form["anchor"]]
            inversion = scales[form["scale"]]["inversion"]
            self.assertEqual(
                data["display_label"],
                f"{root_label} Root ({theory.ordinal(inversion)} Inversion)")
        else:
            self.assertIsNone(data["caged_shape"])
            self.assertIsInstance(data["starting_finger"], int)
            self.assertIn(data["starting_finger"], (1, 2, 3, 4))
            root_label = {"root_low_e": "E",
                          "root_low_a": "A"}[form["anchor"]]
            self.assertEqual(
                data["display_label"],
                f"{theory.ordinal(data['starting_finger'])} Finger Form "
                f"({root_label}-root)")

        # window_start = the resolved form's lowest fret, in [1, 12]
        # (octave normalisation).
        self.assertGreaterEqual(data["window_start"], 1)
        self.assertLessEqual(data["window_start"], 12)

        # Notes: non-empty, exact key set, correct types, valid values.
        self.assertIsInstance(data["notes"], list)
        self.assertGreater(len(data["notes"]), 0)
        for note in data["notes"]:
            self.assertEqual(set(note), NOTE_KEYS)
            self.assertIsInstance(note["string"], int)
            self.assertIsInstance(note["fret"], int)
            self.assertIsInstance(note["pitch_class"], int)
            self.assertIsInstance(note["note_name"], str)
            self.assertIsInstance(note["is_root"], bool)
            self.assertIn(note["string"], (1, 2, 3, 4, 5, 6))
            self.assertGreaterEqual(note["fret"], 1)
            # Spelling follows the served key: sharp chromatic names for
            # sharp/natural keys, diatonic flat spelling for flat keys —
            # either way the name must denote the note's pitch class.
            self.assertEqual(note["pitch_class"],
                             theory.note_name_to_pc(note["note_name"]))
            if data["key"] in theory.FLAT_KEYS:
                self.assertNotIn("#", note["note_name"])
            else:
                self.assertEqual(note["note_name"],
                                 theory.NOTE_NAMES[note["pitch_class"]])
        self.assertEqual(data["window_start"],
                         min(n["fret"] for n in data["notes"]))

        # Payload must match a direct resolution of the same form + key.
        window_start, notes = theory.resolve_form(data["form_id"], data["key"])
        self.assertEqual(data["window_start"], window_start)
        self.assertEqual(data["notes"], notes)


class RoundApiTests(ValidRoundMixin, TestCase):
    def test_round_ok_and_shape(self):
        resp = self.client.get("/api/round/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assert_valid_round(resp.json())

    def test_round_randomisation_stays_in_domain(self):
        num_forms = len(theory.load_fingerings())
        # Coupon-collector draw count: enough that P(any one form is never
        # drawn) stays negligible as shipped content grows, rather than a
        # fixed count that gets flakier every time a form is added.
        draws = num_forms * 40
        seen = {"scales": set(), "directions": set(), "forms": set(),
                "keys": set(), "categories": set()}
        for _ in range(draws):
            resp = self.client.get("/api/round/")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assert_valid_round(data)
            seen["scales"].add(data["scale"])
            seen["directions"].add(data["direction"])
            seen["forms"].add(data["form_id"])
            seen["keys"].add(data["key"])
            seen["categories"].add(data["category"])
        self.assertEqual(seen["categories"],
                         {"scale", "arpeggio", "pentatonic", "chord"})
        # Chord Inv. rounds carry a null direction instead of Ascending/
        # Descending — both still show up alongside it.
        self.assertEqual(seen["directions"], {"Ascending", "Descending", None})
        self.assertEqual(seen["forms"], set(theory.load_fingerings()))
        self.assertGreaterEqual(len(seen["keys"]), 5)
        # Both accidental spellings get served (flat/sharp coin flip).
        self.assertTrue(seen["keys"] & set(theory.FLAT_KEYS))
        self.assertTrue(seen["keys"] & set(theory.SHARP_TO_FLAT))
        self.assertEqual(seen["scales"], {
            "Major Scale", "Natural Minor Scale",
            "Major 7 Arpeggio", "Dominant 7 Arpeggio",
            "Minor 7 Arpeggio", "Minor 7b5 Arpeggio",
            "Diminished 7 Arpeggio",
            "Major Pentatonic", "Minor Pentatonic",
            "Major 7 Chord", "Minor 7 Chord", "Dominant 7 Chord",
            "Minor 7b5 Chord", "Diminished 7 Chord",
        })

    def test_round_rejects_post(self):
        resp = self.client.post("/api/round/")
        self.assertEqual(resp.status_code, 405)


# A minimal valid chord-category form (major7, 1st inversion, E-root
# anchor — same shape as VALID_CHORD_FORM in test_configs.py, but built
# fresh here rather than imported to keep the two test modules independent).
# No chord fingerings ship yet (pilot content pending), so these tests
# patch theory.load_fingerings() to exercise the category=="chord" branch
# of api_round ahead of real content landing.
_CHORD_FORM_RAW = {
    "id": "test-chord-form",
    "scale": "major7_chord_1st_inv",
    "name": "Test Chord Form",
    "anchor": "root_low_e",
    "example_key": "A",
    "tab": {
        "E": [9], "A": [7], "D": [6, 7], "G": [6, 9], "B": [9, 10], "e": [],
    },
}


# Captured once, before any test patches theory.load_fingerings — the
# side_effect below must not call the (possibly-patched) function itself.
_BASE_FINGERINGS = dict(theory.load_fingerings())
_CHORD_FORM = theory._validate_fingering(
    dict(_CHORD_FORM_RAW), theory.FINGERINGS_DIR / "fake.yaml",
    theory.load_scales())


def _chord_fingerings(*args, **kwargs):
    """Real shipped forms + one synthetic chord form, alone on its scale
    (excludes real forms of that scale so ?scales= stays deterministic)."""
    base = {form_id: form for form_id, form in _BASE_FINGERINGS.items()
            if form["scale"] != _CHORD_FORM["scale"]}
    return {**base, _CHORD_FORM["id"]: _CHORD_FORM}


class ChordRoundApiTests(TestCase):
    """Chord Inv. rounds carry no direction — see api_round."""

    def test_chord_round_has_null_direction(self):
        with mock.patch("practice.theory.load_fingerings",
                         side_effect=_chord_fingerings):
            resp = self.client.get(
                "/api/round/?scales=major7_chord_1st_inv")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["category"], "chord")
        self.assertIsNone(data["direction"])
        self.assertEqual(data["display_label"], "E Root (1st Inversion)")


class RoundKeySpellingTests(TestCase):
    """The 50% flat/sharp presentation of accidental keys.

    api_round draws random.choice(KEYS) then, for accidental roots only,
    random.random() < 0.5 flips to the flat spelling. Both draws are
    mocked to pin each branch deterministically for every accidental key.
    """

    @staticmethod
    def pinned_choice(chosen_key, form_id=None):
        """random.choice replacement keyed by argument, so tests don't
        care how many draws the view makes or in what order."""
        def choose(seq):
            if seq is theory.KEYS:
                return chosen_key
            if seq is theory.DIRECTIONS:
                return "Ascending"
            return form_id or seq[0]  # the form pool
        return choose

    def get_round(self, chosen_key, coin, form_id=None):
        """One /api/round/ with the key draw and flat/sharp coin pinned."""
        with mock.patch("practice.views.random.choice",
                        side_effect=self.pinned_choice(chosen_key, form_id)), \
             mock.patch("practice.views.random.random", return_value=coin):
            resp = self.client.get("/api/round/")
        self.assertEqual(resp.status_code, 200)
        return resp.json()

    def test_every_accidental_key_flat_when_coin_below_half(self):
        for sharp, flat in theory.SHARP_TO_FLAT.items():
            with self.subTest(sharp=sharp):
                data = self.get_round(sharp, coin=0.49999)
                self.assertEqual(data["key"], flat)
                # The whole payload is the flat-key resolution: flat-spelled
                # notes, no sharps anywhere.
                _, notes = theory.resolve_form(data["form_id"], flat)
                self.assertEqual(data["notes"], notes)
                for note in data["notes"]:
                    self.assertNotIn("#", note["note_name"])

    def test_every_accidental_key_sharp_when_coin_at_or_above_half(self):
        for sharp in theory.SHARP_TO_FLAT:
            for coin in (0.5, 0.99999):
                with self.subTest(sharp=sharp, coin=coin):
                    data = self.get_round(sharp, coin=coin)
                    self.assertEqual(data["key"], sharp)
                    for note in data["notes"]:
                        self.assertEqual(
                            note["note_name"],
                            theory.NOTE_NAMES[note["pitch_class"]])

    def test_natural_keys_never_flip_and_never_draw_the_coin(self):
        naturals = [k for k in theory.KEYS if k not in theory.SHARP_TO_FLAT]
        self.assertEqual(len(naturals), 7)
        for key in naturals:
            with self.subTest(key=key):
                with mock.patch("practice.views.random.choice",
                                side_effect=self.pinned_choice(key)), \
                     mock.patch("practice.views.random.random") as coin:
                    resp = self.client.get("/api/round/")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.json()["key"], key)
                coin.assert_not_called()

    def test_gb_round_spells_cb(self):
        """End-to-end: a Gb major-scale round spells exactly the Gb major
        names, Cb included (form pinned — the maj7 arpeggio form has no
        4th degree, so it never contains a Cb)."""
        data = self.get_round(
            "F#", coin=0.0, form_id="major-scale-e-root-1st-finger-form")
        self.assertEqual(data["key"], "Gb")
        self.assertEqual(data["form_id"], "major-scale-e-root-1st-finger-form")
        names = {n["note_name"] for n in data["notes"]}
        self.assertEqual(names, {"Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"})

    def test_gb_maj7_arpeggio_round_spelling(self):
        """The maj7 arpeggio form, flat-spelled end to end:
        Gb maj7 arpeggio = Gb Bb Db F."""
        data = self.get_round(
            "F#", coin=0.0, form_id="major7-arpeggio-e-root-1st-finger-form")
        self.assertEqual(data["key"], "Gb")
        self.assertEqual(data["scale"], "Major 7 Arpeggio")
        self.assertEqual(data["display_label"], "1st Finger Form (E-root)")
        names = {n["note_name"] for n in data["notes"]}
        self.assertEqual(names, {"Gb", "Bb", "Db", "F"})
        # The form skips the high e string entirely.
        self.assertNotIn(1, {n["string"] for n in data["notes"]})

class RoundFilterTests(ValidRoundMixin, TestCase):
    """GET /api/round/?scales=... — the start-menu exercise filter.

    The no-param domain is already pinned by RoundApiTests' 400-call
    test; these cover the filtered paths.
    """

    def forms_of(self, *scale_ids):
        return {fid for fid, form in theory.load_fingerings().items()
                if form["scale"] in scale_ids}

    def test_filter_single_scale_stays_in_domain_over_100_calls(self):
        seen = set()
        for _ in range(100):
            resp = self.client.get("/api/round/?scales=major_pentatonic")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assert_valid_round(data)
            self.assertEqual(data["scale"], "Major Pentatonic")
            seen.add(data["form_id"])
        # Every major-pentatonic form (and nothing else) gets served.
        self.assertEqual(seen, self.forms_of("major_pentatonic"))

    def test_filter_multi_scale(self):
        seen_names, seen_forms = set(), set()
        for _ in range(100):
            resp = self.client.get(
                "/api/round/?scales=major_scale,minor7_arpeggio")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assert_valid_round(data)
            seen_names.add(data["scale"])
            seen_forms.add(data["form_id"])
        self.assertEqual(seen_names, {"Major Scale", "Minor 7 Arpeggio"})
        self.assertEqual(seen_forms,
                         self.forms_of("major_scale", "minor7_arpeggio"))

    def test_filter_each_scale_id_individually(self):
        """Every playable scale id serves its rounds; a config-defined but
        form-less id (major/minor arpeggio have no shipped forms) is a 400 —
        never a 500 from an empty random pool."""
        playable = {form["scale"]
                    for form in theory.load_fingerings().values()}
        for scale_id, spec in theory.load_scales().items():
            with self.subTest(scale=scale_id):
                resp = self.client.get(f"/api/round/?scales={scale_id}")
                if scale_id in playable:
                    self.assertEqual(resp.status_code, 200)
                    self.assertEqual(resp.json()["scale"], spec["name"])
                else:
                    self.assertEqual(resp.status_code, 400)
                    self.assertIn(scale_id, resp.json()["errors"]["scales"])

    def test_filter_formless_plus_playable_id_still_serves(self):
        """A mixed filter with one form-less id still has a pool — rounds
        come from the playable id only."""
        resp = self.client.get("/api/round/?scales=major_arpeggio,major_scale")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["scale"], "Major Scale")

    def test_filter_all_scales_param_equivalent_to_absent(self):
        param = ",".join(theory.load_scales())
        for _ in range(5):
            resp = self.client.get(f"/api/round/?scales={param}")
            self.assertEqual(resp.status_code, 200)
            self.assert_valid_round(resp.json())

    def test_filter_unknown_id_400_names_bad_ids(self):
        resp = self.client.get("/api/round/?scales=phrygian")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("phrygian", resp.json()["errors"]["scales"])

    def test_filter_mixed_known_unknown_400_names_only_bad(self):
        resp = self.client.get("/api/round/?scales=major_scale,phrygian,nope")
        self.assertEqual(resp.status_code, 400)
        message = resp.json()["errors"]["scales"]
        self.assertIn("phrygian", message)
        self.assertIn("nope", message)
        # The good id is only echoed in the "(known: ...)" tail, never
        # reported as unknown.
        self.assertNotIn("major_scale", message.split("(known:")[0])

    def test_filter_empty_value_400(self):
        resp = self.client.get("/api/round/?scales=")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("scales", resp.json()["errors"])

    def test_filter_only_commas_400(self):
        resp = self.client.get("/api/round/?scales=,,")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("scales", resp.json()["errors"])

    def test_filter_duplicate_ids_ok(self):
        resp = self.client.get("/api/round/?scales=major_scale,major_scale")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["scale"], "Major Scale")

    def test_filter_trailing_comma_tolerated(self):
        """Documents the lenient tokenization: empty tokens are dropped."""
        resp = self.client.get("/api/round/?scales=major_scale,")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["scale"], "Major Scale")

    def test_filter_garbage_400_never_500(self):
        cases = {
            "space in token": "major scale",
            "wrong case": "MAJOR_SCALE",
            "literal percent-encoding": "%20",
            "very long token": "x" * 500,
            "unicode token": "мажор",
        }
        for label, value in cases.items():
            with self.subTest(case=label):
                resp = self.client.get("/api/round/", {"scales": value})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("scales", resp.json()["errors"])

    def test_filter_narrows_the_selection_pool(self):
        """Form selection draws from exactly the filtered pool."""
        expected = [fid for fid, form in theory.load_fingerings().items()
                    if form["scale"] == "minor_pentatonic"]
        with mock.patch("practice.views.random.choice",
                        side_effect=random.choice) as spy:
            resp = self.client.get("/api/round/?scales=minor_pentatonic")
        self.assertEqual(resp.status_code, 200)
        pools = [c.args[0] for c in spy.call_args_list
                 if c.args[0] is not theory.KEYS
                 and c.args[0] is not theory.DIRECTIONS]
        self.assertEqual(pools, [expected])

    def test_filter_post_still_405(self):
        resp = self.client.post("/api/round/?scales=major_scale")
        self.assertEqual(resp.status_code, 405)

