"""Tests for the page and API endpoints."""

import json

from django.test import TestCase

from practice import theory
from practice.models import AttemptLog

ROUND_KEYS = {"scale", "key", "direction", "form_id", "form_name",
              "category", "display_label", "caged_shape", "starting_finger",
              "window_start", "notes"}
NOTE_KEYS = {"string", "fret", "pitch_class", "note_name", "is_root"}

VALID_LOG_PAYLOAD = {
    "form_id": "minor-pentatonic-e-shape",
    "scale": "Minor Pentatonic",
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
        self.assertIn("coming soon", html)
        self.assertIn("data-csrf-token", html)

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
        self.assertIn("style.css?v=4", html)
        self.assertIn("app.js?v=4", html)


class RoundApiTests(TestCase):
    def assert_valid_round(self, data):
        fingerings = theory.load_fingerings()
        scales = theory.load_scales()

        self.assertEqual(set(data), ROUND_KEYS)
        self.assertIn(data["scale"], theory.scale_names())
        self.assertIn(data["key"], theory.KEYS)
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
        if data["category"] in ("pentatonic", "arpeggio"):
            self.assertIsInstance(data["caged_shape"], str)
            self.assertIn(data["caged_shape"], theory.CAGED_SHAPES)
            self.assertIsNone(data["starting_finger"])
            self.assertEqual(data["display_label"],
                             f"{data['caged_shape']} Shape")
        else:
            self.assertIsNone(data["caged_shape"])
            self.assertIsInstance(data["starting_finger"], int)
            self.assertIn(data["starting_finger"], (1, 2, 3, 4))
            self.assertEqual(
                data["display_label"],
                f"{theory.ordinal(data['starting_finger'])} Finger Form")

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
            self.assertIn(note["note_name"], theory.NOTE_NAMES)
            self.assertEqual(note["pitch_class"],
                             theory.NOTE_NAMES.index(note["note_name"]))
        self.assertEqual(data["window_start"],
                         min(n["fret"] for n in data["notes"]))

        # Payload must match a direct resolution of the same form + key.
        window_start, notes = theory.resolve_form(data["form_id"], data["key"])
        self.assertEqual(data["window_start"], window_start)
        self.assertEqual(data["notes"], notes)

    def test_round_ok_and_shape(self):
        resp = self.client.get("/api/round/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "application/json")
        self.assert_valid_round(resp.json())

    def test_round_randomisation_stays_in_domain_over_100_calls(self):
        seen = {"scales": set(), "directions": set(), "forms": set(),
                "keys": set(), "categories": set()}
        for _ in range(100):
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
        # over 100 uniform draws from the 3 shipped major-scale forms).
        self.assertEqual(seen["categories"], {"scale"})
        self.assertEqual(seen["directions"], {"Ascending", "Descending"})
        self.assertEqual(seen["forms"], set(theory.load_fingerings()))
        self.assertGreaterEqual(len(seen["keys"]), 5)
        self.assertEqual(seen["scales"], {"Major Scale"})

    def test_round_rejects_post(self):
        resp = self.client.post("/api/round/")
        self.assertEqual(resp.status_code, 405)


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
        self.assertEqual(row.form_id, "minor-pentatonic-e-shape")
        self.assertEqual(row.scale, "Minor Pentatonic")
        self.assertEqual(row.key, "A")
        self.assertEqual(row.direction, "Ascending")
        self.assertTrue(row.correct)
        self.assertIsNotNone(row.timestamp)

    def test_valid_log_correct_false(self):
        payload = {**VALID_LOG_PAYLOAD,
                   "form_id": "major-pentatonic-e-shape",
                   "scale": "Major Pentatonic",
                   "key": "F#",
                   "direction": "Descending",
                   "correct": False}
        resp = self.post_log(payload)
        self.assertEqual(resp.status_code, 201)
        row = AttemptLog.objects.get()
        self.assertEqual(row.form_id, "major-pentatonic-e-shape")
        self.assertEqual(row.scale, "Major Pentatonic")
        self.assertEqual(row.key, "F#")
        self.assertEqual(row.direction, "Descending")
        self.assertFalse(row.correct)

    def test_new_v2_form_ids_and_scales_accepted(self):
        """Arpeggio + scale-category rounds log fine (no membership check
        on form_id, per the v1 decision; scale display names now include
        the new families)."""
        cases = [
            {"form_id": "dominant7-arpeggio-a-shape",
             "scale": "Dominant 7 Arpeggio"},
            {"form_id": "natural-minor-scale-2nd-finger-form",
             "scale": "Natural Minor Scale"},
            {"form_id": "major7-arpeggio-g-shape",
             "scale": "Major 7 Arpeggio"},
        ]
        for case in cases:
            with self.subTest(**case):
                resp = self.post_log({**VALID_LOG_PAYLOAD, **case})
                self.assertEqual(resp.status_code, 201)
        self.assertEqual(AttemptLog.objects.count(), len(cases))

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
            "unknown direction": {**VALID_LOG_PAYLOAD, "direction": "Sideways"},
            "empty form_id": {**VALID_LOG_PAYLOAD, "form_id": ""},
            "form_id as int": {**VALID_LOG_PAYLOAD, "form_id": 7},
            "form_id too long": {**VALID_LOG_PAYLOAD, "form_id": "x" * 65},
        }
        for label, payload in bad_payloads.items():
            with self.subTest(case=label):
                resp = self.post_log(payload)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_form_id_too_long_400_with_field_error(self):
        """65 chars exceeds the model's max_length=64 → per-field 400."""
        resp = self.post_log({**VALID_LOG_PAYLOAD, "form_id": "x" * 65})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("form_id", resp.json()["errors"])
        self.assertEqual(AttemptLog.objects.count(), 0)

    def test_form_id_at_max_length_accepted(self):
        """Exactly 64 chars fits the column; no membership check on
        form_id, so any 64-char string logs fine."""
        form_id = "x" * 64
        resp = self.post_log({**VALID_LOG_PAYLOAD, "form_id": form_id})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AttemptLog.objects.get().form_id, form_id)

    def test_log_rejects_get(self):
        resp = self.client.get("/api/log/")
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(AttemptLog.objects.count(), 0)
