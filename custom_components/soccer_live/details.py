"""Small provider-neutral helpers for on-demand fixture details."""

from __future__ import annotations

from copy import deepcopy

DETAIL_KEYS = (
    "key_events", "match_details", "lineup_home", "lineup_away",
    "home_statistics", "away_statistics", "momentum", "shotmap",
)


def has_match_details(match: dict | None) -> bool:
    """Whether a fixture already contains useful popup/detail information."""
    if not isinstance(match, dict):
        return False
    return match.get("detail_loaded") is True or any(
        match.get(key) for key in DETAIL_KEYS
    )


# Prefer a finished/live copy of a fixture over a scheduled one: after a match
# ends a stale "pre" duplicate can linger in the schedule lists (matches /
# upcoming_matches) alongside the real result in previous_matches / the archive.
_STATE_RANK = {"post": 3, "in": 2, "live": 2, "pre": 1}


def find_match(attributes: dict | None, match_id) -> dict | None:
    """Find one fixture in any normal Soccer Live published location.

    When several published copies share the event id, the most advanced one
    wins (finished/live over scheduled); copies of equal state keep discovery
    order, so the authoritative current/next view is preferred on a tie.
    """
    wanted = str(match_id or "")
    if not wanted:
        return None
    attrs = attributes or {}
    candidates = []
    for key in ("current_match", "next_match"):
        match = attrs.get(key)
        if isinstance(match, dict) and str(match.get("event_id")) == wanted:
            candidates.append(match)
    for key in ("matches", "previous_matches", "upcoming_matches", "match_archive"):
        for match in attrs.get(key) or []:
            if isinstance(match, dict) and str(match.get("event_id")) == wanted:
                candidates.append(match)
    if not candidates:
        return None
    return max(candidates, key=lambda m: _STATE_RANK.get(str(m.get("state") or "").lower(), 0))


def public_match_details(match: dict | None) -> dict | None:
    """Return a detached response safe for a service/WebSocket caller."""
    return deepcopy(match) if isinstance(match, dict) else None
