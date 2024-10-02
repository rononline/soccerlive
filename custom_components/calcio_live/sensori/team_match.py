from .const import _LOGGER
from dateutil import parser

def team_match_data(data):
    try:
        team_data = data.get("team", {})
        team_name = team_data.get("displayName", "N/A")

        logos = team_data.get("logos", [])
        logo_default = logos[0].get("href", "N/A") if logos else "N/A"
        logo_dark = logos[1].get("href", "N/A") if len(logos) > 1 else "N/A"

        record_items = team_data.get("record", {}).get("items", [])
        overall_record = {}
        if record_items:
            overall_record = {stat['name']: stat.get('value', "N/A") for stat in record_items[0].get("stats", [])}

        next_event = team_data.get("nextEvent", [])[0] if team_data.get("nextEvent") else None

        if next_event:
            event_name = next_event.get("name", "N/A")
            event_date = _parse_date(next_event.get("date", "N/A"))
            venue = next_event.get("competitions", [])[0].get("venue", {}).get("fullName", "N/A")

            home_team_data = next_event.get("competitions", [])[0].get("competitors", [])[0].get("team", {})
            home_team_name = home_team_data.get("displayName", "N/A")
            home_team_logo = home_team_data.get("logos", [])[0].get("href", "N/A") if home_team_data.get("logos") else "N/A"

            away_team_data = next_event.get("competitions", [])[0].get("competitors", [])[1].get("team", {})
            away_team_name = away_team_data.get("displayName", "N/A")
            away_team_logo = away_team_data.get("logos", [])[0].get("href", "N/A") if away_team_data.get("logos") else "N/A"

            odds = next_event.get("competitions", [])[0].get("odds", [])
            home_odds, away_odds = {}, {}
            if odds:
                home_odds_info = odds[0].get("homeTeamOdds", {})
                away_odds_info = odds[0].get("awayTeamOdds", {})

                home_odds = {
                    "favorite": home_odds_info.get("favorite", "N/A"),
                    "moneyLine_open": home_odds_info.get("open", {}).get("moneyLine", {}).get("value", "N/A"),
                    "moneyLine_current": home_odds_info.get("current", {}).get("moneyLine", {}).get("value", "N/A"),
                    "spread_open": home_odds_info.get("open", {}).get("spread", {}).get("displayValue", "N/A"),
                    "spread_current": home_odds_info.get("current", {}).get("spread", {}).get("displayValue", "N/A")
                }

                away_odds = {
                    "favorite": away_odds_info.get("favorite", "N/A"),
                    "moneyLine_open": away_odds_info.get("open", {}).get("moneyLine", {}).get("value", "N/A"),
                    "moneyLine_current": away_odds_info.get("current", {}).get("moneyLine", {}).get("value", "N/A"),
                    "spread_open": away_odds_info.get("open", {}).get("spread", {}).get("displayValue", "N/A"),
                    "spread_current": away_odds_info.get("current", {}).get("spread", {}).get("displayValue", "N/A")
                }

            return {
                "team_name": team_name,
                "logo_default": logo_default,
                "logo_dark": logo_dark,
                "next_event_name": event_name,
                "next_event_date": event_date,
                "venue": venue,
                "home_team": home_team_name,
                "home_team_logo": home_team_logo,
                "away_team": away_team_name,
                "away_team_logo": away_team_logo,
                "home_odds": home_odds,
                "away_odds": away_odds,
                "overall_record": overall_record
            }

        else:
            return {
                "team_name": team_name,
                "logo_default": logo_default,
                "logo_dark": logo_dark,
                "overall_record": overall_record
            }
    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati del team match: {e}")
        return {}

def _parse_date(date_str):
    """Funzione per convertire la data da stringa ISO a formato leggibile."""
    try:
        parsed_date = parser.isoparse(date_str)
        return parsed_date.strftime("%d-%m-%Y %H:%M")
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return "N/A"
