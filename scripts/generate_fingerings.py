#!/usr/bin/env python
"""Generate every fingering-form YAML config from first principles.

Run from the repo root with the project venv:

    .venv/bin/python scripts/generate_fingerings.py [-o OUTPUT_DIR]

The script deletes all *.yaml/*.yml files in the output directory (default
practice/configs/fingerings/) and re-emits the full set:

  * 10 pentatonic CAGED boxes   ({major,minor} pentatonic x C A G E D)
  * 25 arpeggio CAGED shapes    (maj, min, maj7, min7, dom7 x C A G E D)
  *  6 scale finger forms       ({major, natural minor} x 1st/2nd/4th finger)

Output is fully deterministic (hand-formatted YAML, stable ordering), so
re-running the script always produces byte-identical files.

Generation rules (v2 Phase 0, hand-verified):

Pentatonic boxes
  For each string the playable offsets (relative to the root-on-low-E anchor)
  repeat every 12 frets: offset ≡ interval + shift (mod 12) with per-string
  shifts s6 +0, s5 +7, s4 +2, s3 +9, s2 +5, s1 +0. Sort the residues, extend
  the cyclic sequence, and start each string's sequence at the largest
  representative <= 0 (this picks e.g. -1 instead of 11 so box 1 hugs the
  anchor). Box k = the kth and (k+1)th entries of that per-string sequence.
  Ascending box order is named E, D, C, A, G (box 1 = E shape: root at
  offset 0 on string 6).

Arpeggio shapes
  Shape X's window = [min, max] offset across all strings of the same-letter
  pentatonic box (major-pentatonic windows for maj/maj7/dom7, minor-
  pentatonic for min/min7). The shape holds every offset in the window whose
  interval, (open_pc + offset + 8) mod 12, is a chord tone. Strings may end
  up with a single note.

Scale finger forms
  Finger f's window = offsets [-(f-1) .. -(f-1)+3] (4 frets); take every
  in-scale offset in the window on every string. If a form were incomplete
  (some scale interval never appearing) the window is widened by one fret on
  the side that fixes it and the YAML gains a comment noting this; no shipped
  form currently needs the widening.
"""

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCALES_FILE = REPO_ROOT / "practice" / "configs" / "scales.yaml"
DEFAULT_OUT_DIR = REPO_ROOT / "practice" / "configs" / "fingerings"

# Standard tuning pitch classes, string 6 (low E) -> string 1 (high e).
STANDARD_TUNING = {6: 4, 5: 9, 4: 2, 3: 7, 2: 11, 1: 4}
STRINGS = (6, 5, 4, 3, 2, 1)

# offset ≡ interval + shift (mod 12) per string, for the root_low_e anchor.
# (Equivalent to interval = (open_pc + offset + 8) mod 12.)
STRING_SHIFTS = {6: 0, 5: 7, 4: 2, 3: 9, 2: 5, 1: 0}

# Ascending CAGED box order; box 1 (root at offset 0 on string 6) = E shape.
SHAPE_ORDER = ("E", "D", "C", "A", "G")

# Arpeggio quality -> (scale id, parent pentatonic for box windows).
ARPEGGIOS = (
    ("major_arpeggio", "major_pentatonic"),
    ("minor_arpeggio", "minor_pentatonic"),
    ("major7_arpeggio", "major_pentatonic"),
    ("minor7_arpeggio", "minor_pentatonic"),
    ("dominant7_arpeggio", "major_pentatonic"),
)

SCALE_FORMS = ("major_scale", "natural_minor_scale")
SCALE_FINGERS = (1, 2, 4)

ORDINALS = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}


def load_scales():
    with open(SCALES_FILE) as fh:
        return yaml.safe_load(fh)


def interval_of(string, offset):
    """Key-independent interval of a note at `offset` under root_low_e."""
    return (STANDARD_TUNING[string] + offset + 8) % 12


def string_offset_sequence(string, intervals):
    """The 6-entry ascending offset sequence for one string.

    Residues of {interval + shift mod 12}, sorted, with the cyclic sequence
    phased to start at the largest representative <= 0 (so box 1 sits on the
    anchor; e.g. major pentatonic string 5 starts at -1, not 11).
    """
    base = sorted({(i + STRING_SHIFTS[string]) % 12 for i in intervals})
    extended = [b - 12 for b in base] + base + [b + 12 for b in base]
    start = max(idx for idx, o in enumerate(extended) if o <= 0)
    return extended[start:start + len(SHAPE_ORDER) + 1]


def pentatonic_boxes(intervals):
    """All 5 boxes: {shape_letter: {string: [low_offset, high_offset]}}."""
    sequences = {s: string_offset_sequence(s, intervals) for s in STRINGS}
    boxes = {}
    for k, shape in enumerate(SHAPE_ORDER):  # box k+1
        boxes[shape] = {
            s: [sequences[s][k], sequences[s][k + 1]] for s in STRINGS
        }
    return boxes


def box_window(box):
    """(min, max) offset of a pentatonic box across all strings."""
    offs = [o for pair in box.values() for o in pair]
    return min(offs), max(offs)


def arpeggio_shape(box, chord_intervals):
    """Every chord tone inside the box's [min, max] offset window."""
    lo, hi = box_window(box)
    shape = {}
    for s in STRINGS:
        shape[s] = [o for o in range(lo, hi + 1)
                    if interval_of(s, o) in chord_intervals]
        if not shape[s]:
            raise SystemExit(
                f"arpeggio shape has an empty string {s} in window "
                f"[{lo}, {hi}] for intervals {sorted(chord_intervals)}"
            )
    return shape


def covered_intervals(offsets):
    return {interval_of(s, o) for s, offs in offsets.items() for o in offs}


def scale_window_offsets(scale_intervals, lo, hi):
    return {
        s: [o for o in range(lo, hi + 1)
            if interval_of(s, o) in scale_intervals]
        for s in STRINGS
    }


def scale_finger_form(scale_intervals, finger):
    """Offsets for a finger form; returns (offsets, widened_side_or_None)."""
    lo = -(finger - 1)
    hi = lo + 3
    offsets = scale_window_offsets(scale_intervals, lo, hi)
    if set(scale_intervals) <= covered_intervals(offsets):
        return offsets, None
    for side, (wlo, whi) in (("low", (lo - 1, hi)), ("high", (lo, hi + 1))):
        widened = scale_window_offsets(scale_intervals, wlo, whi)
        if set(scale_intervals) <= covered_intervals(widened):
            return widened, side
    raise SystemExit(
        f"finger form {finger} incomplete even after widening to 5 frets "
        f"(intervals {sorted(scale_intervals)})"
    )


# ---------------------------------------------------------------------------
# YAML emission (hand-formatted for byte-for-byte determinism + comments)
# ---------------------------------------------------------------------------

GENERATED_HEADER = (
    "# GENERATED by scripts/generate_fingerings.py — do not edit by hand.\n"
    "# Regenerate with: .venv/bin/python scripts/generate_fingerings.py\n"
)


def offsets_yaml(offsets):
    lines = ["offsets:"]
    for s in STRINGS:
        lines.append(f"  {s}: [{', '.join(str(o) for o in offsets[s])}]")
    return "\n".join(lines) + "\n"


def intervals_comment(offsets):
    """Comment block spelling out each note's interval, for hand-checking."""
    lines = ["# interval = (open_string_pc + offset + 8) mod 12:"]
    for s in STRINGS:
        pairs = ", ".join(
            f"{o} -> {interval_of(s, o)}" for o in offsets[s]
        )
        lines.append(f"#   string {s} (pc {STANDARD_TUNING[s]}): {pairs}")
    return "\n".join(lines) + "\n"


def emit_caged(scale_id, scale_name, shape, offsets, extra_comment=""):
    slug = scale_id.replace("_", "-")
    return (
        f"{GENERATED_HEADER}"
        f"#\n"
        f"# {scale_name} — {shape} Shape (CAGED box "
        f"{SHAPE_ORDER.index(shape) + 1}).\n"
        f"{extra_comment}"
        f"{intervals_comment(offsets)}"
        f"id: {slug}-{shape.lower()}-shape\n"
        f"scale: {scale_id}\n"
        f'name: "{scale_name} — {shape} Shape"\n'
        f"caged_shape: {shape}\n"
        f"anchor: root_low_e\n"
        f"{offsets_yaml(offsets)}"
    )


def emit_scale_form(scale_id, scale_name, finger, offsets, widened):
    slug = scale_id.replace("_", "-")
    ord_f = ORDINALS[finger]
    lo = min(o for offs in offsets.values() for o in offs)
    hi = max(o for offs in offsets.values() for o in offs)
    widen_comment = (
        f"# NOTE: window widened by 1 fret on the {widened} side to reach "
        f"completeness.\n" if widened else ""
    )
    return (
        f"{GENERATED_HEADER}"
        f"#\n"
        f"# {scale_name} — {ord_f} Finger Form "
        f"(window offsets {lo}..{hi}).\n"
        f"{widen_comment}"
        f"{intervals_comment(offsets)}"
        f"id: {slug}-{ord_f}-finger-form\n"
        f"scale: {scale_id}\n"
        f'name: "{scale_name} — {ord_f} Finger Form"\n'
        f"starting_finger: {finger}\n"
        f"anchor: root_low_e\n"
        f"{offsets_yaml(offsets)}"
    )


def generate_all():
    """Return {filename: yaml_text} for all 41 configs (deterministic)."""
    scales = load_scales()
    files = {}

    # Pentatonic boxes (10).
    boxes_by_scale = {}
    for scale_id in ("major_pentatonic", "minor_pentatonic"):
        spec = scales[scale_id]
        boxes = pentatonic_boxes(spec["intervals"])
        boxes_by_scale[scale_id] = boxes
        for shape in SHAPE_ORDER:
            fname = f"{scale_id}_{shape.lower()}_shape.yaml"
            files[fname] = emit_caged(
                scale_id, spec["name"], shape, boxes[shape]
            )

    # Arpeggio shapes (25).
    for scale_id, parent_pent in ARPEGGIOS:
        spec = scales[scale_id]
        chord = set(spec["intervals"])
        for shape in SHAPE_ORDER:
            box = boxes_by_scale[parent_pent][shape]
            lo, hi = box_window(box)
            offsets = arpeggio_shape(box, chord)
            comment = (
                f"# Chord tones inside the {parent_pent} {shape}-shape box "
                f"window (offsets {lo}..{hi}).\n"
            )
            fname = f"{scale_id}_{shape.lower()}_shape.yaml"
            files[fname] = emit_caged(
                scale_id, spec["name"], shape, offsets, comment
            )

    # Scale finger forms (6).
    for scale_id in SCALE_FORMS:
        spec = scales[scale_id]
        for finger in SCALE_FINGERS:
            offsets, widened = scale_finger_form(spec["intervals"], finger)
            fname = f"{scale_id}_{ORDINALS[finger]}_finger_form.yaml"
            files[fname] = emit_scale_form(
                scale_id, spec["name"], finger, offsets, widened
            )

    return files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "-o", "--out-dir", type=Path, default=DEFAULT_OUT_DIR,
        help=f"output directory (default: {DEFAULT_OUT_DIR})",
    )
    args = parser.parse_args(argv)

    files = generate_all()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    stale = sorted(args.out_dir.glob("*.yaml")) + sorted(args.out_dir.glob("*.yml"))
    for path in stale:
        path.unlink()
    for fname in sorted(files):
        (args.out_dir / fname).write_text(files[fname])
    print(f"Wrote {len(files)} fingering configs to {args.out_dir} "
          f"(removed {len(stale)} stale files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
