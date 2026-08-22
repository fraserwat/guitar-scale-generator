# guitar-scale-generator
Wanting a more efficient way of keeping up with scales, not forgetting them, but also not spending too much time on them. Also a proof of concept for Claude Fable 5.

## TODOs

- [x] Real TAB rendering.
- [x] Validate with Major Scale forms.
- [x] Reset DJANGO_SECRET_KEY in .env.
- [x] Separate correct & incorrect in results (incorrect first).
- [x] Flat/sharp spelling.
- [x] Descending / Ascending in Orange pop to make it easier to see.
- [x] Select scale types from practice menu.
- [x] Repeat two turns later if incorrect.
- [ ] 7-string scale forms.

Nice-to-haves (no code scaffolding for these — by design):

- [ ] Users/auth.
- [ ] Spaced repetition algorithm.

## Adding a new scale form

- Write the form as a TAB, by hand, in the key of A (root = low E fret 5) — the TAB is the source of truth; the scale diagram and rendered TAB are both built from it.
- Create a yaml file in `practice/configs/fingerings/` (full schema + authoring rules: `practice/configs/fingerings/README.md`) with:
  - `id` — unique slug naming the root string (e.g. `major-scale-e-root-1st-finger-form` vs `major-scale-a-root-1st-finger-form`)
  - `scale` — an id from `practice/configs/scales.yaml`
  - `name` — display name
  - `anchor` — the string the root anchors on: `root_low_e`, `root_low_a`, `root_low_d` or `root_low_g` — plus `example_key: A`
  - `tab` — string labels `E A D G B e` (low to high), each a list of frets; span ≤ 6 frets; frets ≥ 1
  - plus `starting_finger` (1-4) for scale- and arpeggio-category forms (arpeggio forms are derived from the same-finger scale forms), or `caged_shape` (`C|A|G|E|D`) for pentatonic forms
- Convention (validated as hard errors): the root must appear on the anchor string (fret 5 on low E in A for `root_low_e`, etc.). Scale/arpeggio finger forms **start on the root** — nothing may sound below it; pentatonic CAGED boxes are exempt (they span the whole position). Every note must be in the scale and every scale interval must appear somewhere.
- The app auto-loads every yaml in that directory — no registration step. Loading is cached, so restart the server to pick up changes.
