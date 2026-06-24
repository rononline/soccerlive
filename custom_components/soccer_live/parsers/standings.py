import logging
_LOGGER = logging.getLogger(__name__)
from dateutil import parser
from datetime import datetime

def standings_data(data):
    try:
        standings_list = []

        for child in data.get("children", []):
            standings_data = child.get("standings", {}).get("entries", [])
            standings = []

            for index, entry in enumerate(standings_data, start=1):
                team = entry.get("team", {})
                stats = {stat['name']: stat['displayValue'] for stat in entry.get("stats", [])}

                note = entry.get("note") or {}
                rank = note.get("rank", index)
                zone_color = note.get("color", "")        # ESPN hex color, e.g. "007AC0"
                zone_label = note.get("description", "")  # e.g. "UEFA Champions League"
                zone_abbrev = note.get("abbreviation", "") # e.g. "UCL"

                team_data = {
                    "rank": rank,
                    "team_id": team.get("id"),
                    "team_name": team.get("displayName"),
                    "team_logo": (team.get("logos") or [{}])[0].get("href", "N/A"),
                    "points": stats.get("points", "N/A"),
                    "games_played": stats.get("gamesPlayed", "N/A"),
                    "wins": stats.get("wins", "N/A"),
                    "draws": stats.get("ties", "N/A"),
                    "losses": stats.get("losses", "N/A"),
                    "goals_for": stats.get("pointsFor", "N/A"),
                    "goals_against": stats.get("pointsAgainst", "N/A"),
                    "goal_difference": stats.get("pointDifferential", "N/A"),
                    "zone_color": f"#{zone_color}" if zone_color else "",
                    "zone_label": zone_label,
                    "zone_abbrev": zone_abbrev,
                }
                standings.append(team_data)

            full_table_link = child.get("standings", {}).get("links", [])[0].get("href", "N/A") if child.get("standings", {}).get("links") else "N/A"

            standings_list.append({
                "name": child.get("name", "Unknown"),
                "standings": standings,
                "full_table_link": full_table_link
            })

        # ESPN exposes season as either a "seasons" array or a singular "season" object
        seasons_data = data.get("seasons") or []
        if not seasons_data:
            singular = data.get("season")
            if isinstance(singular, dict):
                seasons_data = [singular]
        current_year = datetime.now().year
        current_season = (
            next((s for s in seasons_data if s.get("year") == current_year), None)
            or next((s for s in seasons_data if s.get("year") == current_year - 1), None)
            or (seasons_data[-1] if seasons_data else None)
        )

        season_display_name = current_season.get("displayName", "N/A") if current_season else "N/A"
        season_start = _parse_date(current_season.get("startDate", "N/A")) if current_season else None
        season_end = _parse_date(current_season.get("endDate", "N/A")) if current_season else None

        # ESPN puts name/abbreviation at the top level for some endpoints and under
        # leagues[0] for others; try both.
        _leagues = data.get("leagues") or []
        _first_league = _leagues[0] if _leagues else {}
        league_name = data.get("name") or _first_league.get("name", "N/A") or "N/A"
        league_abbreviation = data.get("abbreviation") or _first_league.get("abbreviation", "N/A") or "N/A"
        # Try multiple locations ESPN may put the competition logo
        logos = (data.get("logos") or
                 (data.get("leagues") or [{}])[0].get("logos") or
                 (data.get("sport") or {}).get("logos") or [])
        league_logo = logos[0].get("href", "") if logos else ""

        return {
            "season": season_display_name,
            "season_start": season_start,
            "season_end": season_end,
            "league_name": league_name,
            "league_abbreviation": league_abbreviation,
            "league_logo": league_logo,
            "standings_groups": standings_list
        }
    except Exception as e:
        _LOGGER.error(f"Error processing standings data: {e}")
        return {}



def _parse_date(date_str):
    try:
        parsed_date = parser.isoparse(date_str)
        return parsed_date.strftime("%d-%m-%Y")
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Error parsing date {date_str}: {e}")
        return None