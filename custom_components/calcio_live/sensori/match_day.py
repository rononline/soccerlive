from .const import _LOGGER
from dateutil import parser
from datetime import timedelta

def match_day_data(data):
    try:
        matches_data = data.get("events", [])
        matches = []

        for match in matches_data:
            match_date = _parse_date(match.get("date", "N/A"))
            
            competitions = match.get("competitions", [])

            if not competitions or len(competitions[0].get("competitors", [])) < 2:
                _LOGGER.warning(f"Partita senza dati completi: {match}")
                continue

            competitors = competitions[0].get("competitors", [])

            home_team_data = competitors[0].get("team", {})
            home_team = home_team_data.get("displayName", "N/A")
            home_logo = home_team_data.get("logo", "N/A")
            home_form = competitors[0].get("form", "N/A")
            home_score = competitors[0].get("score", "N/A")
            home_records = competitors[0].get("records", [])[0].get("summary", "N/A") if competitors[0].get("records") else "N/A"
            home_statistics = _get_statistics(competitors[0])

            away_team_data = competitors[1].get("team", {})
            away_team = away_team_data.get("displayName", "N/A")
            away_logo = away_team_data.get("logo", "N/A")
            away_form = competitors[1].get("form", "N/A")
            away_score = competitors[1].get("score", "N/A")
            away_records = competitors[1].get("records", [])[0].get("summary", "N/A") if competitors[1].get("records") else "N/A"
            away_statistics = _get_statistics(competitors[1])

            # Dettagli del match
            match_status = match.get("status", {}).get("type", {}).get("description", "N/A")
            clock = match.get("status", {}).get("displayClock", "N/A")
            period = match.get("status", {}).get("period", "N/A")
            completed = match.get("status", {}).get("type", {}).get("completed", False)
            venue = competitions[0].get("venue", {}).get("fullName", "N/A")
            
            match_details = _get_details(competitions[0].get("details", []))

            # Estrazione delle odds per la partita
            odds_info = match.get("odds", [])
            home_odds, away_odds, draw_odds, over_under = _get_odds(odds_info)

            match_data = {
                "date": match_date,
                "home_team": home_team,
                "home_logo": home_logo,
                "home_form": home_form,
                "home_score": home_score,
                "home_records": home_records,
                "home_statistics": home_statistics,
                "away_team": away_team,
                "away_logo": away_logo,
                "away_form": away_form,
                "away_score": away_score,
                "away_records": away_records,
                "away_statistics": away_statistics,
                "status": match_status,
                "clock": clock,
                "period": period,
                "completed": completed,
                "venue": venue,
                "home_odds": home_odds,
                "away_odds": away_odds,
                "draw_odds": draw_odds,
                "over_under": over_under,
                "match_details": match_details,
            }
            matches.append(match_data)

        return {
            "matches": matches,
        }

    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati delle partite: {e}")
        return {}

def _get_statistics(competitor):
    statistics = {}
    stats = competitor.get("statistics", [])
    for stat in stats:
        stat_name = stat.get("name", "Unknown")
        stat_value = stat.get("displayValue", "N/A")
        statistics[stat_name] = stat_value
    return statistics

def _get_details(details):
    events = []
    for detail in details:
        event_type = detail.get("type", {}).get("text", "Unknown")
        clock = detail.get("clock", {}).get("displayValue", "N/A")
        athletes = [athlete.get("displayName", "Unknown") for athlete in detail.get("athletesInvolved", [])]
        athletes_str = ", ".join(athletes) if athletes else "N/A"
        events.append(f"{event_type} - {clock}: {athletes_str}")
    return events

def _get_odds(odds_info):
    home_odds = "N/A"
    away_odds = "N/A"
    draw_odds = "N/A"
    over_under = "N/A"

    for odd in odds_info:
        provider = odd.get("provider", {}).get("name", "N/A")
        if provider == "Bet 365":
            home_odds = odd.get("homeTeamOdds", {}).get("summary", "N/A")
            away_odds = odd.get("awayTeamOdds", {}).get("summary", "N/A")
            draw_odds = odd.get("drawOdds", {}).get("summary", "N/A")
            over_under = odd.get("total", {}).get("displayName", "Total") + ": " + odd.get("total", {}).get("over", {}).get("line", "N/A")

    return home_odds, away_odds, draw_odds, over_under


def _parse_date(date_str):
    try:
        parsed_date = parser.isoparse(date_str)
        # Aggiungi 2 ore all'orario
        parsed_date = parsed_date + timedelta(hours=2)
        return parsed_date.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return "N/A"
