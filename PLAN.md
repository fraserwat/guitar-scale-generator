# Guitar Scale Practice App — v2 Build Plan

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done · `[!]` blocked/issue.
(v1 shipped 2026-07-13: config-driven pentatonic forms, exhaustive 50-test suite, verified. This plan replaces the v1 doc.)

**Agents:** `plan-1` (Plan agent) stalled twice on the offset-table derivation and was abandoned; Phase 0 design completed by the orchestrator directly. Phases 1–4 delegated to build agent `build-2`; Phase 5 verification by orchestrator.

---

## BugFinder report (2026-07-14, automated bug-hunt output)

Whole-repo sweep: theory.py, views.py, generator script, tests, settings, YAML configs.
Test suite: 84/84 green at end of hunt.

### Finding 1 (only finding, low severity) — CONFIRMED, unfixed
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

## Deferred (unchanged)
- 7-string · Real TAB rendering · Users/auth · Spaced repetition algorithm · Flat/sharp spelling · Config hot-reload
