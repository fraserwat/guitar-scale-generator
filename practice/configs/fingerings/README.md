# Fingering (scale form) configs

Files live under a subfolder per scale category — `scales/`, `pentatonics/`,
`arpeggios/`, `chords/` — loaded recursively (`load_fingerings()` globs
`**/*.yaml`), so any further nesting inside those (e.g. `chords/major7/`)
needs no code change. The subfolder is purely organisational; nothing reads
the path itself, only the `scale`/`category` fields below.

Each YAML file defines one fingering form as a **hand-authored TAB** — the
source of truth. Which frets a form actually uses is playing convention,
which interval math can't derive, so the TAB is written by hand and the
theory engine (`practice/theory.py`) acts as a validator: all files are
loaded and checked at first use, and a bad config fails loudly with an
error naming the file, string, and fret.

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
                                  # pentatonic and chord
caged_shape: E                    # C|A|G|E|D — REQUIRED iff the category is
                                  # pentatonic; FORBIDDEN otherwise
                                  # (chord-category forms need neither field
                                  # — the label comes from the scale's own
                                  # `inversion`, see ../scales.yaml)
anchor: root_low_e                # transposition strategy — the string the
                                  # root anchors on: root_low_e, root_low_a,
                                  # root_low_d or root_low_g. In a round's
                                  # key, the whole form shifts so the root
                                  # lands on that key's root fret on the
                                  # anchor string, then by whole octaves
                                  # until its lowest fret is in [1, 12]
example_key: A                    # must be exactly A — every TAB is authored
                                  # in the same fixed key (root fret on the
                                  # anchor string: E 5, A 12, D 7, G 2)
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
ordinal suffix plus the anchor string) for scale and arpeggio forms,
`"E Root (1st Inversion)"` for chord forms — the anchor-string suffix is
what tells same-inversion variants (e.g. E-root vs A-root) apart in the UI.

Chord-category forms are a fully separate concept from arpeggios — see
`../scales.yaml`'s comment header. Each chord-category *scale* (not the
fingering form) declares one `inversion` (0-3, an index into that scale's
own `intervals` — 0 is root position) and a `menu_group`
(`core_diatonic` | `altered`), so there's one scale entry per (chord type,
inversion), e.g. `major7_chord_0th_inv` .. `major7_chord_3rd_inv`. A chord
fingering form just references one of those scales via `scale:` — it
carries neither `starting_finger` nor `caged_shape`.

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
- **Root on the anchor string, nothing below it** (pentatonic, scale,
  arpeggio): the root must appear on the string named by `anchor` (in the
  key of A: fret 5 on `E` for root_low_e, fret 12 on `A` for root_low_a,
  fret 7 on `D` for root_low_d, fret 2 on `G` for root_low_g) — that fret
  is what transposition anchors on. Each CAGED pentatonic box anchors on
  the string carrying its root: E shape → root_low_e, D shape →
  root_low_d, C and A shapes → root_low_a, G shape → root_low_g (in A the
  boxes sit at G 2-5, E 5-8, D 7-10, C 9-13, A 12-15 for minor; G 2-5,
  E 4-7, D 6-10, C 9-12, A 11-14 for major). Scale/arpeggio finger forms
  additionally require no note sound below that root fret — they're
  played from the low root up. Pentatonic CAGED boxes are exempt from the
  "nothing below" half — they span the whole position (e.g. low-E notes
  under an A-string root).
- **Bass note on the anchor string matches the inversion** (chord forms
  only): the anchor string carries whichever chord tone is *this
  inversion's* bass note — not necessarily the root. The lowest-sounding
  note in the whole form must (a) be on the `anchor` string and (b) have
  the interval from the root that the scale's `inversion` specifies (0 →
  root, 1 → the scale's 2nd interval — the 3rd, 2 → the 5th, 3 → the
  7th). `anchor_fret` (the transposition reference fret) is unchanged by
  this — it's still purely "where the key's root would sit on this
  string," a fixed reference point independent of what's actually played
  there.
- The form must span at most 6 frets (`max fret - min fret <= 5`, the
  display-window width).
- Every note must belong to the referenced scale (checked in the example
  key), and every interval of the scale must appear at least once across
  the six strings (the error names the missing intervals).
