# Changelog

## v3.0.0 (2026-06-14)

### 🎯 Major Release: soccer_live Domain Only

**Breaking Changes:**
- Removed all backward compatibility with `calcio_live_` domain
- All entities now use `sensor.soccer_live_*` naming exclusively
- v2.x users must migrate to v3.0.0 (automatic entity migration recommended)

**What's New:**
- Live Commentary sensor with play-by-play commentary
- Push notifications support (configurable via integration options)
- All 7 improvement phases from card (loading states, error handling, offline cache)
- Enhanced async event handling (events queued safely in executor context)

### 📊 Sensor Types
All sensors now use consistent `sensor.soccer_live_*` naming:
- `team_match` - Next/current match
- `team_matches` - All matches for team
- `match_day` - Competition matches
- `standings` - League tables
- `top_scorers` - Top scorers
- `bracket` - Knockout brackets
- `all_matches_today` - Worldwide matches
- `commentary` - **NEW** - Live play-by-play

### 🔔 Push Notifications
Configure via integration options → Notify Service:
- `notify.mobile_app_yourphone` - iOS/Android
- `notify.telegram` - Telegram bot
- `notify.pushbullet` - PushBullet

Automatic notifications on:
- ⚽ Goal
- 🟨 Yellow card
- 🟥 Red card
- 🔄 Substitution
- 🏁 Match finished

### ⚡ Technical Improvements
- Fixed async operation safety in executor context
- Events properly queued in `_pending_events` during executor execution
- Async operations (`hass.bus.fire()`, notifications) on event loop only
- Better error handling in commentary sensor

### 📝 Documentation
- Comprehensive README with setup instructions
- 15+ automation examples
- Push notification configuration guide
- Migration guide from v2.x to v3.0.0

### ⚠️ Migration from v2.x
Users on v2.x (with `calcio_live_` domain) should:
1. Uninstall old `Calcio Live` integration
2. Uninstall old `Calcio Live Cards` (HACS)
3. Install new `Soccer Live` integration
4. Install new `Soccer Live Cards` (HACS)
5. Reconfigure automations to use `sensor.soccer_live_*` entities

---

## v2.17.3 (2026-06-14)
- All 7 improvement phases from card

## v2.17.2 (2026-06-12)
- Fix: commentary sensor data processing and state initialization

## v2.17.1 (2026-06-12)
- Fix: commentary sensor - use state field instead of status

## v2.17.0 (2026-06-11)
- Add Live Commentary sensor, push notifications support
