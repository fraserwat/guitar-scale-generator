# guitar-scale-generator
Wanting a more efficient way of keeping up with scales, not forgetting them, but also not spending too much time on them. Also a proof of concept for Claude Fable 5.

## TODOs

- [ ] Validate with Major Scale forms.
- [ ] Put secret key in .env and push to production.
- [ ] Separate correct & incorrect in results (incorrect first).
- [ ] Confirm & update scale configs.
- [ ] Real TAB rendering.
- [ ] Flat/sharp spelling.
- [ ] Reconcile with fraserwatt.dev website theme.
- [ ] Select scale types from practice menu.
- [ ] Repeat in Queue+3 if incorrect.
- [ ] 7-string scale forms.
- [ ] Users/auth.
- [ ] Spaced repetition algorithm.
- [ ] Config hot-reload.

## Adding a new scale form

- Create a yaml file in `practice/configs/fingerings/` (full schema: `practice/configs/fingerings/README.md`) with:
  - `id` — unique slug (e.g. `major-scale-1st-finger-form`)
  - `scale` — an id from `practice/configs/scales.yaml`
  - `name` — display name
  - `anchor: root_low_e`
  - `offsets` — keys `6` → `1` (low E to high E), per-string fret offsets relative to the anchor; total span ≤ 6 frets
  - plus `starting_finger` (1-4) for scale-category forms, or `caged_shape` (`C|A|G|E|D`) for pentatonic/arpeggio forms
- The app auto-loads every yaml in that directory — no registration step. Loading is cached, so restart the server to pick up changes.
- **WARNING:** running `scripts/generate_fingerings.py` deletes every yaml in `practice/configs/fingerings/` and regenerates ALL 41 original forms — undoing the current pruning down to the 3 E-root major-scale forms.
