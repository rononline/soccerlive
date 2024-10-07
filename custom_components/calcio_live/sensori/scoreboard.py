from .const import _LOGGER
from dateutil import parser
from pytz import timezone, utc

def process_league_data(data, hass=None):
    """
    Processa i dati della lega, estraendo abbreviation, startDate, endDate, e href del logo.
    """
    try:
        leagues_data = data.get("leagues", [])
        league_info = []

        for league in leagues_data:
            league_abbreviation = league.get("abbreviation", "N/A")
            league_start_date = league.get("season", {}).get("startDate", "N/A")
            league_end_date = league.get("season", {}).get("endDate", "N/A")
            
            logos = league.get("logos", [])
            logo_href = logos[0].get("href", "N/A") if logos else "N/A"
            
            league_info.append({
                "abbreviation": league_abbreviation,
                "startDate": _parse_date(hass, league_start_date, show_time=False),
                "endDate": _parse_date(hass, league_end_date, show_time=False),
                "logo_href": logo_href
            })

        return league_info

    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati della lega: {e}")
        return []


# Includi la chiamata alla nuova funzione `process_league_data` nella funzione principale
def process_match_data(data, hass, team_name=None, next_match_only=False):
    """
    Processa i dati delle partite.
    - Se `team_name` è fornito, filtra solo le partite della squadra specifica.
    - Se `next_match_only` è True, restituisce solo la prossima partita dopo l'ultima conclusa.
    """
    try:
        matches_data = data.get("events", [])
        league_info = process_league_data(data, hass)  # Passa l'oggetto hass qui
        matches = []
        team_logo = None  # Valore predefinito per il logo della squadra

        if team_name:
            _LOGGER.debug(f"Filtraggio delle partite per la squadra: {team_name}")
        else:
            _LOGGER.warning("Nessun nome squadra fornito, elaborazione di tutte le partite.")

        for match in matches_data:
            match_name = match.get("name", "").lower()

            # Se il nome della squadra è fornito, filtra solo le partite in cui è coinvolta
            if team_name and team_name.lower() not in match_name:
                continue

            match_date = _parse_date(hass, match.get("date", "N/A"))

            competitions = match.get("competitions", [])
            if not competitions or len(competitions[0].get("competitors", [])) < 2:
                _LOGGER.warning(f"Partita senza dati completi: {match}")
                continue

            competitors = competitions[0].get("competitors", [])

            # Estrai i dati della squadra di casa
            home_team_data = competitors[0].get("team", {})
            home_team = home_team_data.get("displayName", "N/A")
            home_logo = home_team_data.get("logo", "N/A")
            home_form = competitors[0].get("form", "N/A")
            home_score = competitors[0].get("score", "N/A")
            home_statistics = _get_statistics(competitors[0])

            # Estrai i dati della squadra ospite
            away_team_data = competitors[1].get("team", {})
            away_team = away_team_data.get("displayName", "N/A")
            away_logo = away_team_data.get("logo", "N/A")
            away_form = competitors[1].get("form", "N/A")
            away_score = competitors[1].get("score", "N/A")
            away_statistics = _get_statistics(competitors[1])

            # Dettagli della partita
            match_status = match.get("status", {}).get("type", {}).get("description", "N/A")
            clock = match.get("status", {}).get("displayClock", "N/A")
            period = match.get("status", {}).get("period", "N/A")
            venue = competitions[0].get("venue", {}).get("fullName", "N/A")
            match_details = _get_details(competitions[0].get("details", []))

            # Se è stata fornita una squadra, prendi il logo della squadra specifica
            if team_name and (team_name.lower() in home_team.lower() or team_name.lower() in away_team.lower()):
                team_logo = home_logo if team_name.lower() in home_team.lower() else away_logo

            match_data = {
                "date": match_date,
                "home_team": home_team,
                "home_logo": home_logo,
                "home_form": home_form,
                "home_score": home_score,
                "home_statistics": home_statistics,
                "away_team": away_team,
                "away_logo": away_logo,
                "away_form": away_form,
                "away_score": away_score,
                "away_statistics": away_statistics,
                "status": match_status,
                "clock": clock,
                "period": period,
                "venue": venue,
                "match_details": match_details,
            }
            matches.append(match_data)

        # Se l'opzione `next_match_only` è attiva, restituisce solo la prossima partita
        if next_match_only:
            upcoming_matches = [m for m in matches if m.get("status") == "Scheduled"]
            if upcoming_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Tutte le partite",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [upcoming_matches[0]]  # Restituisce solo la prossima partita
                }

        return {
            "league_info": league_info,
            "team_name": team_name if team_name else "Tutte le partite",
            "team_logo": team_logo if team_logo else "N/A",
            "matches": matches
        }

    except Exception as e:
        _LOGGER.error(f"Errore nel processare i dati delle partite: {e}")
        return {}


def _get_statistics(competitor):
    """Estrai le statistiche della squadra."""
    statistics = {}
    stats = competitor.get("statistics", [])
    for stat in stats:
        stat_name = stat.get("name", "Unknown")
        stat_value = stat.get("displayValue", "N/A")
        statistics[stat_name] = stat_value
    return statistics

def _get_details(details):
    """Estrai i dettagli della partita (eventi come gol, cartellini, etc.)."""
    events = []
    for detail in details:
        event_type = detail.get("type", {}).get("text", "Unknown")
        clock = detail.get("clock", {}).get("displayValue", "N/A")
        athletes = [athlete.get("displayName", "Unknown") for athlete in detail.get("athletesInvolved", [])]
        athletes_str = ", ".join(athletes) if athletes else "N/A"
        events.append(f"{event_type} - {clock}: {athletes_str}")
    return events


from dateutil import parser
from pytz import timezone, utc

def _parse_date(hass, date_str, show_time=True):
    """
    Converti la data da formato ISO a un formato leggibile, utilizzando il fuso orario di Home Assistant.
    - hass: Oggetto di Home Assistant che contiene la configurazione, incluso il fuso orario.
    - show_time: Se True, mostra anche l'orario. Se False, mostra solo la data.
    """
    try:
        # Ottieni il fuso orario configurato in Home Assistant
        user_timezone = hass.config.time_zone

        # Parsing della data in UTC
        parsed_date = parser.isoparse(date_str).replace(tzinfo=utc)

        # Converti la data al fuso orario configurato
        local_tz = timezone(user_timezone)
        local_date = parsed_date.astimezone(local_tz)

        if show_time:
            return local_date.strftime("%d/%m/%Y %H:%M")  # Mostra data e orario
        else:
            return local_date.strftime("%d/%m/%Y")  # Solo data
    except (ValueError, TypeError) as e:
        _LOGGER.error(f"Errore nel parsing della data {date_str}: {e}")
        return "N/A"



