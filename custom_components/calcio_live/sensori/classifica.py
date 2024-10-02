from .const import _LOGGER

from dateutil import parser
from datetime import datetime, timedelta

def classifica_data(data):
    try:
        standings_data = data.get("children", [])[0].get("standings", {}).get("entries", [])
        standings = []

        for index, entry in enumerate(standings_data, start=1):
            team = entry.get("team", {})
            stats = {stat['name']: stat['displayValue'] for stat in entry.get("stats", [])}

            rank = entry.get("note", {}).get("rank", index)

            team_data = {
                "rank": rank,
                "team_id": team.get("id"),
                "team_name": team.get("displayName"),
                "team_logo": team.get("logos", [])[0].get("href"),
                "points": stats.get("points", "N/A"),
                "games_played": stats.get("gamesPlayed", "N/A"),
                "wins": stats.get("wins", "N/A"),
                "draws": stats.get("ties", "N/A"),
                "losses": stats.get("losses", "N/A"),
                "goals_for": stats.get("pointsFor", "N/A"),
                "goals_against": stats.get("pointsAgainst", "N/A"),
                "goal_difference": stats.get("pointDifferential", "N/A")
            }
            standings.append(team_data)

        seasons_data = data.get("seasons", [])
        current_season = None
        for season in seasons_data:
            if season.get("year") == 2024:
                current_season = season
                break

        season_display_name = current_season.get("displayName", "N/A") if current_season else "N/A"
        season_start_raw = current_season.get("startDate", "N/A")
        season_end_raw = current_season.get("endDate", "N/A")

        season_start = _parse_date(season_start_raw)
        season_end = _parse_date(season_end_raw)

        return {
            "standings": standings,
            "season": season_display_name,
            "season_start": season_start,
            "season_end": season_end,
            "full_table_link": data.get("children", [])[0].get("standings", {}).get("links", [])[0].get("href", "N/A")
        }
    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati della classifica: {e}")
        return {}


def _parse_date(date_str):
    """Funzione per convertire la data da stringa ISO a formato leggibile."""
    try:
        parsed_date = parser.isoparse(date_str)
        return parsed_date.strftime("%d-%m-%Y")
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return None