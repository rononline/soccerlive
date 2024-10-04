from .const import _LOGGER
from dateutil import parser

def team_matches_data(data):
    try:
        team_data = data.get("team", {})
        team_name = team_data.get("displayName", "N/A")
        team_logo = team_data.get("logo", [{}])[0].get("href", "N/A")
    
        events = data.get("events", [])
        matches = []

        for event in events:
            match_data = _extract_match_data(event)
            matches.append(match_data)

        return {
            "team_name": team_name,
            "team_logo": team_logo,
            "matches": matches
        }

    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati delle partite: {e}")
        return {}

def _extract_match_data(event):
    try:
        event_name = event.get("name", "N/A")
        event_date = _parse_date(event.get("date", "N/A"))
        venue = event.get("competitions", [])[0].get("venue", {}).get("fullName", "N/A")

        home_team_data = event.get("competitions", [])[0].get("competitors", [])[0].get("team", {})
        home_team_name = home_team_data.get("displayName", "N/A")
        home_team_logo = home_team_data.get("logos", [])[0].get("href", "N/A") if home_team_data.get("logos") else "N/A"
        home_team_score = event.get("competitions", [])[0].get("competitors", [])[0].get("score", {}).get("displayValue", "N/A")

        away_team_data = event.get("competitions", [])[0].get("competitors", [])[1].get("team", {})
        away_team_name = away_team_data.get("displayName", "N/A")
        away_team_logo = away_team_data.get("logos", [])[0].get("href", "N/A") if away_team_data.get("logos") else "N/A"
        away_team_score = event.get("competitions", [])[0].get("competitors", [])[1].get("score", {}).get("displayValue", "N/A")

        # Estrazione delle odds (se presenti)
#        odds = event.get("competitions", [])[0].get("odds", [])
#        home_odds, away_odds = {}, {}
#        if odds:
#            home_odds_info = odds[0].get("homeTeamOdds", {})
#            away_odds_info = odds[0].get("awayTeamOdds", {})

#            home_odds = {
#                "favorite": home_odds_info.get("favorite", "N/A"),
#                "moneyLine_open": home_odds_info.get("open", {}).get("moneyLine", {}).get("value", "N/A"),
#                "moneyLine_current": home_odds_info.get("current", {}).get("moneyLine", {}).get("value", "N/A"),
#                "spread_open": home_odds_info.get("open", {}).get("spread", {}).get("displayValue", "N/A"),
#                "spread_current": home_odds_info.get("current", {}).get("spread", {}).get("displayValue", "N/A")
#            }

#            away_odds = {
#                "favorite": away_odds_info.get("favorite", "N/A"),
#                "moneyLine_open": away_odds_info.get("open", {}).get("moneyLine", {}).get("value", "N/A"),
#                "moneyLine_current": away_odds_info.get("current", {}).get("moneyLine", {}).get("value", "N/A"),
#                "spread_open": away_odds_info.get("open", {}).get("spread", {}).get("displayValue", "N/A"),
#                "spread_current": away_odds_info.get("current", {}).get("spread", {}).get("displayValue", "N/A")
#            }

        match_data = {
            "event_name": event_name,
            "event_date": event_date,
            "venue": venue,
            "home_team": home_team_name,
            "home_team_logo": home_team_logo,
            "home_team_score": home_team_score,
            "away_team": away_team_name,
            "away_team_logo": away_team_logo,
            "away_team_score": away_team_score
#            "home_odds": home_odds,
#            "away_odds": away_odds
        }
    
        return match_data

    except Exception as e:
        _LOGGER.error(f"Errore nell'estrazione dei dati della partita: {e}")
        return {}

def _parse_date(date_str):
    """Funzione per convertire la data da stringa ISO a formato leggibile."""
    try:
        parsed_date = parser.isoparse(date_str)
        return parsed_date.strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return "N/A"