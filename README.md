# guitar-scale-generator
Wanting a more efficient way of keeping up with scales, not forgetting them, but also not spending too much time on them. Also a proof of concept for Claude Fable 5.

## TODOs

- [x] Real TAB rendering.
- [ ] Validate with Major Scale forms.
- [ ] Reset DJANGO_SECRET_JEY in .env.
- [ ] Separate correct & incorrect in results (incorrect first).
- [ ] Confirm & update scale configs.
- [ ] Flat/sharp spelling.
- [ ] Reconcile with fraserwatt.dev website theme.
- [ ] Select scale types from practice menu.
- [ ] Repeat in Queue+3 if incorrect.
- [ ] 7-string scale forms.
- [ ] Users/auth.
- [ ] Spaced repetition algorithm.
- [ ] Config hot-reload.

## Adding a new scale form

- Write the form as a TAB, by hand, in the key of A (root = low E fret 5) — the TAB is the source of truth; the scale diagram and rendered TAB are both built from it.
- Create a yaml file in `practice/configs/fingerings/` (full schema + authoring rules: `practice/configs/fingerings/README.md`) with:
  - `id` — unique slug naming the root string (e.g. `major-scale-e-root-1st-finger-form`; A-root variants are planned, so be specific)
  - `scale` — an id from `practice/configs/scales.yaml`
  - `name` — display name
  - `anchor: root_low_e` and `example_key: A`
  - `tab` — string labels `E A D G B e` (low to high), each a list of frets; span ≤ 6 frets; frets ≥ 1
  - plus `starting_finger` (1-4) for scale-category forms, or `caged_shape` (`C|A|G|E|D`) for pentatonic/arpeggio forms
- Convention (validated as hard errors): the form **starts on the root** — the low-E root (fret 5 in A) must be present and nothing may sound below it. Every note must be in the scale and every scale interval must appear somewhere.
- The app auto-loads every yaml in that directory — no registration step. Loading is cached, so restart the server to pick up changes.
