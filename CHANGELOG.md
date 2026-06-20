# Changelog

## v3.6.16 (2026-06-20)
- Add Home Assistant automation blueprints for goal, red card and match started notifications

## v3.6.15 (2026-06-20)
- Docs: document health attributes, automation last-event attributes, schedule summary attributes and new match color/count fields

## v3.6.14 (2026-06-20)
- Automation attributes: expose `last_event`, `last_event_type`, `last_event_timestamp` and typed last-event attributes for goals, cards, match started and match finished
- Health attributes: expose `last_successful_update`, `last_error` and `api_status`
- Schedule summary: expose deduplicated `schedule_*` counts and compact live/upcoming/recent match lists

## v3.6.13 (2026-06-20)
- Match sensors: expose top-level home/away colors and `team_colors` for card auto-skins
- Match sensors: expose next/live match abbreviations, event IDs, event counts, H2H counts and broadcast counts for richer cards and automations

## v3.6.12 (2026-06-19)
- `standings` sensor: remove fallback ESPN logo URL construction — ESPN uses numeric IDs not competition code strings, causing 404 errors; card now shows fallback emoji instead

## v3.6.11 (2026-06-19)
- `standings` sensor: when ESPN standings API returns no logo, construct fallback URL from competition code (`espncdn.com/leaguelogos/soccer/500/{code}.png`)
- `standings` sensor: state changed from Dutch "Stand" to "Standings"
- `standings` parser: broader logo extraction (tries top-level `logos`, then `leagues[0].logos`)

## v3.6.10 (2026-06-19)
- `standings` parser: include `league_logo` from ESPN logos array
- `bracket` sensor: include `league_logo` and `league_name` from `process_league_data`
- `match_day` sensor: include `league_logo`; state changed from Dutch "Speelronde" to "Match day"
- `commentary` sensor: include `league_logo`; state no longer says "Geen live wedstrijd" — now "No live match"
- `news` sensor: include `league_name` and empty `league_logo`; state no longer says "artikelen" — now "articles"

## v3.6.9 (2026-06-19)
- Fix Dutch sensor state strings: `"tegen"` → `"vs"`, `"wedstrijden beschikbaar"` → `"matches available"`, `"Geen wedstrijden beschikbaar"` → `"No matches available"`

## v3.6.8 (2026-06-19)
- `bracket.py`: remove dead `round_name_nl`/`name_nl` Dutch fields; simplify slug/canonical tuples to plain strings; translate Italian docstrings to English
- `sensor.py`: bracket sensor state now uses English — `"Round of 16 (16 teams)"` instead of `"Round of 16 (16 ploegen)"`; fallback `"Bracket unavailable"` instead of `"Bracket niet beschikbaar"`

## v3.6.7 (2026-06-19)
- README: `league_info` attribute added to data contract table
- Config-flow: `commentary` setup step added to all 6 translation files (was missing — showed blank UI)
- Comments in `bracket.py`, `standings.py`, `sensor.py` translated to English

## v3.6.6 (2026-06-18)
- Add `icon.png` inside component directory so the HA update entity shows the integration icon

## v3.6.5 (2026-06-18)
- `league_info` objects now include a `name` field (ESPN full league name, e.g. "FIFA World Cup") — Countdown card uses this to display the competition name

## v3.6.4 (2026-06-18)
- Translate remaining NL/IT inline comments in sensor.py to English

## v3.6.3 (2026-06-18)
- All remaining Dutch/Italian log messages translated to English (goal/card/substitution/match events in sensor.py)
- URL-based shared fetch cache: sensors sharing the same ESPN endpoint now share one fetch per cache window instead of fetching separately
- Parser tests added (17 passing): scoreboard and standings parsers tested against minimal ESPN fixtures; direct module import bypasses HA's `__init__.py`

## v3.6.2 (2026-06-18)
- All log messages standardized to English (IT/NL strings in sensor.py and parsers)
- Data contract table added to README: match object attributes, enriched sensor fields, top-level `next_match_*` attributes

## v3.6.1 (2026-06-17)
- Pass `enable_summary_enrichment` and `max_matches` to all sensor constructors (were read from options but not forwarded)
- Translation labels for `enable_summary_enrichment`, `max_matches`, `notify_service` added in all 7 languages
- `next_match_has_stats`/`next_match_has_commentary` use parser flags with fallback to statistics/events presence
- Diagnostics: `sensor_type` now read reliably from state attributes (works for `team_matches_mixed`, `all_matches_today`, etc.)
- `sensor_type` added as explicit state attribute on every sensor

## v3.6.0 (2026-06-17)

### Bug fix (high priority)
- `_parse_match_datetime()` now tries both `%d-%m-%Y %H:%M` and `%d/%m/%Y %H:%M` — mismatch was causing `next_match_datetime_iso` and `next_match_minutes_until` to always return `N/A`/`None`

### New top-level attributes
- `next_match_broadcasts` — list of TV/streaming channels
- `next_match_attendance`, `next_match_neutral_site`, `next_match_has_stats`, `next_match_has_commentary`, `next_match_links`, `next_match_week`

### Diagnostics
- `diagnostics.py` added — download via HA Settings → Integrations → Soccer Live; includes competition code, sensor types, request count, match count, cache age (no large match payloads)

### Options flow
- `enable_summary_enrichment` (default: on) — disable to skip ESPN summary endpoint and reduce API calls
- `max_matches` (0/5/10/15/20/30, default: 0 = unlimited) — caps `matches` list to reduce recorder payload

## v3.5.6 (2026-06-17)
- Normalise indentation in `_fetch_match_summary` and `_get_calendar_data` HTTP session blocks

## v3.5.5 (2026-06-17)
- Fix indentation in HTTP session blocks in `sensor.py` and `config_flow.py` (normalised after aiohttp migration)

## v3.5.4 (2026-06-17)
- Use `async_get_clientsession(hass)` instead of bare `aiohttp.ClientSession()` in sensor + config_flow
- `_scorers_unavailable` now correctly set to `True` on 404 — sensor skips subsequent requests

## v3.5.3 (2026-06-17)
- Team matching on ESPN `team_id` (competitor ID) when available; falls back to name matching
- Parser: `process_match_data()` accepts `team_id` parameter

## v3.5.2 (2026-06-16)
- Fix: `scoreboard.py` skips matches with `< 2 competitors` (postponed/incomplete ESPN events no longer crash the entire sensor update)

## v3.5.1 (2026-06-16)
- Live polling: sensors with active matches refresh automatically every 60 s (in addition to base interval)
- Live polling only applies to live-capable sensor types; standings/scorers/news/bracket unaffected
- `manifest.json` version synced to `3.5.0` (was `3.4.2`)
- `hacs.json`: description added

## v3.5.0 (2026-06-15)
- Standings: `zone_color`, `zone_label`, `zone_abbrev` from `entry.note` per team
- Scoreboard: `home/away_record_summary`, `home/away_standing_summary` from competitors
- Scoreboard: `broadcasts` (full list), `neutral_site`, `tickets_available` per match
- Scoreboard: `has_stats` (boxscoreAvailable), `has_commentary` (playByPlayAvailable)
- Scoreboard: `match_links` compact dict `{summary, commentary, stats, video}`
- Scoreboard: `week_number` from `events[].week.number`
- Summary: `last_five_home`/`last_five_away` from `boxscore.players[].statistics`
- News: `byline`, `last_modified`, `image_caption`, `image_credit`, `tags`, `premium`
- Top scorers 404: clear INFO log
- `manifest.json` version synced to 3.4.2
- News: `byline`, `last_modified`, `image_caption`, `image_credit`, `tags`, `premium`
- Top scorers 404: clear INFO log (not an error, ESPN doesn't support all competitions)

## v3.3.0 (2026-06-15)
- `async_step_campionato` → `async_step_league`, `step_id="campionato"` → `"league"` (all 7 translation files)
- `nome_squadra` / `nome_squadra_normalizzato` → `display_name_input` / `display_name_normalized`
- Italian error messages and comments in `parsers/scoreboard.py` → English
- All `CalcioLive*` class names in card code → `SoccerLive*`
- Releases consolidated: removed 30+ micro-releases

## v3.2.0 (2026-06-15)

## v3.1.2 (2026-06-15)
- Event tracking now uses `event_id` as primary key (fallback to team names)
- Prevents false deduplication on rematches, friendlies or team name changes

## v3.1.1 (2026-06-15)
- `_process_data` fully pure: events collected via passed `events: list` parameter
- All `_detect_and_dispatch_*` and `_dispatch_*` methods no longer mutate `self._pending_events`
- `self._save_store_needed` derived from events on event loop instead of set in executor
- Fallback return fixed: no longer reads `self._state` / `self._attributes`

## v3.1.0 (2026-06-15)
- Rename `sensori/` → `parsers/`, `classifica.py` → `standings.py`
- Rename `classifica_data()` → `standings_data()`
- Sensor IDs: `soccerlive_classifica_*` → `soccerlive_standings_*`, `soccerlive_cannonieri_*` → `soccerlive_scorers_*`
- Image filenames renamed from Italian to English
- All Italian inline comments replaced with English

## v3.0.9 (2026-06-15)
- `_process_data` returns `{"state": ..., "attributes": {...}, "events": [...]}` instead of mutating entity state in executor thread
- `self._state` and `self._attributes` now assigned on event loop only

## v3.0.8 (2026-06-15)
- Fix: manual team entry now sets `team_name` (was: created zero sensors)
- Fix: `start_date` / `end_date` from options flow now read correctly (was: only read from `entry.data`)
- Fix: cache hit path now runs `_enrich_with_summary()` and `_enrich_with_commentary()`
- Fix: translation key in team step: `team_id` → `team_name` in all 7 language files

## v3.0.7 (2026-06-15)
- Wrap data processing in `try/except`: malformed ESPN response no longer crashes sensor

## v3.0.6 (2026-06-15)
- Remove server-side geocoding (caused HA bootstrap timeout with 35+ pending tasks)

## v3.0.5 (2026-06-15)
- Non-blocking geocoding attempt (subsequently replaced by full removal in v3.0.6)

## v3.0.4 (2026-06-15)
- Server-side stadium geocoding via Nominatim (subsequently reverted due to bootstrap issues)

## v3.0.3 (2026-06-15)
- Add `icon.png` at repo root for HACS display
- Replace placeholder blue square with soccer ball icon

## v3.0.2 (2026-06-14)
- Critical fix: include `config_entry_id` in `unique_id` generation
- Prevents duplicate sensor errors when the same team is added in multiple config entries

---

## v3.0.0 (2026-06-14)
- Initial Soccer Live integration release (fork of Calcio Live by @Bobsilvio)
- Live Commentary sensor with play-by-play commentary
- Push notifications on goal, cards, substitution, match finished
- HA events: `soccer_live_goal`, `soccer_live_yellow_card`, `soccer_live_red_card`, `soccer_live_match_started`, `soccer_live_substitution`, `soccer_live_match_finished`
- Device grouping per config entry
- All sensors use `sensor.soccer_live_*` naming
