import logging
_LOGGER = logging.getLogger(__name__)
from dateutil import parser
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta, timezone

def process_league_data(data, hass=None):
    try:
        leagues_data = data.get("leagues", [])
        league_info = []

        for league in leagues_data:
            league_name = league.get("name", "")
            league_abbreviation = league.get("abbreviation", "N/A")
            league_start_date = league.get("season", {}).get("startDate", "N/A")
            league_end_date = league.get("season", {}).get("endDate", "N/A")

            logos = league.get("logos", [])
            logo_href = logos[0].get("href", "N/A") if logos else "N/A"

            league_info.append({
                "name": league_name,
                "abbreviation": league_abbreviation,
                "startDate": _parse_date(hass, league_start_date, show_time=False),
                "endDate": _parse_date(hass, league_end_date, show_time=False),
                "logo_href": logo_href
            })

        return league_info

    except Exception as e:
        _LOGGER.error(f"Error processing league data: {e}")
        return []

def get_season_slug_or_displayname(match):
    season_data = match.get("season", {})
    
    # Check for 'slug' first
    slug = season_data.get("slug")
    if slug:
        return slug
    
    # Fall back to 'displayName' if no slug
    display_name = season_data.get("displayName")
    return display_name
    
def process_match_data(data, hass, team_name=None, team_id=None, next_match_only=False, start_date=None, end_date=None, recent_match_hours=24):
    try:
        matches_data = data.get("events", [])
        league_info = process_league_data(data, hass)
        matches = []
        team_logo = None

        # Build id-keyed lookup so per-match league resolution works for multi-league
        # endpoints like /all/scoreboard (which has many leagues in the top-level array)
        top_leagues = data.get("leagues", [])
        leagues_by_id = {}
        for _lg in top_leagues:
            _lid = str(_lg.get("id", "") or "")
            if _lid:
                _logos = _lg.get("logos", [])
                leagues_by_id[_lid] = {
                    "name": _lg.get("name") or _lg.get("abbreviation") or "",
                    "logo": _logos[0].get("href", "") if _logos else "",
                }
        # For single-league endpoints use the name directly as before
        top_league_name = top_leagues[0].get("name", "N/A") if len(top_leagues) == 1 else "N/A"

        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        team_id_str = str(team_id) if team_id else None

        for match in matches_data:
            # When team_id is available prefer ID matching (done after extracting competitors).
            # Fall back to name pre-filter only when we have no ID.
            if team_name and not team_id_str:
                match_name = match.get("name", "").lower()
                if team_name.lower() not in match_name:
                    continue

            match_date_str = match.get("date", "")

            try:
                match_date = parser.isoparse(match_date_str).astimezone(timezone.utc) if match_date_str else None
            except ValueError:
                _LOGGER.error(f"Error parsing match date: {match_date_str}")
                continue

            if start_date and match_date and match_date < start_date:
                continue
            if end_date and match_date and match_date > end_date:
                continue

            # Only for mixed sensor type
            season_info = get_season_slug_or_displayname(match)
            week_number = (match.get("week") or {}).get("number")

            competitions = match.get("competitions", [])
            comp = competitions[0] if competitions else {}
            comp_league = comp.get("league", {}) or {}
            # team schedule endpoint (/all/teams/{id}/schedule) puts league at event level
            event_league = match.get("league", {}) or {}
            league_id = str(comp_league.get("id", "") or event_league.get("id", "") or "")

            # For /all/scoreboard the league id is encoded in the competition uid:
            # e.g.  "s:600~l:ned.1~e:700001"  →  league_id = "ned.1"
            if not league_id:
                comp_uid = comp.get("uid", "") or match.get("uid", "") or ""
                for _part in comp_uid.split("~"):
                    if _part.startswith("l:"):
                        league_id = _part[2:]
                        break

            # /all/scoreboard: comp.altGameNote = "FIFA World Cup, Group F" → league name
            alt_note = (comp.get("altGameNote") or "").strip()
            league_name_from_note = alt_note.split(",")[0].strip() if alt_note else ""

            league_name = (
                comp_league.get("displayName")
                or comp_league.get("name")
                or event_league.get("displayName")
                or event_league.get("name")
                or (leagues_by_id.get(league_id, {}).get("name") if league_id else None)
                or league_name_from_note
                or (top_league_name if top_league_name != "N/A" else None)
                or "N/A"
            )
            league_logo = (leagues_by_id.get(league_id, {}).get("logo") if league_id else None) or ""
            _LOGGER.debug(
                "league_resolve: event=%s uid=%s league_id=%s comp_league=%s → name=%s",
                match.get("id"), comp.get("uid", match.get("uid", "")), league_id, comp_league, league_name
            )

            competitors = comp.get("competitors", []) if comp else []
            if len(competitors) < 2:
                _LOGGER.debug(f"Skipping match with fewer than 2 competitors: {match.get('name', 'unknown')}")
                continue

            home_team_data = competitors[0].get("team", {})
            if team_id_str:
                _home_id = str(home_team_data.get("id", ""))
                _away_id = str((competitors[1].get("team", {}) or {}).get("id", ""))
                if _home_id != team_id_str and _away_id != team_id_str:
                    continue
            home_team = home_team_data.get("displayName", "N/A")
            home_logo = home_team_data.get("logo", None)
            if not home_logo:
                home_logos = home_team_data.get("logos", [{}])
                home_logo = home_logos[0].get("href", "N/A")
            home_form = competitors[0].get("form", "N/A")
            home_score = competitors[0].get("score", "N/A")
            home_statistics = _get_statistics(competitors[0])

            away_team_data = competitors[1].get("team", {})
            away_team = away_team_data.get("displayName", "N/A")
            away_logo = away_team_data.get("logo", None)
            if not away_logo:
                away_logos = away_team_data.get("logos", [{}])
                away_logo = away_logos[0].get("href", "N/A")
            away_form = competitors[1].get("form", "N/A")
            away_score = competitors[1].get("score", "N/A")
            away_statistics = _get_statistics(competitors[1])

            status_type = match.get("status", {}).get("type", {})
            match_state = status_type.get("state", "N/A")
            match_status = status_type.get("description", "N/A")
            status_detail = status_type.get("detail", "N/A")
            clock = match.get("status", {}).get("displayClock", "N/A")
            period = match.get("status", {}).get("period", "N/A")

            venue_obj = comp.get("venue", {}) or {}
            venue = venue_obj.get("fullName", "N/A")
            venue_address = venue_obj.get("address", {}) or {}
            venue_city = venue_address.get("city", "N/A")
            venue_country = venue_address.get("country", "N/A")

            home_abbrev = home_team_data.get("abbreviation", "N/A")
            home_color = home_team_data.get("color", "N/A")
            home_record = _get_record(competitors[0])
            home_top_scorer = _get_top_scorer(competitors[0])
            home_record_summary = competitors[0].get("recordSummary", "")
            home_standing_summary = competitors[0].get("standingSummary", "")

            away_abbrev = away_team_data.get("abbreviation", "N/A")
            away_color = away_team_data.get("color", "N/A")
            away_record = _get_record(competitors[1])
            away_top_scorer = _get_top_scorer(competitors[1])
            away_record_summary = competitors[1].get("recordSummary", "")
            away_standing_summary = competitors[1].get("standingSummary", "")

            broadcast = _get_broadcast(comp)
            broadcasts = _get_broadcasts(comp)
            neutral_site = comp.get("neutralSite", False)
            tickets_available = comp.get("ticketsAvailable", False)
            attendance = comp.get("attendance", 0)
            has_stats = comp.get("boxscoreAvailable", False)
            has_commentary = comp.get("playByPlayAvailable", False)
            match_links = _get_links(comp)

            match_details = _get_details(comp.get("details", []))

            if team_name and (team_name.lower() in home_team.lower() or team_name.lower() in away_team.lower()):
                team_logo = home_logo if team_name.lower() in home_team.lower() else away_logo

            match_data = {
                "event_id": match.get("id"),
                "date": _parse_date(hass, match.get("date")),
                "season_info": season_info,
                "week_number": week_number,
                "league_name": league_name,
                "league_logo": league_logo,
                "home_team": home_team,
                "home_abbrev": home_abbrev,
                "home_color": home_color,
                "home_logo": home_logo,
                "home_form": home_form,
                "home_score": home_score,
                "home_statistics": home_statistics,
                "home_record": home_record,
                "home_top_scorer": home_top_scorer,
                "home_record_summary": home_record_summary,
                "home_standing_summary": home_standing_summary,
                "away_team": away_team,
                "away_abbrev": away_abbrev,
                "away_color": away_color,
                "away_logo": away_logo,
                "away_form": away_form,
                "away_score": away_score,
                "away_statistics": away_statistics,
                "away_record": away_record,
                "away_top_scorer": away_top_scorer,
                "away_record_summary": away_record_summary,
                "away_standing_summary": away_standing_summary,
                "state": match_state,
                "status": match_status,
                "status_detail": status_detail,
                "clock": clock,
                "period": period,
                "venue": venue,
                "venue_city": venue_city,
                "venue_country": venue_country,
                "broadcast": broadcast,
                "broadcasts": broadcasts,
                "neutral_site": neutral_site,
                "tickets_available": tickets_available,
                "attendance": attendance,
                "has_stats": has_stats,
                "has_commentary": has_commentary,
                "links": match_links,
                "match_details": match_details,
            }
            matches.append(match_data)

        if next_match_only:
            # Priority 1: Live matches
            live_matches = [m for m in matches if m["state"] == "in"]
            if live_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Alle wedstrijden",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [live_matches[0]]
                }

            # Priority 2: Recently finished matches (within the configured window, default 48h)
            # ESPN returns events in chronological order, so [-1] is the most recent.
            recent_finished_matches = [m for m in matches
                if m["state"] == "post" and is_within_recent_window(m["date"], recent_match_hours)
            ]

            if recent_finished_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Alle wedstrijden",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [recent_finished_matches[-1]]
                }

            # Priority 3: Upcoming matches
            upcoming_matches = [m for m in matches if m["state"] == "pre"]
            if upcoming_matches:
                return {
                    "league_info": league_info,
                    "team_name": team_name if team_name else "Alle wedstrijden",
                    "team_logo": team_logo if team_logo else "N/A",
                    "matches": [upcoming_matches[0]]
                }

            # Off-season: no live/recent/upcoming match — return empty so sensor
            # does not fall back to the full season list (oldest match first = wrong).
            return {
                "league_info": league_info,
                "team_name": team_name if team_name else "Alle wedstrijden",
                "team_logo": team_logo if team_logo else "N/A",
                "matches": []
            }

        return {
            "league_info": league_info,
            "team_name": team_name if team_name else "Alle wedstrijden",
            "team_logo": team_logo if team_logo else "N/A",
            "matches": matches
        }

    except Exception as e:
        _LOGGER.error(f"Error processing match data: {e}")
        return {}

def is_within_recent_window(end_time, hours=24):
    """Ritorna True se la partita (kickoff) è avvenuta entro le ultime `hours`."""
    try:
        if isinstance(end_time, str):
            end_time_dt = datetime.strptime(end_time, "%d-%m-%Y %H:%M").replace(tzinfo=timezone.utc)
        elif isinstance(end_time, datetime):
            end_time_dt = end_time
        else:
            raise ValueError("La data fornita non è né una stringa né un oggetto datetime")
        current_time = datetime.now(timezone.utc)
        return current_time - end_time_dt <= timedelta(hours=hours)
    except Exception as e:
        _LOGGER.error(f"Error calculating recent interval ({hours}h): {e}")
        return False

# Backwards-compat alias
def is_within_last_48_hours(end_time):
    return is_within_recent_window(end_time, 48)

def _get_statistics(competitor):
    statistics = {}
    stats = competitor.get("statistics", [])
    for stat in stats:
        stat_name = stat.get("name", "Unknown")
        stat_value = stat.get("displayValue", "N/A")
        statistics[stat_name] = stat_value
    return statistics

def _get_record(competitor):
    """Restituisce il record stagionale della squadra (es. '14-6-14' = V-N-P)."""
    records = competitor.get("records", []) or []
    if records:
        return records[0].get("summary", "")
    return ""

def _get_top_scorer(competitor):
    """Restituisce il capocannoniere della squadra: {name, short_name, value}."""
    leaders = competitor.get("leaders", []) or []
    for ldr in leaders:
        if ldr.get("name") == "goals":
            tops = ldr.get("leaders", []) or []
            if tops:
                t = tops[0]
                athlete = t.get("athlete", {}) or {}
                return {
                    "name": athlete.get("displayName", ""),
                    "short_name": athlete.get("shortName", ""),
                    "value": t.get("displayValue", ""),
                }
    return None

def _get_broadcast(competition):
    """Returns the first broadcast channel name (backwards-compatible)."""
    gbs = competition.get("geoBroadcasts", []) or []
    if gbs:
        media = gbs[0].get("media", {}) or {}
        return media.get("shortName", "")
    return ""

def _get_broadcasts(competition):
    """Returns all broadcast channel names from geoBroadcasts."""
    gbs = competition.get("geoBroadcasts", []) or []
    channels = []
    for gb in gbs:
        name = (gb.get("media", {}) or {}).get("shortName", "")
        if name and name not in channels:
            channels.append(name)
    return channels

def _get_links(competition):
    """Extract compact links dict from competition.links for stats/commentary/video."""
    links_raw = competition.get("links", []) or []
    result = {}
    key_map = {
        "summary":     ["summary", "gamecenter"],
        "commentary":  ["commentary", "playbyplay"],
        "stats":       ["boxscore", "stats"],
        "video":       ["video", "highlights"],
    }
    for link in links_raw:
        rel = [r.lower() for r in (link.get("rel") or [])]
        href = link.get("href", "")
        if not href:
            continue
        for key, patterns in key_map.items():
            if key not in result and any(p in rel for p in patterns):
                result[key] = href
    return result

def process_summary_data(data):
    """Estrae lineup, formazioni, key events e head-to-head dal summary endpoint.
    Restituisce un dict con: lineup_home, lineup_away, formation_home, formation_away,
    key_events, head_to_head."""
    out = {
        "lineup_home": [],
        "lineup_away": [],
        "formation_home": "",
        "formation_away": "",
        "key_events": [],
        "head_to_head": [],
    }
    try:
        rosters = data.get("rosters", []) or []
        for r in rosters:
            home_away = r.get("homeAway", "")
            formation = r.get("formation", "")
            roster = r.get("roster", []) or []
            players = []
            for p in roster:
                a = p.get("athlete", {}) or {}
                players.append({
                    "name": a.get("displayName", ""),
                    "short_name": a.get("shortName", ""),
                    "jersey": p.get("jersey", ""),
                    "position": (p.get("position", {}) or {}).get("abbreviation", ""),
                    "starter": p.get("starter", False),
                    "headshot": (a.get("headshot", {}) or {}).get("href", ""),
                })
            if home_away == "home":
                out["lineup_home"] = players
                out["formation_home"] = formation
            elif home_away == "away":
                out["lineup_away"] = players
                out["formation_away"] = formation

        key_events = data.get("keyEvents", []) or []
        for ev in key_events:
            t = ev.get("type", {}) or {}
            clock = (ev.get("clock", {}) or {}).get("displayValue", "")
            team = (ev.get("team", {}) or {}).get("displayName", "")
            participants = ev.get("participants", []) or []
            athletes = []
            for p in participants:
                a = p.get("athlete", {}) or {}
                athletes.append(a.get("displayName", ""))
            out["key_events"].append({
                "type": t.get("type", ""),
                "type_text": t.get("text", ""),
                "short_text": ev.get("shortText", ""),
                "clock": clock,
                "team": team,
                "athletes": athletes,
                "scoring_play": ev.get("scoringPlay", False),
            })

        # The Team card shows at most 8 h2h matches and does not use logos;
        # limit to 10 entries and omit home_logo/away_logo to stay well
        # under the 16384-byte recorder payload limit.
        H2H_MAX = 10
        h2h = data.get("headToHeadGames", []) or []
        for game in h2h:
            if len(out["head_to_head"]) >= H2H_MAX:
                break
            events = game.get("events", []) or []
            for e in events:
                if len(out["head_to_head"]) >= H2H_MAX:
                    break
                comp = (e.get("competitions", []) or [{}])[0]
                competitors = comp.get("competitors", []) or []
                if len(competitors) < 2:
                    continue
                home_c = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
                away_c = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
                out["head_to_head"].append({
                    "date": e.get("date", ""),
                    "home_team": (home_c.get("team", {}) or {}).get("displayName", ""),
                    "home_score": home_c.get("score", ""),
                    "away_team": (away_c.get("team", {}) or {}).get("displayName", ""),
                    "away_score": away_c.get("score", ""),
                })
        # Recent form: boxscore.participants[].statistics contains lastFiveGames
        for participant in (data.get("boxscore", {}) or {}).get("players", []) or []:
            home_away = participant.get("homeAway", "")
            stats = participant.get("statistics", []) or []
            form_key = "last_five_home" if home_away == "home" else "last_five_away"
            for stat_group in stats:
                for stat in (stat_group.get("stats", []) or []):
                    if stat.get("name") == "lastFiveGames":
                        out[form_key] = stat.get("displayValue", "")
                        break

    except Exception as e:
        _LOGGER.error(f"Error processing summary data: {e}")
    return out

def process_news_data(data):
    articles = []
    try:
        items = data.get("articles", []) or []
        for a in items:
            images = a.get("images", []) or []
            img_obj = images[0] if images else {}
            img = img_obj.get("url", "")
            img_caption = img_obj.get("caption", "")
            img_credit = img_obj.get("credit", "")

            categories = a.get("categories", []) or []
            tags = []
            league_name = ""
            for c in categories:
                desc = c.get("description", "") or ""
                if c.get("type") == "league" and not league_name:
                    league_name = desc or (c.get("league", {}) or {}).get("description", "")
                if desc and desc not in tags:
                    tags.append(desc)

            byline = ""
            for contributor in (a.get("contributors", []) or []):
                name = contributor.get("name", "") or (contributor.get("athlete", {}) or {}).get("displayName", "")
                if name:
                    byline = name
                    break

            articles.append({
                "headline": a.get("headline", ""),
                "description": a.get("description", ""),
                "byline": byline,
                "published": a.get("published", ""),
                "last_modified": a.get("lastModified", ""),
                "image": img,
                "image_caption": img_caption,
                "image_credit": img_credit,
                "link": (a.get("links", {}) or {}).get("web", {}).get("href", "") or a.get("link", ""),
                "category": league_name,
                "tags": tags[:5],
                "type": a.get("type", ""),
                "premium": a.get("premium", False),
            })
    except Exception as e:
        _LOGGER.error(f"Error processing news: {e}")
    return articles

def _get_details(details):
    events = []
    for detail in details:
        event_type = detail.get("type", {}).get("text", "Unknown")
        clock = detail.get("clock", {}).get("displayValue", "N/A")
        athletes = [athlete.get("displayName", "Unknown") for athlete in detail.get("athletesInvolved", [])]
        athletes_str = ", ".join(athletes) if athletes else "N/A"
        team_abbr = (detail.get("team", {}) or {}).get("abbreviation", "")
        team_str = f" [{team_abbr}]" if team_abbr else ""
        events.append(f"{event_type}{team_str} - {clock}: {athletes_str}")
    return events

def process_scorers_data(data):
    """Extracts top scorers list from ESPN /leaders endpoint."""
    scorers = []
    try:
        for section in (data.get("leaders", []) or []):
            if "goal" not in section.get("name", "").lower():
                continue
            for entry in (section.get("leaders", []) or []):
                athlete = entry.get("athlete", {}) or {}
                team = entry.get("team", {}) or {}
                scorers.append({
                    "rank": entry.get("rank", len(scorers) + 1),
                    "goals": entry.get("displayValue", "0"),
                    "player": athlete.get("displayName", ""),
                    "short_name": athlete.get("shortName", ""),
                    "headshot": (athlete.get("headshot", {}) or {}).get("href", ""),
                    "team_name": team.get("displayName", ""),
                    "team_logo": team.get("logo", "") or "",
                })
            break
    except Exception as e:
        _LOGGER.error(f"Error processing top scorers data: {e}")
    return scorers


def _parse_date(hass, date_str, show_time=True):
    try:
        user_timezone = hass.config.time_zone
        parsed_date = parser.isoparse(date_str).replace(tzinfo=timezone.utc)
        local_tz = ZoneInfo(user_timezone)
        local_date = parsed_date.astimezone(local_tz)

        if show_time:
            return local_date.strftime("%d-%m-%Y %H:%M")
        else:
            return local_date.strftime("%d-%m-%Y")
    except (ValueError, TypeError) as e:

        return "N/A"