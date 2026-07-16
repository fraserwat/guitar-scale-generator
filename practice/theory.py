"""Music theory engine for ScaleRunner, the guitar scale practice game.

Scales and fingering forms are config-driven:
  * practice/configs/scales.yaml        — scale id -> {name, intervals}
  * practice/configs/fingerings/*.yaml  — one fingering form per file

Each fingering form is a hand-authored TAB written in the fixed example key
(EXAMPLE_KEY): convention — which frets a form actually uses — is empirical
knowledge that interval math can't derive, so the TAB is the source of truth
and the theory here acts as a validator. The loader converts the TAB to
anchor-relative offsets once, at load time; everything downstream (transposing
to a key, the neck diagram, the rendered TAB) derives from that.

Configs are validated aggressively at load time (hand-authored TABs can
contain typos), and loading fails loudly with an error naming the offending
file, string, and fret.

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

# Canonical (sharp-spelled) chromatic note names, one per pitch class.
# Sharp-spelled and natural keys display these names; flat-spelled keys get
# proper per-key diatonic spelling instead (see spell_scale / resolve_form).
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

KEYS = list(NOTE_NAMES)  # all 12 pitch classes, named with sharps

# The 5 accidental (black-key) roots and their flat enharmonic spellings.
SHARP_TO_FLAT = {"C#": "Db", "D#": "Eb", "F#": "Gb", "G#": "Ab", "A#": "Bb"}
FLAT_TO_SHARP = {flat: sharp for sharp, flat in SHARP_TO_FLAT.items()}
FLAT_KEYS = list(SHARP_TO_FLAT.values())

# Every key spelling the app accepts: 12 sharp-spelled + 5 flat-spelled.
VALID_KEYS = KEYS + FLAT_KEYS

# Diatonic spelling machinery: the 7 letters, their natural pitch classes,
# and how many letter steps above the root letter each semitone interval
# sits (any kind of third = 2 letter steps, etc.; the tritone (6) is
# spelled as a diminished fifth).
LETTERS = "CDEFGAB"
NATURAL_PCS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
INTERVAL_LETTER_STEPS = {
    0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3,
    6: 4, 7: 4, 8: 5, 9: 5, 10: 6, 11: 6,
}

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

# Form ids are stored in the AttemptLog.form_id column (max_length=64);
# bounding them here keeps every loadable id insertable on strict backends
# (SQLite would silently accept longer values). No Django import: the model
# mirrors this constant rather than the reverse.
FORM_ID_MAX_LENGTH = 64

# Anchor strategy -> the string carrying the root that transposition anchors
# on. Each strategy maps a key to the fret of its root on that string;
# everything downstream (offset resolution, window computation, rendering)
# is strategy-agnostic.
ANCHOR_ROOT_STRINGS = {
    "root_low_e": 6,
    "root_low_a": 5,
    "root_low_d": 4,  # D-shape CAGED boxes anchor on the D-string root
    "root_low_g": 3,  # G-shape CAGED boxes anchor on the G-string root
}
ANCHOR_STRATEGIES = tuple(ANCHOR_ROOT_STRINGS)

# All TABs are authored in this one key (root = low E fret 5). A single fixed
# key keeps hand-authored configs directly comparable and the loader trivial.
EXAMPLE_KEY = "A"

# TAB string labels (standard tuning, low E to high e) -> string numbers.
TAB_STRINGS = {"E": 6, "A": 5, "D": 4, "G": 3, "B": 2, "e": 1}

# Semitones of each open string ABOVE the open low E — absolute pitch, not
# pitch class. Used to reject notes that sound below the low root:
# scale/arpeggio finger forms "start on the root" and never play below it
# (pentatonic CAGED boxes are exempt — they span the whole position).
STRING_BASE_SEMITONES = {6: 0, 5: 5, 4: 10, 3: 15, 2: 19, 1: 24}

# Scale categories drive the fingering-form label language:
#   pentatonic forms      -> CAGED shapes ("E Shape")
#   scale/arpeggio forms  -> finger forms ("2nd Finger Form"; the arpeggio
#                            forms are derived from the same-finger scale
#                            forms, so they share the finger-form language)
CATEGORIES = ("pentatonic", "arpeggio", "scale")
CAGED_CATEGORIES = ("pentatonic",)
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


def parse_note_name(name: str) -> tuple[str, int]:
    """Split a spelled note into (letter, accidental offset).

    'Gb' -> ('G', -1), 'C#' -> ('C', 1), 'A' -> ('A', 0), 'Bbb' -> ('B', -2).
    Raises ValueError for anything that isn't a letter plus uniform
    accidentals.
    """
    if not isinstance(name, str) or not name or name[0] not in NATURAL_PCS:
        raise ValueError(f"Invalid note name: {name!r}")
    accidentals = name[1:]
    if not accidentals:
        offset = 0
    elif set(accidentals) == {"#"}:
        offset = len(accidentals)
    elif set(accidentals) == {"b"}:
        offset = -len(accidentals)
    else:
        raise ValueError(f"Invalid note name: {name!r}")
    return name[0], offset


def note_name_to_pc(name: str) -> int:
    """Pitch class 0-11 of any spelled note ('Gb' -> 6, 'Cb' -> 11, 'E#' -> 5)."""
    letter, offset = parse_note_name(name)
    return (NATURAL_PCS[letter] + offset) % 12


def key_to_pc(key: str) -> int:
    """Validate a key name and return its pitch class. Raises ValueError.

    Accepts the 12 sharp-spelled names plus the 5 flat enharmonic spellings
    of the accidental keys (Db, Eb, Gb, Ab, Bb).
    """
    if key not in VALID_KEYS:
        raise ValueError(f"Unknown key: {key!r} (expected one of {VALID_KEYS})")
    return note_name_to_pc(key)


def spell_interval(key: str, interval: int) -> str:
    """Spell the note `interval` semitones above the root of `key`.

    The spelling walks letter names from the key's own root letter, so it is
    consistent with the key: the perfect 4th of Gb is Cb (not B), the major
    7th of F# is E# (not F).
    """
    if not _is_int(interval):
        raise ValueError(f"Interval must be an int, got {interval!r}")
    letter, _ = parse_note_name(key)
    root_pc = note_name_to_pc(key)
    steps = INTERVAL_LETTER_STEPS[interval % 12]
    target_letter = LETTERS[(LETTERS.index(letter) + steps) % 7]
    offset = (root_pc + interval - NATURAL_PCS[target_letter]) % 12
    if offset > 6:  # pick the nearer accidental direction (e.g. -1, not +11)
        offset -= 12
    return target_letter + ("#" * offset if offset >= 0 else "b" * -offset)


def spell_scale(key: str, intervals: list[int]) -> dict[int, str]:
    """Map pitch class -> correctly spelled note name for a scale in a key.

    E.g. spell_scale('Gb', major intervals) spells Gb Ab Bb Cb Db Eb F.
    """
    root_pc = note_name_to_pc(key)
    return {(root_pc + i) % 12: spell_interval(key, i) for i in intervals}


def anchor_fret(key: str, anchor: str = "root_low_e") -> int:
    """Return the absolute anchor fret for a key under an anchor strategy.

    The anchor fret is where the key's root sits on the strategy's root
    string; 12 is returned instead of 0, so frets stay >= 1 and the display
    window always has a full fret line on its left edge.
    """
    if anchor not in ANCHOR_ROOT_STRINGS:
        raise ValueError(
            f"Unknown anchor strategy: {anchor!r} (expected one of {ANCHOR_STRATEGIES})"
        )
    fret = (key_to_pc(key) - STANDARD_TUNING[ANCHOR_ROOT_STRINGS[anchor]]) % 12
    return 12 if fret == 0 else fret


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

    if "offsets" in raw:
        raise ConfigError(
            f"{path}: legacy 'offsets' schema — forms are now defined as a "
            f"hand-authored 'tab' in the fixed example key {EXAMPLE_KEY!r} "
            f"(see practice/configs/fingerings/README.md)"
        )

    required = ("id", "scale", "name", "anchor", "example_key", "tab")
    missing = [k for k in required if k not in raw]
    if missing:
        raise ConfigError(f"{path}: missing required field(s): {', '.join(missing)}")

    form_id = raw["id"]
    if not isinstance(form_id, str) or not form_id.strip():
        raise ConfigError(f"{path}: 'id' must be a non-empty string")
    if len(form_id) > FORM_ID_MAX_LENGTH:
        raise ConfigError(
            f"{path}: 'id' must be at most {FORM_ID_MAX_LENGTH} characters "
            f"(the attempt-log column bound), got {len(form_id)}"
        )

    scale_id = raw["scale"]
    if scale_id not in scales:
        raise ConfigError(
            f"{path}: unknown scale {scale_id!r} (known: {list(scales)})"
        )
    category = scales[scale_id]["category"]

    if not isinstance(raw["name"], str) or not raw["name"].strip():
        raise ConfigError(f"{path}: 'name' must be a non-empty string")

    if raw["anchor"] not in ANCHOR_STRATEGIES:
        raise ConfigError(
            f"{path}: unknown anchor {raw['anchor']!r} "
            f"(expected one of {ANCHOR_STRATEGIES})"
        )
    root_string = ANCHOR_ROOT_STRINGS[raw["anchor"]]
    root_label = next(l for l, s in TAB_STRINGS.items() if s == root_string)

    # Category-dependent label field:
    #   pentatonic      -> caged_shape (C|A|G|E|D), starting_finger forbidden
    #   scale/arpeggio  -> starting_finger (1-4), caged_shape forbidden
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
    else:  # category in ("scale", "arpeggio")
        if "caged_shape" in raw:
            raise ConfigError(
                f"{path}: 'caged_shape' is forbidden for category "
                f"{category!r} (use 'starting_finger')"
            )
        if not _is_int(starting_finger) or not 1 <= starting_finger <= 4:
            raise ConfigError(
                f"{path}: 'starting_finger' is required for category "
                f"{category!r} and must be an int 1-4, got {starting_finger!r}"
            )
        caged_shape = None
        display_label = f"{ordinal(starting_finger)} Finger Form ({root_label}-root)"

    if raw["example_key"] != EXAMPLE_KEY:
        raise ConfigError(
            f"{path}: 'example_key' must be {EXAMPLE_KEY!r} (all TABs are "
            f"authored in the same fixed key), got {raw['example_key']!r}"
        )

    tab = raw["tab"]
    if not isinstance(tab, dict) or set(tab) != set(TAB_STRINGS):
        raise ConfigError(
            f"{path}: 'tab' must have exactly the string keys "
            f"{list(TAB_STRINGS)} (low E to high e), got "
            f"{sorted(tab, key=str) if isinstance(tab, dict) else tab!r}"
        )
    for label, frets in tab.items():
        if not isinstance(frets, list) or not all(map(_is_int, frets)):
            raise ConfigError(
                f"{path}: string {label}: tab must be a list of ints "
                f"(use [] for a string the form skips)"
            )
        for fret in frets:
            if fret < 1:
                raise ConfigError(
                    f"{path}: string {label}, fret {fret}: frets must be "
                    f">= 1 (open strings don't transpose)"
                )

    example_anchor = anchor_fret(EXAMPLE_KEY, raw["anchor"])  # root fret on the anchor string

    all_frets = [f for frets in tab.values() for f in frets]
    if not all_frets:
        raise ConfigError(f"{path}: tab has no notes on any string")
    span = max(all_frets) - min(all_frets)
    if span > WINDOW_SIZE - 1:
        raise ConfigError(
            f"{path}: form spans {span + 1} frets "
            f"(max {WINDOW_SIZE}): frets {min(all_frets)}..{max(all_frets)}"
        )

    # The root must appear on the anchor string — that is what transposition
    # anchors on, so it holds for every category. The stricter "start on the
    # root" convention (no note sounds below it) applies only to scale and
    # arpeggio finger forms; pentatonic CAGED boxes span the whole position
    # and may play below the root.
    if example_anchor not in tab[root_label]:
        raise ConfigError(
            f"{path}: the root ({EXAMPLE_KEY} at fret {example_anchor}) must "
            f"appear on string {root_label} — the anchor string carries the root"
        )
    if category not in CAGED_CATEGORIES:
        root_abs = STRING_BASE_SEMITONES[root_string] + example_anchor
        for label, frets in tab.items():
            string = TAB_STRINGS[label]
            for fret in frets:
                if STRING_BASE_SEMITONES[string] + fret < root_abs:
                    raise ConfigError(
                        f"{path}: string {label}, fret {fret}: sounds below "
                        f"the low root ({EXAMPLE_KEY} at {root_label}-string "
                        f"fret {example_anchor}) — finger forms never play "
                        f"below the root"
                    )

    # Musical validation in the example key: every declared note must belong
    # to the scale. TAB_STRINGS iterates low E -> high e, so validation
    # errors report low-string problems first (matching how guitarists read
    # the shapes).
    root_pc = key_to_pc(EXAMPLE_KEY)
    interval_set = set(scales[scale_id]["intervals"])
    covered = set()
    for label, string in TAB_STRINGS.items():
        for fret in tab[label]:
            pc = (STANDARD_TUNING[string] + fret) % 12
            interval = (pc - root_pc) % 12
            if interval not in interval_set:
                raise ConfigError(
                    f"{path}: string {label}, fret {fret}: {note_name(pc)} "
                    f"(interval {interval}) is not in scale {scale_id!r} "
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
        "tab": {label: sorted(frets) for label, frets in tab.items()},
        # Anchor-relative offsets derived from the TAB; everything downstream
        # (resolve_form, the diagrams) consumes these. Pre-sorted so
        # resolve_form can iterate without re-sorting.
        "offsets": {
            TAB_STRINGS[label]: sorted(f - example_anchor for f in frets)
            for label, frets in tab.items()
        },
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

    Note spelling follows the key: sharp-spelled and natural keys use the
    canonical sharp chromatic names; flat-spelled keys (Db, Eb, Gb, Ab, Bb)
    spell the whole scale diatonically in flats (e.g. Gb major is
    Gb Ab Bb Cb Db Eb F — including Cb, never B).

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

    # Per-key spelling: flat keys get a diatonic pc -> name map built from
    # the scale's intervals. The map is total — the loader rejects any form
    # note outside its scale — so a KeyError here means a validator bug and
    # should surface, not be papered over.
    if key in FLAT_KEYS:
        scales = load_scales(scales_path)
        spelling = spell_scale(key, scales[form["scale"]]["intervals"])

        def name_of(pc: int) -> str:
            return spelling[pc]
    else:
        name_of = note_name

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
                "note_name": name_of(pc),
                "is_root": pc == root_pc,
            })
    return window_start, notes
