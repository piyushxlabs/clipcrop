"""Pure deterministic state reducers for the ClipCrop state machine.

Strictly implements the 4 locked reducers defined in:
- docs/AGENT_ORCHESTRATION_BLUEPRINT.md Section 3
- rules/state-invariants-and-tool-preconditions.md
"""

from __future__ import annotations

from typing import Any, TypeVar

from src.exceptions import StateValidationError
from src.state.schema import StateSchema

T = TypeVar("T")

# Locked field-to-reducer mapping per AGENT_ORCHESTRATION_BLUEPRINT.md Section 3
FIELD_REDUCERS: dict[str, str] = {
    "session_id": "immutable_after_init",
    "source_video": "immutable_after_init",
    "config": "immutable_after_init",
    "transcript_segments": "append_only",
    "vad_segments": "append_only",
    "rendered_clips": "append_only",
    "crop_path_exports": "append_only",
    "skipped_segments": "append_only",
    "error_logs": "append_only",
    "candidate_segments": "last_write_wins",
    "tracking_results": "merge_by_key",
    "confidence_gate_results": "merge_by_key",
    "crop_paths": "merge_by_key",
}


def immutable_after_init(current_value: Any, new_value: Any, field_name: str = "field") -> Any:
    """Reducer: immutable_after_init.

    Allows initialization once (when current_value is None).
    Any subsequent write attempt raises StateValidationError.
    """
    if current_value is not None:
        raise StateValidationError(
            f"Field '{field_name}' is immutable after initialization and cannot be mutated."
        )
    return new_value


def append_only(current_list: list[T], new_items: list[T] | T) -> list[T]:
    """Reducer: append_only.

    Preserves all existing list items and appends new item(s).
    Guarantees earlier items are never deleted, dropped, or reordered.
    Returns a fresh list container to prevent external caller side-effects.
    """
    updated_list = list(current_list)
    if isinstance(new_items, list):
        updated_list.extend(new_items)
    else:
        updated_list.append(new_items)
    return updated_list


def merge_by_key(
    current_dict: dict[str, T],
    new_entries: dict[str, T] | tuple[str, T],
) -> dict[str, T]:
    """Reducer: merge_by_key.

    Merges entries keyed by segment_id without clobbering or overwriting
    other unrelated segment entries in the dictionary.
    Returns a fresh dictionary container.
    """
    updated_dict = dict(current_dict)
    if isinstance(new_entries, tuple) and len(new_entries) == 2:
        key, value = new_entries
        updated_dict[key] = value
    elif isinstance(new_entries, dict):
        updated_dict.update(new_entries)
    else:
        raise StateValidationError(
            f"Invalid input for merge_by_key: expected dict or (key, value) tuple, got {type(new_entries)}."
        )
    return updated_dict


def last_write_wins(current_value: T, new_value: T, max_candidates: int = 10) -> T:
    """Reducer: last_write_wins.

    Replaces the current value atomically with the new value.
    For candidate_segments lists, enforces the hard cap CLIPCROP_MAX_CANDIDATES.
    """
    if isinstance(new_value, list):
        if len(new_value) > max_candidates:
            raise StateValidationError(
                f"Candidate segment count ({len(new_value)}) exceeds maximum allowed ({max_candidates})."
            )
        return list(new_value)  # type: ignore[return-value]
    return new_value


def apply_state_update(
    state: StateSchema,
    field_name: str,
    value: Any,
    key: str | None = None,
) -> StateSchema:
    """Central state mutation dispatcher.

    Routes field updates strictly through the field's declared reducer,
    validates the mutation, and updates StateSchema without bypassing invariants.
    """
    if field_name not in FIELD_REDUCERS:
        raise StateValidationError(f"Field '{field_name}' is not a recognized StateSchema field.")

    reducer_name = FIELD_REDUCERS[field_name]
    current_val = getattr(state, field_name)

    if reducer_name == "immutable_after_init":
        reduced_val = immutable_after_init(current_val, value, field_name=field_name)

    elif reducer_name == "append_only":
        reduced_val = append_only(current_val, value)

    elif reducer_name == "merge_by_key":
        if key is not None:
            reduced_val = merge_by_key(current_val, (key, value))
        elif isinstance(value, dict):
            reduced_val = merge_by_key(current_val, value)
        elif isinstance(value, tuple) and len(value) == 2:
            reduced_val = merge_by_key(current_val, value)
        else:
            raise StateValidationError(
                f"Merge-by-key field '{field_name}' requires either a 'key' parameter, "
                "a dictionary, or a (key, value) tuple."
            )

    elif reducer_name == "last_write_wins":
        max_c = state.config.max_candidates if hasattr(state, "config") and state.config else 10
        reduced_val = last_write_wins(current_val, value, max_candidates=max_c)

    else:
        raise StateValidationError(f"Unknown reducer '{reducer_name}' mapped to field '{field_name}'.")

    state._update_from_reducer(field_name, reduced_val)
    return state


def verify_render_precondition(state: StateSchema, segment_id: str) -> None:
    """Verify precondition for smooth_crop_path and render_vertical_clip.

    Must ONLY execute if confidence_gate_results[segment_id].decision == 'render'.
    """
    gate_decision = state.confidence_gate_results.get(segment_id)
    if gate_decision is None:
        raise StateValidationError(
            f"Precondition failed: No confidence gate decision found for segment '{segment_id}'."
        )
    if gate_decision.decision != "render":
        raise StateValidationError(
            f"Precondition failed: Segment '{segment_id}' was gated as '{gate_decision.decision}' "
            f"(reason: {gate_decision.reason}) and cannot be rendered."
        )


def verify_export_precondition(state: StateSchema, segment_id: str) -> None:
    """Verify precondition for export_crop_path_data.

    Must ONLY execute after a successful render_vertical_clip record exists for that segment_id,
    guaranteeing paired deliverables.
    """
    verify_render_precondition(state, segment_id)
    matching_clips = [c for c in state.rendered_clips if c.segment_id == segment_id]
    if not matching_clips:
        raise StateValidationError(
            f"Precondition failed: No rendered clip found for segment '{segment_id}'. "
            "export_crop_path_data requires an existing rendered clip to guarantee paired deliverables."
        )
