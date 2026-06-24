"""Normalize external ESPN response data used by the config flow."""


def parse_competitions(data):
    """Return valid competition slug/name pairs from an ESPN response."""
    if not isinstance(data, dict):
        return {}

    competitions = {}
    for league in data.get("leagues") or []:
        if not isinstance(league, dict):
            continue
        slug = league.get("slug")
        name = league.get("name")
        if slug and name:
            competitions[slug] = name
    return competitions


def parse_teams(data):
    """Return valid team id/display-name pairs from an ESPN response."""
    if not isinstance(data, dict):
        return []

    sports = data.get("sports") or []
    sport = sports[0] if sports and isinstance(sports[0], dict) else {}
    teams = []
    for league in sport.get("leagues") or []:
        if not isinstance(league, dict):
            continue
        for entry in league.get("teams") or []:
            if not isinstance(entry, dict):
                continue
            team = entry.get("team")
            if not isinstance(team, dict):
                continue
            team_id = team.get("id")
            display_name = team.get("displayName")
            if team_id and display_name:
                teams.append({"id": team_id, "displayName": display_name})
    return teams
