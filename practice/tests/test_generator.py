"""Tests for scripts/generate_fingerings.py and the generated configs.

The generator always runs against a temp directory here — NEVER against
practice/configs/fingerings/. The shipped dir is pruned to the 3 E-root
major-scale forms, and the generator's main() deletes-and-rewrites its
whole output dir, so pointing it at the live dir would resurrect the 38
pruned files.

The known-good offset tables below are asserted LITERALLY against the
generator's output (loaded through the engine), independently of the
generator's own logic.
"""

import filecmp
import subprocess
import sys
import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from practice import theory

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GENERATOR = REPO_ROOT / "scripts" / "generate_fingerings.py"
FINGERINGS_DIR = REPO_ROOT / "practice" / "configs" / "fingerings"

# The pruned subset that actually ships in the repo.
SHIPPED_FILES = [
    "major_scale_1st_finger_form.yaml",
    "major_scale_2nd_finger_form.yaml",
    "major_scale_4th_finger_form.yaml",
]

# Module-level temp dir holding one generator run, shared by the tests
# below (the determinism test does its own fresh runs).
_generated_tmp = None
GENERATED_DIR = None


def setUpModule():
    global _generated_tmp, GENERATED_DIR
    _generated_tmp = tempfile.TemporaryDirectory()
    GENERATED_DIR = Path(_generated_tmp.name)
    run_generator(GENERATED_DIR)


def tearDownModule():
    _generated_tmp.cleanup()

# Phase-0 hand-verified tables (offsets per string, low E = 6 first).
KNOWN_GOOD_OFFSETS = {
    "minor-pentatonic-e-shape": {
        6: [0, 3], 5: [0, 2], 4: [0, 2], 3: [0, 2], 2: [0, 3], 1: [0, 3]},
    "minor-pentatonic-d-shape": {
        6: [3, 5], 5: [2, 5], 4: [2, 5], 3: [2, 4], 2: [3, 5], 1: [3, 5]},
    "major-pentatonic-e-shape": {
        6: [0, 2], 5: [-1, 2], 4: [-1, 2], 3: [-1, 1], 2: [0, 2], 1: [0, 2]},
    "major-arpeggio-e-shape": {
        6: [0], 5: [-1, 2], 4: [2], 3: [1], 2: [0], 1: [0]},
    "major-scale-2nd-finger-form": {
        6: [-1, 0, 2], 5: [-1, 0, 2], 4: [-1, 1, 2],
        3: [-1, 1, 2], 2: [0, 2], 1: [-1, 0, 2]},
}


def run_generator(out_dir):
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "-o", str(out_dir)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise AssertionError(f"generator failed: {result.stderr}")
    return result


class GeneratorDeterminismTests(SimpleTestCase):
    def test_two_runs_produce_identical_files(self):
        with tempfile.TemporaryDirectory() as a, \
                tempfile.TemporaryDirectory() as b:
            run_generator(a)
            run_generator(b)
            files_a = sorted(p.name for p in Path(a).glob("*.yaml"))
            files_b = sorted(p.name for p in Path(b).glob("*.yaml"))
            self.assertEqual(files_a, files_b)
            self.assertEqual(len(files_a), 41)
            match, mismatch, errors = filecmp.cmpfiles(
                a, b, files_a, shallow=False)
            self.assertEqual(sorted(match), files_a)
            self.assertEqual(mismatch, [])
            self.assertEqual(errors, [])

    def test_generates_exactly_41_files(self):
        self.assertEqual(len(list(GENERATED_DIR.glob("*.yaml"))), 41)
        self.assertEqual(len(list(GENERATED_DIR.glob("*.yml"))), 0)


class ShippedSubsetTests(SimpleTestCase):
    """The pruned shipped dir stays an exact, in-sync generator subset."""

    def test_shipped_dir_contains_exactly_the_3_major_scale_forms(self):
        shipped = sorted(
            p.name
            for pattern in ("*.yaml", "*.yml")
            for p in FINGERINGS_DIR.glob(pattern)
        )
        self.assertEqual(shipped, SHIPPED_FILES)

    def test_shipped_configs_byte_identical_to_generator_output(self):
        """Each shipped yaml == the same-named file the generator emits."""
        generated_names = {p.name for p in GENERATED_DIR.glob("*.yaml")}
        self.assertTrue(set(SHIPPED_FILES) <= generated_names)
        match, mismatch, errors = filecmp.cmpfiles(
            GENERATED_DIR, FINGERINGS_DIR, SHIPPED_FILES, shallow=False)
        self.assertEqual(sorted(match), SHIPPED_FILES)
        self.assertEqual(mismatch, [])
        self.assertEqual(errors, [])


class KnownGoodTableTests(SimpleTestCase):
    """The 5 hand-verified offset tables, asserted against generated YAMLs."""

    maxDiff = None

    def test_known_good_tables_literal(self):
        fingerings = theory.load_fingerings(GENERATED_DIR)
        for form_id, offsets in KNOWN_GOOD_OFFSETS.items():
            with self.subTest(form=form_id):
                self.assertEqual(fingerings[form_id]["offsets"], offsets)

    def test_v1_forms_reproduced_under_caged_names(self):
        """v1 Form 1/Form 2 = the E and D shapes, byte-for-byte offsets."""
        fingerings = theory.load_fingerings(GENERATED_DIR)
        self.assertEqual(
            fingerings["minor-pentatonic-e-shape"]["offsets"],
            {6: [0, 3], 5: [0, 2], 4: [0, 2], 3: [0, 2], 2: [0, 3], 1: [0, 3]})
        self.assertEqual(
            fingerings["minor-pentatonic-d-shape"]["offsets"],
            {6: [3, 5], 5: [2, 5], 4: [2, 5], 3: [2, 4], 2: [3, 5], 1: [3, 5]})
        # v1 ids are gone.
        self.assertNotIn("minor-pentatonic-form-1", fingerings)
        self.assertNotIn("minor-pentatonic-form-2", fingerings)
        self.assertNotIn("major-pentatonic-form-1", fingerings)

    def test_pentatonic_boxes_tile_the_octave(self):
        """Consecutive boxes share their boundary note on every string, and
        the 5 boxes cover the string's full cyclic note sequence."""
        fingerings = theory.load_fingerings(GENERATED_DIR)
        for scale in ("major-pentatonic", "minor-pentatonic"):
            shapes = ["e", "d", "c", "a", "g"]  # ascending box order
            forms = [fingerings[f"{scale}-{s}-shape"] for s in shapes]
            for string in range(1, 7):
                for lower, upper in zip(forms, forms[1:]):
                    with self.subTest(scale=scale, string=string,
                                      boxes=(lower["id"], upper["id"])):
                        self.assertEqual(lower["offsets"][string][-1],
                                         upper["offsets"][string][0])
                # G shape's top note = E shape's bottom note + 12.
                self.assertEqual(forms[-1]["offsets"][string][-1],
                                 forms[0]["offsets"][string][0] + 12)

    def test_arpeggio_offsets_subset_of_matching_pentatonic_window(self):
        """Arpeggio shape X sits inside pentatonic shape X's box window."""
        fingerings = theory.load_fingerings(GENERATED_DIR)
        parents = {
            "major-arpeggio": "major-pentatonic",
            "major7-arpeggio": "major-pentatonic",
            "dominant7-arpeggio": "major-pentatonic",
            "minor-arpeggio": "minor-pentatonic",
            "minor7-arpeggio": "minor-pentatonic",
        }
        for arp, pent in parents.items():
            for shape in ("c", "a", "g", "e", "d"):
                arp_form = fingerings[f"{arp}-{shape}-shape"]
                pent_form = fingerings[f"{pent}-{shape}-shape"]
                pent_offs = [o for offs in pent_form["offsets"].values()
                             for o in offs]
                lo, hi = min(pent_offs), max(pent_offs)
                arp_offs = [o for offs in arp_form["offsets"].values()
                            for o in offs]
                with self.subTest(arp=arp_form["id"]):
                    self.assertTrue(all(lo <= o <= hi for o in arp_offs))

    def test_no_scale_form_needed_widening(self):
        """All 6 finger forms are complete within their 4-fret windows."""
        fingerings = theory.load_fingerings(GENERATED_DIR)
        for form in fingerings.values():
            if form["category"] != "scale":
                continue
            offs = [o for offsets in form["offsets"].values()
                    for o in offsets]
            lo = -(form["starting_finger"] - 1)  # window start
            with self.subTest(form=form["id"]):
                # Every offset inside the un-widened 4-fret window
                # [-(f-1), -(f-1)+3].
                self.assertTrue(all(lo <= o <= lo + 3 for o in offs),
                                (lo, sorted(set(offs))))
