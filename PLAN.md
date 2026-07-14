# ScaleRunner (guitar scale practice app) — v2 Build Plan

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked/issue.
(v1 shipped 2026-07-13: config-driven pentatonic forms, exhaustive 50-test suite, verified. This plan replaces the v1 doc.)

**Agents:** `plan-1` (Plan agent) stalled twice on the offset-table derivation and was abandoned; Phase 0 design completed by the orchestrator directly. Phases 1–4 delegated to build agent `build-2`; Phase 5 verification by orchestrator.

---

## BugFinder report (2026-07-14, automated bug-hunt output)

Whole-repo sweep: theory.py, views.py, generator script, tests, settings, YAML configs.
Test suite: 84/84 green at end of hunt.

### Finding 1 (only finding, low severity) — FIXED 2026-07-14 (v3, agent A)
`POST /api/log/` accepts an unbounded `form_id` and stores it past the model's
declared limit.
- Location: practice/views.py:76-77 (validation) vs practice/models.py:14
  (`form_id = models.CharField(max_length=64)`).
- Repro: POST `{"form_id": "x"*5000, "scale": "Minor Pentatonic", "key": "A",
  "direction": "Ascending", "correct": true}` → 201; stored form_id length
  5000 vs declared max_length 64 (SQLite ignores VARCHAR length).
- On a strict backend (PostgreSQL / strict MySQL) the same request would raise
  DataError at AttemptLog.objects.create() → 500, violating the endpoint's
  "400 never 500 on bad input" contract.
- Coverage gap: tests cover empty/non-string form_id but not overlong values.
- Proposed fix (pending user go-ahead): length ≤ 64 check in the view + regression test.

### Verified clean
- theory.py: interval algebra, E→12 anchor edge case, octave normalisation —
  exhaustive probe of 41 forms × 12 keys, zero invariant violations.
- Generator output byte-identical to shipped practice/configs/fingerings/ (41 files);
  STRING_SHIFTS, box tiling, arpeggio windows, finger-form windows hand-verified.
- GET /api/round/ hammered 300×: all 200. POST /api/log/ malformed-input probes
  (invalid UTF-8, null, wrong types, empty body, form-encoded): all 400, never 500.
- ruff/mypy: boilerplate noise only.

### Observation (not a defect)
A transient failure of test_index_has_v2_ui_hooks mid-hunt was caused by the
concurrent frontend agent's in-flight edits; it updated index.html and
practice/tests/test_api.py (a Python test file, not just frontend) to a
consistent state and the suite is green.

---

## v3 (2026-07-14): parallel agent round — bugfix · E-root prune · security

Three worktree-isolated agents branched from checkpoint `46c8ffb`, merged A → C → B, zero conflicts. Suite 86/86 green on merged main; orchestrator verification passed.

- [x] **Agent A — Finding 1 fixed.** `POST /api/log/` now rejects `form_id` > 64 chars with 400; bound derived from `AttemptLog._meta.get_field("form_id").max_length` (practice/views.py). Regression tests: 65-char → 400, 64-char boundary → 201 (practice/tests/test_api.py).
- [x] **Agent B — shipped fingerings pruned to the 3 E-root major-scale forms** (`major_scale_{1st,2nd,4th}_finger_form.yaml`) for manual validation; the other 38 yamls deleted. All non-yaml functionality (scales.yaml, theory.py, generator, views, frontend) retained, viable but unused. Generator tests repointed to temp dirs (running `scripts/generate_fingerings.py` against the live dir would regenerate all 41 — warned in README); new test pins shipped files byte-identical to generator output; exhaustive 41-form × 12-key theory coverage preserved via temp-dir generation. README: "Adding a new scale form" section added.
- [x] **Agent C — SECRET_KEY moved to .env** (python-dotenv; `DJANGO_SECRET_KEY`/`DJANGO_DEBUG`/`DJANGO_ALLOWED_HOSTS`; fail-loud `ImproperlyConfigured` when DEBUG=false without a key). `.env` gitignored, `.env.example` tracked, README setup bullets. Full audit in **SECURITY_AUDIT.md** — headline items: old committed key is burned (in git history at `46c8ffb`; never reuse), prod hardening block (HSTS/secure cookies/SSL redirect) still TODO, `/api/log/` has no rate limiting, admin exposed unused. Report-only items intentionally not implemented this round.
- [x] **Agent C round 2 (user-triggered) — audit items implemented** (`security-hardening-round-2`, merged): `if not DEBUG:` HTTPS hardening block (SSL redirect, secure cookies, HSTS env-tunable via `DJANGO_SECURE_HSTS_SECONDS`); per-IP rate limit on `POST /api/log/` (`practice/ratelimit.py`, `DJANGO_API_RATE_LIMIT_PER_MINUTE` default 60, 429 + Retry-After, 6 new tests); admin removed (restore notes in config/urls.py); `requirements.lock`; `STATIC_ROOT`. DEBUG-default-true kept deliberately (fresh clones/tests). `check --deploy` down to W021 only (HSTS preload, intentional). Suite 92/92 green post-merge.

Orchestrator verification on merged main: 86/86 tests OK; fingerings dir = exactly 3 yamls + README; 10× `/api/round/` served only the 3 kept ids; overlong-form_id POST → 400; `git grep django-insecure` clean in tracked files; fresh local `.env` key generated (agent-reported key discarded as transcript-exposed).

---

## v4 (2026-07-14): TAB-as-source + real TAB rendering

The generated 4th-finger major-scale form was wrong vs convention (E/G strings;
two notes below the low root — these "start on the root" forms never play below
it). Convention can't be derived from interval math, so the architecture
inverted: **each fingering yaml is a hand-authored TAB in the fixed example key
A** (root = low E fret 5), and the neck diagram AND a real TAB rendering are
both derived from it. Theory demoted from generator to validator.

- [x] New yaml schema: `example_key: A` + `tab:` with `E A D G B e` labels
      replaces `anchor`-relative `offsets` (loader derives offsets at load
      time; resolve/transposition/API payload unchanged). Legacy `offsets`
      schema rejected with a migration hint.
- [x] New hard validation: frets ≥ 1; low-E root present; **nothing sounds
      below the low root** (absolute-pitch check — catches exactly the class
      of error the generator made); plus the retained span ≤ 6 / in-scale /
      full-interval-coverage checks.
- [x] Files renamed for root-string specificity (A-root variants planned):
      `major_scale_e_root_{1st,2nd,4th}_finger_form.yaml`, ids
      `major-scale-e-root-*-finger-form`. 4th = Fraser's verified TAB;
      1st/2nd drafted from his spec (3nps from root / position form) —
      **pending Fraser's verification** (he trimmed 2nd-form e-string to
      [4,5] during the build; 1st form still DRAFT).
- [x] Real TAB rendering in app.js (deferred item done): numbers on the
      six-line staff in play order, Descending = reversed run; roots orange;
      hidden until the answer reveal like the neck's fret labels.
- [x] `scripts/generate_fingerings.py` + `test_generator.py` DELETED (git
      history keeps them). test_theory reworked: exhaustive coverage = 3
      shipped forms × 12 keys + TAB round-trip invariant (key-A resolution
      reproduces the authored TAB verbatim) + Fraser's ground-truth fixture.
      Note: octave down-shift is now unreachable for valid forms (root-present
      ⇒ min offset ≤ 0).

## v5 (2026-07-14): A-string-root major scale forms + `root_low_a` anchor

Source: "A major scale, six different scale forms" PDF — the three
A-string forms (1st/2nd/4th finger, root = A string fret 12) join the three
shipped E-string forms. First second anchor strategy, built the way the v1
TODO anticipated.

- [x] `ANCHOR_ROOT_STRINGS = {"root_low_e": 6, "root_low_a": 5}` — anchor
      strategy is now a data map (strategy -> root string); `anchor_fret`
      generic over it (12-not-0 convention kept, so A-root forms in A sit at
      the 12th position); `root_fret_low_a` alongside `root_fret_low_e`.
- [x] Validation split: root-on-anchor-string (all forms) vs
      nothing-below-the-root (scale/arpeggio only — pentatonic CAGED boxes
      may play E-string notes below an A-string root, so they're exempt via
      one `CAGED_CATEGORIES` gate; no new config fields).
- [x] `display_label` now carries the anchor: "1st Finger Form (E-root)" /
      "(A-root)" — the exercise header was the only place the player sees
      the form and it couldn't tell same-finger variants apart.
- [x] 3 new configs `major_scale_a_root_{1st,2nd,4th}_finger_form.yaml`
      (hand-transcribed from the PDF, verified two ways: interval math +
      shape-shift of the E-root forms with the B-string bump). 16 forms
      total (6 scale + 10 arpeggio).
- [x] Tests: 136 (was 121) — `root_fret_low_a` all 12 keys + flats; literal
      PDF-TAB resolution for the 3 A-root forms incl. octave-shift cases
      (key B anchors 2 -> shifts to 14); A-root forms never touch low E;
      per-(scale, anchor) finger uniqueness + display_label uniqueness per
      scale; broken-config coverage for root-missing-from-A and
      below-A-string-root; pentatonic below-root carve-out (loads fine).
      `resolve_form` needed zero changes — offsets were already
      strategy-agnostic.

## Pentatonic CAGED boxes (2026-07-14, parallel background agent)

All 5 CAGED boxes for both pentatonic scales, hand-authored TABs in A,
labelled by shape ("E Shape" … "D Shape"):
`{major,minor}_pentatonic_{e,d,c,a,g}_shape.yaml`. 26 forms total
(6 scale + 10 arpeggio + 10 pentatonic).

- [x] Each box anchors on the string carrying its root, per the A-root
      round's design: E shape → `root_low_e`, D → `root_low_d`, C and A →
      `root_low_a`, G → `root_low_g`. The two new strategies are one
      `ANCHOR_ROOT_STRINGS` entry each — the only theory.py change; the
      validation split from the A-root round needed nothing further.
- [x] Boxes authored in position in A (minor: G 2-5, E 5-8, D 7-10,
      C 9-13, A 12-15; major: G 2-5, E 4-7, D 6-10, C 9-12, A 11-14) —
      all inside the display octave, so the TAB round-trip stays verbatim
      and no octave down-shift is ever needed.
- [x] Tests: 142 (was 136) — anchor_fret for D/G strings all 12 keys
      (D→12, G→12 edge cases); every pentatonic scale ships all 5 shapes;
      shipped boxes anchor on their root string; box-1 ground truth in A;
      wrap-around G-shape fixture in C. Randomisation test bumped
      100 → 400 draws (26 forms would flake ~40% at 100).
- [x] No view/JS changes — labels and round payloads already config-driven.

## Rename + title home link (2026-07-14)

- [x] App renamed "Guitar Scale Practice" → **ScaleRunner** everywhere but
      the repo name (page title, h1, JS/CSS/theory headers, docs).
- [x] The title h1 is now a home link: clicking it from any screen stops
      the timer, discards the session (no results), and shows the start
      menu. Pointer cursor + hover brighten signal the affordance.
      Cache-bust bumps: style.css v7, app.js v6.

## Deferred (unchanged)
- 7-string · Users/auth · Spaced repetition algorithm · Flat/sharp spelling · Config hot-reload
- Restore full 41-form config set post-validation (rerun `scripts/generate_fingerings.py`, revert test count changes from v3 prune)
- Rotate/burn the old committed secret key if repo ever goes public (in history at `46c8ffb`) · raise HSTS to 1 year + preload once HTTPS is stable
