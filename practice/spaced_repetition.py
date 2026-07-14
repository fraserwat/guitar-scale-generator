"""Spaced-repetition round selection — STUB.

=============================================================================
TODO(spaced repetition): planned algorithm
-----------------------------------------------------------------------------
Weight upcoming rounds by past performance so the player drills weak spots:
  * Query AttemptLog for the player's history (per-user once auth exists —
    v1 has no accounts, so history is global).
  * Track per-form stats keyed by AttemptLog.form_id (plus key): give higher
    weight to fingering forms / keys with recent incorrect answers, decaying
    over time (e.g. SM-2-style ease factors or a simple exponentially-decayed
    error rate).
  * Ensure a minimum floor weight so every form still appears occasionally.
This module will replace the uniform selection currently used by the round
API view.
=============================================================================
"""


def next_round_weights(form_ids, attempt_history=None):
    """Return a selection weight for each fingering form id.

    STUB: returns uniform weights, which makes the round view's weighted
    choice equivalent to uniform random selection.

    Args:
        form_ids: sequence of candidate fingering form ids (strings).
        attempt_history: unused for now; will be a queryset of AttemptLog
            rows once the real algorithm lands.

    Returns:
        list[float]: one weight per form id (currently all 1.0).
    """
    return [1.0] * len(form_ids)
