# Changelog

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
