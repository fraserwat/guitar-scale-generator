"""Music theory engine for the guitar scale practice game.

Scales and fingering forms are config-driven:
  * practice/configs/scales.yaml        — scale id -> {name, intervals}
  * practice/configs/fingerings/*.yaml  — one fingering form per file

Configs are validated aggressively at load time (declared shapes can contain
typos), and loading fails loudly with an error naming the offending file,
string, and offset.

Only the config loading touches the filesystem; everything else is pure and
unit-testable. No Django imports here.
"""

from collections.abc import Mapping
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import TypedDict

import yaml

CONFIG_DIR = Path(__file__).resolve().parent / "configs"
SCALES_FILE = CONFIG_DIR / "scales.yaml"
FINGERINGS_DIR = CONFIG_DIR / "fingerings"

# Note names use sharps only for v1.
# TODO: proper flat/sharp spelling per key (e.g. F major should spell Bb, not A#).
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

KEYS = list(NOTE_NAMES)  # all 12 pitch classes, named with sharps

DIRECTIONS = ["Ascending", "Descending"]

# Standard tuning, string 6 -> string 1 (low E to high E), as pitch classes.
STANDARD_TUNING = {
    6: 4,   # E
    5: 9,   # A
    4: 2,   # D
    3: 7,   # G
    2: 11,  # B
    1: 4,   # E
}

# Number of fret positions shown in the display window.
WINDOW_SIZE = 6

ANCHOR_STRATEGIES = ("root_low_e",)

# Scale categories drive the fingering-form label language:
#   pentatonic/arpeggio forms -> CAGED shapes ("E Shape")
#   scale forms               -> finger forms ("2nd Finger Form")
CATEGORIES = ("pentatonic", "arpeggio", "scale")
CAGED_CATEGORIES = ("pentatonic", "arpeggio")
CAGED_SHAPES = ("C", "A", "G", "E", "D")


class ConfigError(ValueError):
    """A scale/fingering config file is malformed or musically wrong."""


class Note(TypedDict):
    """One resolved fretboard position (JSON-serializable as-is)."""

    string: int
    fret: int
    pitch_class: int
    note_name: str
    is_root: bool


def _is_int(x: object) -> bool:
    """True for real ints; bool is excluded (bool subclasses int)."""
    return isinstance(x, int) and not isinstance(x, bool)


# ---------------------------------------------------------------------------
# Basic pitch helpers
# ---------------------------------------------------------------------------

def note_name(pitch_class: int) -> str:
    """Return the (sharp-spelled) note name for a pitch class 0-11."""
    if not _is_int(pitch_class):
        raise ValueError(f"Pitch class must be an int, got {pitch_class!r}")
    return NOTE_NAMES[pitch_class % 12]


def ordinal(n: int) -> str:
    """1 -> '1st', 2 -> '2nd', 3 -> '3rd', 4 -> '4th', 11 -> '11th', ..."""
    if not _is_int(n):
        raise ValueError(f"Ordinal needs an int, got {n!r}")
    if 10 <= n % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def key_to_pc(key: str) -> int:
    """Validate a key name and return its pitch class. Raises ValueError."""
    try:
        return NOTE_NAMES.index(key)
    except ValueError:
        raise ValueError(f"Unknown key: {key!r} (expected one of {NOTE_NAMES})")


def root_fret_low_e(key: str) -> int:
    """Fret of the root note on the low E string (string 6).

    Returns 12 instead of 0 for E, so the display window always has a full
    fret line on its left edge.
    """
    root_pc = key_to_pc(key)
    fret = (root_pc - STANDARD_TUNING[6]) % 12
    return 12 if fret == 0 else fret


# =============================================================================
# TODO(anchor strategies): "root_low_e" is the only v1 anchor. Future anchor
# strategies will be added here and selected per-fingering via the `anchor`
# field of the fingering config:
#   - CAGED shapes (5 boxes per key, anchored on different chord forms)
#   - 3-notes-per-string positions
#   - fully randomised window positions
# Each strategy maps (key) -> anchor fret; everything downstream (offset
# resolution, window computation, rendering) is strategy-agnostic.
# =============================================================================
def anchor_fret(key: str, anchor: str = "root_low_e") -> int:
    """Return the absolute anchor fret for a key under an anchor strategy."""
    if anchor == "root_low_e":
        return root_fret_low_e(key)
    raise ValueError(
        f"Unknown anchor strategy: {anchor!r} (expected one of {ANCHOR_STRATEGIES})"
    )


# ---------------------------------------------------------------------------
# Config loading + validation
# ---------------------------------------------------------------------------

@cache
def load_scales(path: str | Path | None = None) -> Mapping[str, dict]:
    """Load and validate scales.yaml.

    Returns a read-only {scale_id: {name, intervals, category}} mapping.
    (The result is cached and shared between callers — hence read-only.)
    """
    path = Path(path) if path else SCALES_FILE
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(f"{path}: expected a non-empty mapping of scale ids")

    scales = {}
    for scale_id, spec in raw.items():
        if not isinstance(spec, dict):
            raise ConfigError(f"{path}: scale {scale_id!r} must be a mapping")
        name = spec.get("name")
        intervals = spec.get("intervals")
        category = spec.get("category")
        if not isinstance(name, str) or not name:
            raise ConfigError(f"{path}: scale {scale_id!r} needs a non-empty 'name'")
        if (
            not isinstance(intervals, list)
            or not intervals
            or not all(isinstance(i, int) and 0 <= i <= 11 for i in intervals)
        ):
            raise ConfigError(
                f"{path}: scale {scale_id!r} 'intervals' must be a non-empty "
                f"list of ints in 0-11"
            )
        if category not in CATEGORIES:
            raise ConfigError(
                f"{path}: scale {scale_id!r} 'category' must be one of "
                f"{CATEGORIES}, got {category!r}"
            )
        scales[scale_id] = {
            "name": name,
            "intervals": list(intervals),
            "category": category,
        }
    return MappingProxyType(scales)


def scale_names(path: str | Path | None = None) -> list[str]:
    """Display names of all configured scales."""
    return [spec["name"] for spec in load_scales(path).values()]


def _validate_fingering(raw: object, path: Path, scales: Mapping[str, dict]) -> dict:
    """Validate one parsed fingering config. Returns the cleaned dict."""
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping at the top level")

    required = ("id", "scale", "name", "anchor", "offsets")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ConfigError(f"{path}: missing required field(s): {', '.join(missing)}")

    form_id = raw["id"]
    if not isinstance(form_id, str) or not form_id.strip():
        raise ConfigError(f"{path}: 'id' must be a non-empty string")

    scale_id = raw["scale"]
    if scale_id not in scales:
        raise ConfigError(
            f"{path}: unknown scale {scale_id!r} (known: {list(scales)})"
        )
    category = scales[scale_id]["category"]

    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise ConfigError(f"{path}: 'name' must be a non-empty string")

    # Category-dependent label field:
    #   pentatonic/arpeggio -> caged_shape (C|A|G|E|D), starting_finger forbidden
    #   scale               -> starting_finger (1-4), caged_shape forbidden
    caged_shape = raw.get("caged_shape")
    starting_finger = raw.get("starting_finger")
    if category in CAGED_CATEGORIES:
        if "starting_finger" in raw:
            raise ConfigError(
                f"{path}: 'starting_finger' is forbidden for category "
                f"{category!r} (use 'caged_shape')"
            )
        if caged_shape not in CAGED_SHAPES:
            raise ConfigError(
                f"{path}: 'caged_shape' is required for category {category!r} "
                f"and must be one of {CAGED_SHAPES}, got {caged_shape!r}"
            )
        starting_finger = None
        display_label = f"{caged_shape} Shape"
    else:  # category == "scale"
        if "caged_shape" in raw:
            raise ConfigError(
                f"{path}: 'caged_shape' is forbidden for category 'scale' "
                f"(use 'starting_finger')"
            )
        if not _is_int(starting_finger) or not 1 <= starting_finger <= 4:
            raise ConfigError(
                f"{path}: 'starting_finger' is required for category 'scale' "
                f"and must be an int 1-4, got {starting_finger!r}"
            )
        caged_shape = None
        display_label = f"{ordinal(starting_finger)} Finger Form"

    if raw["anchor"] not in ANCHOR_STRATEGIES:
        raise ConfigError(
            f"{path}: unknown anchor {raw['anchor']!r} "
            f"(expected one of {ANCHOR_STRATEGIES})"
        )

    offsets = raw["offsets"]
    if not isinstance(offsets, dict) or set(offsets) != {1, 2, 3, 4, 5, 6}:
        raise ConfigError(
            f"{path}: 'offsets' must have exactly the string keys 1-6, "
            f"got {sorted(offsets) if isinstance(offsets, dict) else offsets!r}"
        )
    for string, offs in offsets.items():
        if not isinstance(offs, list) or not offs or not all(map(_is_int, offs)):
            raise ConfigError(
                f"{path}: string {string}: offsets must be a non-empty list of ints"
            )

    all_offsets = [o for offs in offsets.values() for o in offs]
    span = max(all_offsets) - min(all_offsets)
    if span > WINDOW_SIZE - 1:
        raise ConfigError(
            f"{path}: form spans {span + 1} frets "
            f"(max {WINDOW_SIZE}): offsets {min(all_offsets)}..{max(all_offsets)}"
        )

    # Musical validation: every declared note must belong to the scale.
    # interval = (open_pc + anchor_fret + offset - root_pc) mod 12 is
    # key-independent for the root_low_e anchor, since
    # anchor_fret - root_pc == -open_pc_of_low_E == 8 (mod 12).
    interval_set = set(scales[scale_id]["intervals"])
    covered = set()
    # Iterate string 6 -> 1 so validation errors report low-string problems
    # first (matching how guitarists read the shapes).
    for string, offs in sorted(offsets.items(), reverse=True):
        for offset in offs:
            interval = (STANDARD_TUNING[string] + offset + 8) % 12
            if interval not in interval_set:
                raise ConfigError(
                    f"{path}: string {string}, offset {offset}: interval "
                    f"{interval} is not in scale {scale_id!r} "
                    f"(intervals {sorted(interval_set)})"
                )
            covered.add(interval)

    # Completeness: every interval of the scale must appear at least once
    # somewhere in the form.
    missing_intervals = sorted(interval_set - covered)
    if missing_intervals:
        raise ConfigError(
            f"{path}: form is incomplete — interval(s) "
            f"{missing_intervals} of scale {scale_id!r} never appear "
            f"(intervals {sorted(interval_set)})"
        )

    return {
        "id": form_id,
        "scale": scale_id,
        "name": raw["name"],
        "category": category,
        "display_label": display_label,
        "caged_shape": caged_shape,
        "starting_finger": starting_finger,
        "anchor": raw["anchor"],
        # Stored pre-sorted so resolve_form can iterate without re-sorting.
        "offsets": {s: sorted(offs) for s, offs in offsets.items()},
    }


@cache
def load_fingerings(
    dir_path: str | Path | None = None,
    scales_path: str | Path | None = None,
) -> Mapping[str, dict]:
    """Load and validate every fingering config.

    Returns a read-only {form_id: form} mapping — cached and shared between
    callers, so treat the contents as immutable.
    Raises ConfigError (loudly, at first use) if any file is invalid;
    exceptions are not cached, so every call retries a failed load.
    """
    dir_path = Path(dir_path) if dir_path else FINGERINGS_DIR
    scales = load_scales(scales_path)

    fingerings = {}
    files = sorted([*dir_path.glob("*.yaml"), *dir_path.glob("*.yml")])
    if not files:
        raise ConfigError(f"No fingering configs found in {dir_path}")
    for path in files:
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        form = _validate_fingering(raw, path, scales)
        if form["id"] in fingerings:
            raise ConfigError(
                f"{path}: duplicate fingering id {form['id']!r} "
                f"(already defined in another file)"
            )
        fingerings[form["id"]] = form
    return MappingProxyType(fingerings)


# ---------------------------------------------------------------------------
# Form resolution
# ---------------------------------------------------------------------------

def resolve_form(
    form_id: str,
    key: str,
    dir_path: str | Path | None = None,
    scales_path: str | Path | None = None,
) -> tuple[int, list[Note]]:
    """Resolve a fingering form in a key to absolute fretboard positions.

    Returns (window_start, notes) where notes is a list of dicts:
        {string: 1-6, fret: n, pitch_class: pc, note_name: str, is_root: bool}
    ordered low string (6) to high string (1), then by fret.

    The display window covers frets window_start .. window_start + 5.
    is_root is True iff the note's interval from the key's root is 0.

    Octave normalisation: the whole form (all strings together) is shifted
    by whole octaves until its lowest fret lands in [1, 12] — the lowest
    octave where every fret is >= 1. Open strings (fret 0) never occur, and
    shapes with high offsets render low on the neck instead of past fret 12.
    """
    fingerings = load_fingerings(dir_path, scales_path)
    if form_id not in fingerings:
        raise ValueError(
            f"Unknown fingering form: {form_id!r} (known: {list(fingerings)})"
        )
    form = fingerings[form_id]
    root_pc = key_to_pc(key)
    anchor = anchor_fret(key, form["anchor"])

    min_offset = min(o for offs in form["offsets"].values() for o in offs)
    # Octave normalisation: shift the whole form so its lowest fret is in
    # [1, 12]. Python floor division makes this a single exact step:
    # min_fret 0 or negative shifts up, min_fret > 12 shifts down.
    anchor -= 12 * ((anchor + min_offset - 1) // 12)
    window_start = anchor + min_offset  # == the form's lowest fret

    notes: list[Note] = []
    for string in range(6, 0, -1):  # string 6 (low E) first
        open_pc = STANDARD_TUNING[string]
        for offset in form["offsets"][string]:  # pre-sorted at load time
            fret = anchor + offset
            pc = (open_pc + fret) % 12
            notes.append({
                "string": string,
                "fret": fret,
                "pitch_class": pc,
                "note_name": note_name(pc),
                "is_root": pc == root_pc,
            })
    return window_start, notes
