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
                                         # string — A-root variants are
                                         # planned alongside the e-root ones)
scale: major_scale                # scale id from ../scales.yaml
name: "Major Scale — 4th Finger Form (E-root)"  # display name
starting_finger: 4                # int 1-4 — REQUIRED iff the scale's
                                  # category is "scale"; FORBIDDEN for
                                  # pentatonic/arpeggio
caged_shape: E                    # C|A|G|E|D — REQUIRED iff the category is
                                  # pentatonic or arpeggio; FORBIDDEN for
                                  # category "scale"
anchor: root_low_e                # transposition strategy (only root_low_e
                                  # exists): in a round's key, the whole form
                                  # shifts so the root lands on that key's
                                  # low-E root fret, then by whole octaves
                                  # until its lowest fret is in [1, 12]
example_key: A                    # must be exactly A — every TAB is authored
                                  # in the same fixed key (root = low E
                                  # fret 5)
tab:                              # the hand-authored TAB, low E to high e
  E: [5]
  A: [2, 4, 5]
  D: [2, 4]
  G: [1, 2, 4]
  B: [2, 3, 5]
  e: [2, 4, 5]
```

A `display_label` is derived by the engine (not stored in the config):
`"E Shape"` for pentatonic/arpeggio forms, `"4th Finger Form"` (correct
ordinal suffix) for scale forms.

## Authoring rules (enforced as hard errors at load time)

- `id`, `scale`, `name`, `anchor`, `example_key`, `tab` are required;
  `id` non-empty and unique across all files; `scale` must exist in
  `scales.yaml`; the legacy `offsets` schema is rejected with a hint.
- `example_key` must be `A`.
- `tab` must have exactly the string keys `E A D G B e` (low to high,
  case-sensitive), each a non-empty list of ints; a string may hold 1..n
  notes (arpeggio shapes have 1-note strings).
- Frets must be >= 1 — open strings don't transpose.
- **Start on the root**: the root (fret 5 on `E` in the key of A) must be in
  the TAB, and no note may sound below it. These forms are played from the
  low root up; conventionally you never play below it.
- The form must span at most 6 frets (`max fret - min fret <= 5`, the
  display-window width).
- Every note must belong to the referenced scale (checked in the example
  key), and every interval of the scale must appear at least once across
  the six strings (the error names the missing intervals).
