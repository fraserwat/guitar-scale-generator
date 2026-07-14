import json
import random

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import spaced_repetition, theory
from .models import AttemptLog


def index(request):
    """Single-page practice game."""
    return render(request, "practice/index.html")


@require_GET
def api_round(request):
    """Return a randomised practice round as JSON.

    A round = (fingering form, key, direction). The form is chosen via the
    spaced-repetition weights; key and direction are uniform random.
    """
    fingerings = theory.load_fingerings()
    scales = theory.load_scales()

    form_ids = list(fingerings)
    # TODO(spaced repetition): next_round_weights() is a stub returning
    # uniform weights, so this is currently plain uniform random selection.
    # Later it will bias towards forms/keys the player keeps getting wrong.
    weights = spaced_repetition.next_round_weights(form_ids)
    form_id = random.choices(form_ids, weights=weights, k=1)[0]
    key = random.choice(theory.KEYS)
    # Accidental (black-key) roots: 50% chance to present the flat enharmonic
    # spelling instead (e.g. Gb rather than F#). Natural keys are unchanged —
    # random.random() isn't even drawn for them.
    if key in theory.SHARP_TO_FLAT and random.random() < 0.5:
        key = theory.SHARP_TO_FLAT[key]
    direction = random.choice(theory.DIRECTIONS)

    form = fingerings[form_id]
    window_start, notes = theory.resolve_form(form_id, key)
    return JsonResponse({
        "scale": scales[form["scale"]]["name"],
        "key": key,
        "direction": direction,
        "form_id": form_id,
        "form_name": form["name"],
        "category": form["category"],
        "display_label": form["display_label"],
        "caged_shape": form["caged_shape"],          # str, or None for
                                                     # scale/arpeggio forms
        "starting_finger": form["starting_finger"],  # int, or None for CAGED
        "window_start": window_start,
        "notes": notes,
    })


@require_POST
def api_log(request):
    """Log the result of one round — STUB endpoint.

    TODO(spaced repetition): these rows (keyed by form_id) will feed the
    algorithm in practice/spaced_repetition.py.
    TODO(auth): attach the logged-in user once accounts exist.
    """
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body."}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON body must be an object."}, status=400)

    valid_forms = theory.load_fingerings()
    valid_scales = theory.scale_names()
    errors = {}
    form_id = payload.get("form_id")
    scale = payload.get("scale")
    key = payload.get("key")
    direction = payload.get("direction")
    correct = payload.get("correct")

    if not isinstance(form_id, str) or form_id not in valid_forms:
        errors["form_id"] = f"Required; must be one of {list(valid_forms)}."
    if not isinstance(scale, str) or scale not in valid_scales:
        errors["scale"] = f"Required; must be one of {valid_scales}."
    if not isinstance(key, str) or key not in theory.VALID_KEYS:
        errors["key"] = f"Required; must be one of {theory.VALID_KEYS}."
    if not isinstance(direction, str) or direction not in theory.DIRECTIONS:
        errors["direction"] = f"Required; must be one of {theory.DIRECTIONS}."
    if not isinstance(correct, bool):
        errors["correct"] = "Required; must be a JSON boolean."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    log = AttemptLog.objects.create(
        form_id=form_id, scale=scale, key=key, direction=direction, correct=correct
    )
    return JsonResponse({"status": "ok", "id": log.id}, status=201)
