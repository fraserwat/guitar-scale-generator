"""Tests for the page and API endpoints."""

import json
import random
from pathlib import Path
from unittest import mock

from django.test import TestCase, override_settings

from practice import spaced_repetition, theory
from practice.models import AttemptLog

ROUND_KEYS = {"scale", "key", "direction", "form_id", "form_name",
              "category", "display_label", "caged_shape", "starting_finger",
              "window_start", "notes"}
NOTE_KEYS = {"string", "fret", "pitch_class", "note_name", "is_root"}

VALID_LOG_PAYLOAD = {
    "form_id": "major-scale-e-root-1st-finger-form",
    "scale": "Major Scale",
    "key": "A",
    "direction": "Ascending",
    "correct": True,
}


class IndexPageTests(TestCase):
    def test_index_renders_start_screen(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('id="start-screen"', html)
        self.assertIn('id="timer-length"', html)
        self.assertIn('id="start-btn"', html)
        # 7-string is still promised (hover hint on the disabled segment).
        self.assertIn('title="Coming soon"', html)
        self.assertIn("data-csrf-token", html)
        # App name is ScaleRunner; the title h1 is the click-to-menu hook,
        # now wrapping the GBA-style SVG wordmark (two-tone tspans, an
        # accessible name, and the accent-orange "Runner").
        self.assertIn("<title>ScaleRunner</title>", html)
        self.assertIn('<h1 class="app-title" title="Back to menu">', html)
        self.assertIn('aria-label="ScaleRunner"', html)
        self.assertIn('role="img"', html)
        self.assertIn(">Scale</tspan>", html)
        self.assertIn(">Runner</tspan>", html)
        self.assertIn('fill="#ffab4a"', html)
        self.assertNotIn("Guitar Scale Practice", html)

    def test_index_has_v2_ui_hooks(self):
        """Category-language header slots + start-menu keyboard tip."""
        html = self.client.get("/").content.decode()
        self.assertIn('id="round-label"', html)
        self.assertIn('id="round-direction"', html)
        # Keyboard tip lives on the start menu, NOT inside the judge buttons.
        self.assertIn('class="keyboard-tip"', html)
        self.assertNotIn("key-hint", html)
        self.assertIn("for correct", html)
        self.assertIn("for incorrect", html)
        # Real TAB element (the empty -stub era is over).
        self.assertIn('id="tab"', html)
        self.assertNotIn("tab-stub", html)
        # Cache-busted static includes.
        self.assertIn("style.css?v=15", html)
        self.assertIn("app.js?v=10", html)

    def test_app_js_has_retry_queue_hooks(self):
        """Source-presence smoke test for the v4 retry queue (there is no
        JS test runner in this repo — the scheduling behavior itself is
        verified by manual play). Asserts the load-bearing strings exist
        in app.js: the queue, the overtime drain, the 2-turn delay, and
        the is_retry flag sent to /api/log/."""
        app_js = (Path(__file__).resolve().parent.parent
                  / "static" / "practice" / "app.js").read_text()
        self.assertIn("retryQueue", app_js)
        self.assertIn("overtime", app_js)
        self.assertIn("delay: 2", app_js)
        self.assertIn("is_retry", app_js)

    def test_index_strings_segmented_control(self):
        """v5: the greyed 7-string checkbox became a 6/7 segmented radio;
        6 is the checked default, 7 is disabled with a soon badge."""
        html = self.client.get("/").content.decode()
        self.assertIn('role="radiogroup"', html)
        six = html.index('id="strings-6"')
        seven = html.index('id="strings-7"')
        self.assertIn('value="6"', html[six:six + 80])
        self.assertIn("checked", html[six:six + 80])
        self.assertIn('value="7"', html[seven:seven + 80])
        self.assertIn("disabled", html[seven:seven + 80])
        self.assertIn(">soon</span>", html)
        self.assertNotIn('id="seven-string-toggle"', html)

    @staticmethod
    def playable_scale_ids():
        """Scale ids with >= 1 loaded fingering form — the only ones the
        exercise picker offers (major/minor arpeggio are config-defined
        but form-less since the v3 prune)."""
        return {form["scale"] for form in theory.load_fingerings().values()}

    def test_index_exercise_checkboxes_match_config(self):
        """Server-rendered from scales.yaml: every PLAYABLE scale gets a
        checkbox (checked by default) — a new config scale with forms
        appears with no template change; form-less scales are omitted."""
        html = self.client.get("/").content.decode()
        playable = self.playable_scale_ids()
        self.assertEqual(html.count('class="exercise-checkbox"'),
                         len(playable))
        for scale_id in theory.load_scales():
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
        scales_at = html.index(">Scales</h3>")
        arps_at = html.index(">Arpeggios</h3>")
        self.assertLess(scales_at, arps_at)
        playable = self.playable_scale_ids()
        last = scales_at
        for scale_id, spec in theory.load_scales().items():
            if spec["category"] == "arpeggio" or scale_id not in playable:
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
        ("Major 7 Arpeggio" renders as "Major 7"); Scales names stay full."""
        html = self.client.get("/").content.decode()
        playable = self.playable_scale_ids()
        for scale_id, spec in theory.load_scales().items():
            if scale_id not in playable:
                continue
            with self.subTest(scale=scale_id):
                if spec["category"] == "arpeggio":
                    stripped = spec["name"].removesuffix(" Arpeggio")
                    self.assertIn(f">{stripped}</span>", html)
                    self.assertNotIn(spec["name"], html)
                else:
                    self.assertIn(f">{spec['name']}</span>", html)

    def test_index_exercise_hint_and_headings(self):
        html = self.client.get("/").content.decode()
        idx = html.index('id="exercise-hint"')
        self.assertIn("hidden", html[idx:idx + 120])  # hidden by default
        self.assertIn("Pick at least one exercise", html)
        self.assertIn(">Practice Exercises</span>", html)

    def test_index_panel_order(self):
        """Timer -> Strings -> Practice Exercises -> Start."""
        html = self.client.get("/").content.decode()
        order = [html.index('id="timer-length"'),
                 html.index('id="strings-6"'),
                 html.index("Practice Exercises"),
                 html.index('id="start-btn"')]
        self.assertEqual(order, sorted(order))

    def test_app_js_has_exercise_filter_hooks(self):
        """Source-presence smoke test for the v5 exercise filter (no JS
        runner in this repo; behavior verified by manual play): the scales
        query builder, the filter param, and the Start-gating hooks."""
        app_js = (Path(__file__).resolve().parent.parent
                  / "static" / "practice" / "app.js").read_text()
        self.assertIn("buildScalesQuery", app_js)
        self.assertIn('"?scales="', app_js)
        self.assertIn("exercise-checkbox", app_js)
        self.assertIn("updateStartState", app_js)
        self.assertIn("roundQuery", app_js)


class ValidRoundMixin:
    """Full-schema validation of one /api/round/ payload, shared by the
    plain round tests and the ?scales= filter tests."""

    def assert_valid_round(self, data):
        fingerings = theory.load_fingerings()
        scales = theory.load_scales()

        self.assertEqual(set(data), ROUND_KEYS)
        self.assertIn(data["scale"], theory.scale_names())
        self.assertIn(data["key"], theory.VALID_KEYS)
        self.assertIn(data["direction"], theory.DIRECTIONS)
        self.assertIn(data["form_id"], fingerings)

        form = fingerings[data["form_id"]]
        self.assertEqual(data["form_name"], form["name"])
        self.assertEqual(data["scale"], scales[form["scale"]]["name"])

        # New v2 fields: category + display label + XOR-populated
        # caged_shape / starting_finger, consistent with the config.
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

    def test_round_randomisation_stays_in_domain_over_400_calls(self):
        seen = {"scales": set(), "directions": set(), "forms": set(),
                "keys": set(), "categories": set()}
        for _ in range(400):
            resp = self.client.get("/api/round/")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assert_valid_round(data)
            seen["scales"].add(data["scale"])
            seen["directions"].add(data["direction"])
            seen["forms"].add(data["form_id"])
            seen["keys"].add(data["key"])
            seen["categories"].add(data["category"])

        # Randomisation actually varies (P(failure) is astronomically small
        # over 400 uniform draws from the 32 shipped forms: each form is
        # missed with p = (31/32)^400 ~ 3.1e-6).
        self.assertEqual(seen["categories"],
                         {"scale", "arpeggio", "pentatonic"})
        self.assertEqual(seen["directions"], {"Ascending", "Descending"})
        self.assertEqual(seen["forms"], set(theory.load_fingerings()))
        self.assertGreaterEqual(len(seen["keys"]), 5)
        self.assertEqual(seen["scales"], {
            "Major Scale", "Natural Minor Scale",
            "Major 7 Arpeggio", "Dominant 7 Arpeggio",
            "Minor 7 Arpeggio", "Minor 7b5 Arpeggio",
            "Diminished 7 Arpeggio",
            "Major Pentatonic", "Minor Pentatonic",
        })

    def test_round_rejects_post(self):
        resp = self.client.post("/api/round/")
        self.assertEqual(resp.status_code, 405)


class RoundKeySpellingTests(TestCase):
    """The 50% flat/sharp presentation of accidental keys.

    api_round draws random.choice(KEYS) then, for accidental roots only,
    random.random() < 0.5 flips to the flat spelling. Both draws are
    mocked to pin each branch deterministically for every accidental key.
    """

    def get_round(self, chosen_key, coin):
        """One /api/round/ with the key draw and the flat/sharp coin pinned.
        random.choice feeds the key draw, then the direction draw."""
        with mock.patch("practice.views.random.choice",
                        side_effect=[chosen_key, "Ascending"]), \
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
                                side_effect=[key, "Ascending"]), \
                     mock.patch("practice.views.random.random") as coin:
                    resp = self.client.get("/api/round/")
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.json()["key"], key)
                coin.assert_not_called()

    def test_gb_round_spells_cb(self):
        """End-to-end: a Gb major-scale round spells exactly the Gb major
        names, Cb included (form pinned — the maj7 arpeggio form has no
        4th degree, so it never contains a Cb)."""
        with mock.patch(
                "practice.views.random.choices",
                return_value=["major-scale-e-root-1st-finger-form"]):
            data = self.get_round("F#", coin=0.0)
        self.assertEqual(data["key"], "Gb")
        self.assertEqual(data["form_id"], "major-scale-e-root-1st-finger-form")
        names = {n["note_name"] for n in data["notes"]}
        self.assertEqual(names, {"Gb", "Ab", "Bb", "Cb", "Db", "Eb", "F"})

    def test_gb_maj7_arpeggio_round_spelling(self):
        """The new single-yaml maj7 arpeggio form, flat-spelled end to end:
        Gb maj7 arpeggio = Gb Bb Db F."""
        with mock.patch("practice.views.random.choices",
                        return_value=["major7-arpeggio-e-root-1st-finger-form"]):
            data = self.get_round("F#", coin=0.0)
        self.assertEqual(data["key"], "Gb")
        self.assertEqual(data["scale"], "Major 7 Arpeggio")
        self.assertEqual(data["display_label"], "1st Finger Form (E-root)")
        names = {n["note_name"] for n in data["notes"]}
        self.assertEqual(names, {"Gb", "Bb", "Db", "F"})
        # The form skips the high e string entirely.
        self.assertNotIn(1, {n["string"] for n in data["notes"]})

    def test_unmocked_rounds_serve_both_spellings(self):
        """Statistical sanity check on the real RNG: over 400 rounds both a
        flat and a sharp accidental key appear (P(miss) < 1e-30), and every
        served key is a valid spelling."""
        random.seed(1990)
        seen = set()
        for _ in range(400):
            data = self.client.get("/api/round/").json()
            self.assertIn(data["key"], theory.VALID_KEYS)
            seen.add(data["key"])
        self.assertTrue(seen & set(theory.FLAT_KEYS))
        self.assertTrue(seen & set(theory.SHARP_TO_FLAT))


class RoundFilterTests(ValidRoundMixin, TestCase):
    """GET /api/round/?scales=... — the start-menu exercise filter.

    The no-param domain is already pinned by RoundApiTests' 400-call
    test (exact pre-v5 behaviour); these cover the filtered paths.
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
        form-less id (major/minor arpeggio since the v3 prune) is a 400 —
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

    def test_filter_feeds_filtered_ids_to_weights(self):
        """The spaced-repetition hook sees exactly the filtered pool."""
        expected = [fid for fid, form in theory.load_fingerings().items()
                    if form["scale"] == "minor_pentatonic"]
        with mock.patch(
                "practice.views.spaced_repetition.next_round_weights",
                side_effect=spaced_repetition.next_round_weights) as spy:
            resp = self.client.get("/api/round/?scales=minor_pentatonic")
        self.assertEqual(resp.status_code, 200)
        spy.assert_called_once_with(expected)

    def test_filter_post_still_405(self):
        resp = self.client.post("/api/round/?scales=major_scale")
        self.assertEqual(resp.status_code, 405)


# Throttling is covered by test_ratelimit.py; disabled here so these
# validation tests can POST freely (32 forms plus the invalid-payload
# cases exceed the default per-minute cap inside one test-run window).
@override_settings(API_RATE_LIMIT_PER_MINUTE=0)
class LogApiTests(TestCase):
    def post_log(self, payload, raw=None):
        body = raw if raw is not None else json.dumps(payload)
        return self.client.post("/api/log/", body,
                                content_type="application/json")

    def test_valid_log_correct_true(self):
        resp = self.post_log(VALID_LOG_PAYLOAD)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["status"], "ok")
        self.assertEqual(AttemptLog.objects.count(), 1)
        row = AttemptLog.objects.get()
        self.assertEqual(row.form_id, "major-scale-e-root-1st-finger-form")
        self.assertEqual(row.scale, "Major Scale")
        self.assertEqual(row.key, "A")
        self.assertEqual(row.direction, "Ascending")
        self.assertTrue(row.correct)
        self.assertFalse(row.is_retry)
        self.assertIsNotNone(row.timestamp)

    def test_valid_log_correct_false(self):
        payload = {**VALID_LOG_PAYLOAD,
                   "form_id": "dominant7-arpeggio-e-root-1st-finger-form",
                   "scale": "Dominant 7 Arpeggio",
                   "key": "F#",
                   "direction": "Descending",
                   "correct": False}
        resp = self.post_log(payload)
        self.assertEqual(resp.status_code, 201)
        row = AttemptLog.objects.get()
        self.assertEqual(row.form_id, "dominant7-arpeggio-e-root-1st-finger-form")
        self.assertEqual(row.scale, "Dominant 7 Arpeggio")
        self.assertEqual(row.key, "F#")
        self.assertEqual(row.direction, "Descending")
        self.assertFalse(row.correct)

    def test_log_without_is_retry_defaults_false(self):
        """is_retry is optional — pre-v4 payloads must keep logging fine
        and land as first attempts (False)."""
        resp = self.post_log(VALID_LOG_PAYLOAD)
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(AttemptLog.objects.get().is_retry)

    def test_log_is_retry_true(self):
        resp = self.post_log({**VALID_LOG_PAYLOAD, "is_retry": True})
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(AttemptLog.objects.get().is_retry)

    def test_log_is_retry_true_correct_false(self):
        """A failed retry — re-queued client-side, logged like any attempt."""
        payload = {**VALID_LOG_PAYLOAD, "correct": False, "is_retry": True}
        resp = self.post_log(payload)
        self.assertEqual(resp.status_code, 201)
        row = AttemptLog.objects.get()
        self.assertFalse(row.correct)
        self.assertTrue(row.is_retry)

    def test_log_is_retry_false_explicit(self):
        resp = self.post_log({**VALID_LOG_PAYLOAD, "is_retry": False})
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(AttemptLog.objects.get().is_retry)

    def test_log_is_retry_wrong_types_400(self):
        bad_values = {
            "is_retry as string": "true",
            "is_retry as int 1": 1,
            "is_retry as int 0": 0,
            "is_retry as null": None,
            "is_retry as list": [],
            "is_retry as object": {},
        }
        for label, value in bad_values.items():
            with self.subTest(case=label):
                resp = self.post_log({**VALID_LOG_PAYLOAD, "is_retry": value})
                self.assertEqual(resp.status_code, 400)
                self.assertIn("is_retry", resp.json()["errors"])
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_is_retry_field_defaults_false(self):
        """Model default backfills old rows and covers ORM creates that
        omit the kwarg (nothing before v4 passed it)."""
        self.assertIs(AttemptLog._meta.get_field("is_retry").default, False)
        row = AttemptLog.objects.create(
            form_id="major-scale-e-root-1st-finger-form",
            scale="Major Scale", key="A", direction="Ascending", correct=True,
        )
        row.refresh_from_db()
        self.assertFalse(row.is_retry)

    def test_every_loaded_form_id_accepted(self):
        """form_id is validated against the loaded fingering configs, so
        every shipped form — whatever /api/round/ can serve — logs fine."""
        form_ids = list(theory.load_fingerings())
        for form_id in form_ids:
            with self.subTest(form_id=form_id):
                resp = self.post_log({**VALID_LOG_PAYLOAD, "form_id": form_id})
                self.assertEqual(resp.status_code, 201)
        self.assertEqual(AttemptLog.objects.count(), len(form_ids))

    def test_every_flat_key_accepted(self):
        """The client echoes the served key back, so flat spellings
        (Db, Eb, Gb, Ab, Bb) must log fine."""
        for flat in theory.FLAT_KEYS:
            with self.subTest(key=flat):
                resp = self.post_log({**VALID_LOG_PAYLOAD, "key": flat})
                self.assertEqual(resp.status_code, 201)
        self.assertEqual(AttemptLog.objects.count(), len(theory.FLAT_KEYS))
        self.assertEqual(
            sorted(AttemptLog.objects.values_list("key", flat=True)),
            sorted(theory.FLAT_KEYS),
        )

    def test_every_sharp_and_natural_key_accepted(self):
        for key in theory.KEYS:
            with self.subTest(key=key):
                resp = self.post_log({**VALID_LOG_PAYLOAD, "key": key})
                self.assertEqual(resp.status_code, 201)
        self.assertEqual(AttemptLog.objects.count(), len(theory.KEYS))

    def test_invalid_json_body_400(self):
        resp = self.post_log(None, raw="{not json")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_non_object_json_400(self):
        resp = self.post_log(None, raw="[1, 2, 3]")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_missing_each_field_400(self):
        for field in VALID_LOG_PAYLOAD:
            payload = dict(VALID_LOG_PAYLOAD)
            del payload[field]
            with self.subTest(missing=field):
                resp = self.post_log(payload)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(field, resp.json()["errors"])
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_wrong_types_400(self):
        bad_payloads = {
            "correct as string": {**VALID_LOG_PAYLOAD, "correct": "true"},
            "correct as int": {**VALID_LOG_PAYLOAD, "correct": 1},
            "scale as int": {**VALID_LOG_PAYLOAD, "scale": 5},
            "unknown scale": {**VALID_LOG_PAYLOAD, "scale": "Phrygian"},
            "unknown key": {**VALID_LOG_PAYLOAD, "key": "H"},
            "non-key spelling Cb": {**VALID_LOG_PAYLOAD, "key": "Cb"},
            "non-key spelling E#": {**VALID_LOG_PAYLOAD, "key": "E#"},
            "double-flat key": {**VALID_LOG_PAYLOAD, "key": "Bbb"},
            "unknown direction": {**VALID_LOG_PAYLOAD, "direction": "Sideways"},
            "empty form_id": {**VALID_LOG_PAYLOAD, "form_id": ""},
            "form_id as int": {**VALID_LOG_PAYLOAD, "form_id": 7},
            "unknown form_id": {**VALID_LOG_PAYLOAD, "form_id": "no-such-form"},
        }
        for label, payload in bad_payloads.items():
            with self.subTest(case=label):
                resp = self.post_log(payload)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_form_id_bound_mirrors_model_column(self):
        """theory.FORM_ID_MAX_LENGTH (Django-free module) must match the
        AttemptLog column it exists to protect."""
        self.assertEqual(
            AttemptLog._meta.get_field("form_id").max_length,
            theory.FORM_ID_MAX_LENGTH,
        )

    def test_unknown_form_id_400_with_field_error(self):
        """form_id must name a loaded fingering form → per-field 400.
        This also bounds the stored value: every loadable id fits the
        model's max_length=64 column."""
        resp = self.post_log({**VALID_LOG_PAYLOAD, "form_id": "x" * 65})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("form_id", resp.json()["errors"])
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_log_rejects_get(self):
        resp = self.client.get("/api/log/")
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(AttemptLog.objects.count(), 0)
