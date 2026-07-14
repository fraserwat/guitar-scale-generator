# Fingering (scale form) configs

Each YAML file in this directory defines one fingering form of a scale.
All files are loaded and validated at first use; a bad config fails loudly
with an error naming the file, string, and offset.

## Generated — do not edit by hand

Every YAML here is emitted by `scripts/generate_fingerings.py` from the
Phase-0 generative rules (pentatonic CAGED boxes, arpeggio shapes cut from
the matching pentatonic box windows, scale finger forms from 4-fret
windows). To change the shipped forms, edit the generator and re-run it:

```
.venv/bin/python scripts/generate_fingerings.py
```

The script deletes all `*.yaml`/`*.yml` in this directory and re-writes the
full set (currently 41: 10 pentatonic + 25 arpeggio + 6 scale finger forms).
Output is deterministic — re-running produces byte-identical files.

## Schema

```yaml
id: minor-pentatonic-e-shape  # stable unique ID (referenced by AttemptLog and
                              # the future spaced-repetition algorithm)
scale: minor_pentatonic       # scale id from ../scales.yaml
name: "Minor Pentatonic — E Shape"  # display name shown to the player
caged_shape: E                # C|A|G|E|D — REQUIRED iff the scale's category
                              # is pentatonic or arpeggio; FORBIDDEN for
                              # category "scale"
starting_finger: 2            # int 1-4 — REQUIRED iff the scale's category is
                              # "scale"; FORBIDDEN for pentatonic/arpeggio
anchor: root_low_e            # anchor strategy. Only "root_low_e"
                              # (anchor fret = fret of the root on the low E
                              # string, 12 instead of 0). At resolution time
                              # the anchor shifts up an octave if the form
                              # would render below fret 1.
offsets:                      # per string (6 = low E ... 1 = high e):
  6: [0, 3]                   # fret offsets RELATIVE to the anchor fret.
  5: [0, 2]                   # Absolute fret = anchor_fret + offset.
  4: [0, 2]                   # Negative offsets are allowed (form sits partly
  3: [0, 2]                   # below the anchor). A string may hold 1..n
  2: [0, 3]                   # notes (arpeggio shapes have 1-note strings).
  1: [0, 3]
```

A `display_label` is derived by the engine (not stored in the config):
`"E Shape"` for pentatonic/arpeggio forms, `"2nd Finger Form"` (correct
ordinal suffix) for scale forms.

## Validation rules (enforced at load time)

- `id`, `scale`, `name`, `anchor`, `offsets` are required.
- `id` must be a non-empty string, unique across all files.
- `scale` must exist in `scales.yaml` (which also declares each scale's
  `category`: pentatonic | arpeggio | scale).
- `caged_shape` (one of C A G E D) is required for pentatonic/arpeggio
  scales and forbidden for `scale`-category scales; `starting_finger`
  (int 1-4) is required for `scale`-category scales and forbidden otherwise.
- `anchor` must be a known strategy (currently only `root_low_e`).
- `offsets` must have exactly the string keys 1-6, each a non-empty list of
  ints (1..n notes per string).
- The form must span at most 6 frets: `max(offset) - min(offset) <= 5`
  (the display window is 6 frets wide, starting at `anchor_fret +
  min(offset)`, shifted up an octave when that would be below fret 1).
- Every note must belong to the referenced scale:
  `(open_string_pc + offset + 8) mod 12` must be in the scale's interval set
  (the `+8` folds in the root-on-low-E anchor; the check is key-independent).
- Completeness: every interval of the referenced scale must appear at least
  once somewhere across the form's six strings; the error names the missing
  interval(s).
