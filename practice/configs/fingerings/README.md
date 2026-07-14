# Fingering (scale form) configs

Each YAML file in this directory defines one fingering form as a
**hand-authored TAB** — the source of truth. Which frets a form actually
uses is playing convention, which interval math can't derive, so the TAB is
written by hand and the theory engine (`practice/theory.py`) acts as a
validator: all files are loaded and checked at first use, and a bad config
fails loudly with an error naming the file, string, and fret.

Both the neck diagram and the rendered TAB are derived from the authored
TAB (converted once, at load time, to anchor-relative offsets and then
transposed to the round's key).

## Schema

```yaml
id: major-scale-e-root-4th-finger-form   # stable unique ID (referenced by
                                         # AttemptLog; include the root
                                         # string — e-root / a-root — so
                                         # same-finger variants stay distinct)
scale: major_scale                # scale id from ../scales.yaml
name: "Major Scale — 4th Finger Form (E-root)"  # display name
starting_finger: 4                # int 1-4 — REQUIRED iff the scale's
                                  # category is "scale" or "arpeggio"
                                  # (arpeggio forms are derived from the
                                  # same-finger scale forms); FORBIDDEN for
                                  # pentatonic
caged_shape: E                    # C|A|G|E|D — REQUIRED iff the category is
                                  # pentatonic; FORBIDDEN for scale/arpeggio
anchor: root_low_e                # transposition strategy — root_low_e
                                  # (root on the low E string) or root_low_a
                                  # (root on the A string): in a round's key,
                                  # the whole form shifts so the root lands
                                  # on that key's root fret on the anchor
                                  # string, then by whole octaves until its
                                  # lowest fret is in [1, 12]
example_key: A                    # must be exactly A — every TAB is authored
                                  # in the same fixed key (root = low E
                                  # fret 5 for root_low_e, A string fret 12
                                  # for root_low_a)
tab:                              # the hand-authored TAB, low E to high e
  E: [5]
  A: [2, 4, 5]
  D: [2, 4]
  G: [1, 2, 4]
  B: [2, 3, 5]
  e: [2, 4, 5]
```

A `display_label` is derived by the engine (not stored in the config):
`"E Shape"` for pentatonic forms, `"4th Finger Form (E-root)"` (correct
ordinal suffix plus the anchor string) for scale and arpeggio forms — the
root suffix is what tells the two same-finger variants apart in the UI.

## Authoring rules (enforced as hard errors at load time)

- `id`, `scale`, `name`, `anchor`, `example_key`, `tab` are required;
  `id` non-empty and unique across all files; `scale` must exist in
  `scales.yaml`; the legacy `offsets` schema is rejected with a hint.
- `example_key` must be `A`.
- `tab` must have exactly the string keys `E A D G B e` (low to high,
  case-sensitive), each a list of ints; a string may hold 0..n notes —
  write `e: []` explicitly for a string the form skips (arpeggio shapes
  often have 1-note or skipped strings). A *missing* string key is still
  an error, so typos fail loudly. At least one string must have notes.
- Frets must be >= 1 — open strings don't transpose.
- **Root on the anchor string** (all forms): the root must appear on the
  string named by `anchor` (in the key of A: fret 5 on `E` for root_low_e,
  fret 12 on `A` for root_low_a) — that is what transposition anchors on.
- **Start on the root** (scale/arpeggio finger forms only): no note may
  sound below the root. These forms are played from the low root up;
  conventionally you never play below it. Pentatonic CAGED boxes are
  exempt — they span the whole position and may play below the root
  (e.g. low-E notes under an A-string root).
- The form must span at most 6 frets (`max fret - min fret <= 5`, the
  display-window width).
- Every note must belong to the referenced scale (checked in the example
  key), and every interval of the scale must appear at least once across
  the six strings (the error names the missing intervals).
