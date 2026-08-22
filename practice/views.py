import json
import random

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import theory
from .models import AttemptLog


CHORD_MENU_GROUP_LABELS = {"core_diatonic": "Core Diatonic", "altered": "Altered"}


def _exercise_groups():
    """Group configured scales for the start-menu exercise picker.

    "Scales" and "Arpeggios" are flat {label, items} groups (Arpeggios
    strips the redundant " Arpeggio" suffix), one checkbox per scale.
    "Chord Inv." instead collapses down to one checkbox per menu_group
    ("Core Diatonic", "Altered") — its value is every currently-playable
    scale id in that group, comma-joined, so checking it plays all of
    them (today just Major 7 Root Position under Core Diatonic); as more
    chord types/inversions ship, that one checkbox picks them all up
    automatically. Checkbox values are what /api/round/?scales= accepts
    (a bare scale id or several, comma-joined — both parse the same way);
    only scales with a loaded fingering form are offered, and a menu_group
    with none yet (Altered, until a diminished7 form ships) is omitted —
    a checkbox never promises a round it can't serve.
    """
    playable = {form["scale"] for form in theory.load_fingerings().values()}
    groups = [{"label": "Scales", "items": []},
              {"label": "Arpeggios", "items": []},
              {"label": "Chord Inv.", "items": []}]
    chord_group_ids = {group: [] for group in theory.MENU_GROUPS}
    for scale_id, spec in theory.load_scales().items():
        if scale_id not in playable:
            continue
        if spec["category"] == "arpeggio":
            groups[1]["items"].append(
                {"id": scale_id, "name": spec["name"].removesuffix(" Arpeggio")})
        elif spec["category"] == "chord":
            chord_group_ids[spec["menu_group"]].append(scale_id)
        else:
            groups[0]["items"].append({"id": scale_id, "name": spec["name"]})
    for menu_group in theory.MENU_GROUPS:
        ids = chord_group_ids[menu_group]
        if ids:
            groups[2]["items"].append({"id": ",".join(ids),
                                       "name": CHORD_MENU_GROUP_LABELS[menu_group]})
    return groups


def index(request):
    """Single-page practice game."""
    return render(request, "practice/index.html",
                  {"exercise_groups": _exercise_groups()})


@require_GET
def api_round(request):
    """Return a randomised practice round as JSON.

    A round = (fingering form, key, direction), each drawn uniformly at
    random (the form pool optionally narrowed by ?scales=).
    """
    fingerings = theory.load_fingerings()
    scales = theory.load_scales()

    form_ids = list(fingerings)
    # Optional exercise filter: ?scales=major_pentatonic,minor7_arpeggio
    # narrows the pool to forms of those scale ids; absent means all forms.
    # Empty tokens are dropped (a trailing comma is harmless); an
    # effectively empty, unknown-id, or zero-form filter is a 400 — never
    # a 500. (A valid id can have zero loaded forms — major/minor arpeggio
    # ship no fingerings — which is also why _exercise_groups skips them.)
    scales_param = request.GET.get("scales")
    if scales_param is not None:
        wanted = {s for s in scales_param.split(",") if s}
        if not wanted:
            return JsonResponse({"errors": {
                "scales": "Must be a non-empty comma-separated list of "
                          f"scale ids (known: {list(scales)}).",
            }}, status=400)
        unknown = sorted(wanted - set(scales))
        if unknown:
            return JsonResponse({"errors": {
                "scales": f"Unknown scale id(s): {unknown} "
                          f"(known: {list(scales)}).",
            }}, status=400)
        form_ids = [f for f in form_ids if fingerings[f]["scale"] in wanted]
        if not form_ids:
            return JsonResponse({"errors": {
                "scales": "No playable forms for scale id(s): "
                          f"{sorted(wanted)}.",
            }}, status=400)
    form_id = random.choice(form_ids)
    key = random.choice(theory.KEYS)
    # Accidental (black-key) roots: 50% chance to present the flat enharmonic
    # spelling instead (e.g. Gb rather than F#). Natural keys are unchanged —
    # random.random() isn't even drawn for them.
    if key in theory.SHARP_TO_FLAT and random.random() < 0.5:
        key = theory.SHARP_TO_FLAT[key]

    form = fingerings[form_id]
    # Chord-inversion rounds reveal all notes at once — there's no
    # ascending/descending run to direct, so no direction is drawn.
    direction = None if form["category"] == "chord" else random.choice(theory.DIRECTIONS)
    window_start, notes = theory.resolve_form(form_id, key)
    return JsonResponse({
        "scale": scales[form["scale"]]["name"],
        "key": key,
        "direction": direction,
        "form_id": form_id,
        "form_name": form["name"],
        "category": form["category"],
        "display_label": form["display_label"],
        # caged_shape and starting_finger are XOR-populated by category:
        # pentatonic forms carry a shape, scale/arpeggio forms a finger.
        "caged_shape": form["caged_shape"],
        "starting_finger": form["starting_finger"],
        "window_start": window_start,
        "notes": notes,
    })


@require_POST
def api_log(request):
    """Log the result of one round."""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"errors": {"body": "Invalid JSON body."}},
                            status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"errors": {"body": "JSON body must be an object."}},
                            status=400)

    valid_forms = theory.load_fingerings()
    valid_scales = theory.scale_names()
    errors = {}
    form_id = payload.get("form_id")
    scale = payload.get("scale")
    key = payload.get("key")
    direction = payload.get("direction")
    correct = payload.get("correct")
    is_retry = payload.get("is_retry", False)

    if not isinstance(form_id, str) or form_id not in valid_forms:
        errors["form_id"] = f"Required; must be one of {list(valid_forms)}."
        category = None
    else:
        category = valid_forms[form_id]["category"]
    if not isinstance(scale, str) or scale not in valid_scales:
        errors["scale"] = f"Required; must be one of {valid_scales}."
    if not isinstance(key, str) or key not in theory.VALID_KEYS:
        errors["key"] = f"Required; must be one of {theory.VALID_KEYS}."
    # Chord-inversion rounds carry no direction (see api_round); every other
    # category still requires one of theory.DIRECTIONS.
    if category == "chord":
        if direction is not None:
            errors["direction"] = "Must be null for chord-inversion rounds (no ascending/descending)."
    elif not isinstance(direction, str) or direction not in theory.DIRECTIONS:
        errors["direction"] = f"Required; must be one of {theory.DIRECTIONS}."
    if not isinstance(correct, bool):
        errors["correct"] = "Required; must be a JSON boolean."
    if not isinstance(is_retry, bool):
        errors["is_retry"] = "Optional; must be a JSON boolean."

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    log = AttemptLog.objects.create(
        form_id=form_id, scale=scale, key=key, direction=direction,
        correct=correct, is_retry=is_retry,
    )
    return JsonResponse({"status": "ok", "id": log.id}, status=201)
