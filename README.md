# ⚽ Soccer Live — Home Assistant Integration

Real-time football data in Home Assistant via the ESPN API with multi-language support, extensive sensor types, HA events, device grouping and performance optimizations.

> Built on ideas from [Calcio Live](https://github.com/Bobsilvio/calcio-live) by @Bobsilvio

---

## 📦 Installation via HACS

1. Add the repository as a **custom repository** in HACS:  
   `https://github.com/rononline/soccerlive` — category: **Integration**
2. Install **Soccer Live** via HACS
3. Restart Home Assistant
4. Go to **Settings → Integrations → Add Integration** and search for `Soccer Live`

> Also install the companion cards: [Soccer Live Card](https://github.com/rononline/soccerlive-card)

---

## 🗃️ Sensor types

Sensors are created automatically depending on your selection:

| Sensor type | Name | Description |
|---|---|---|
| `team_match` | `soccer_live_next_*` | Next / current match for a team |
| `team_matches` | `soccer_live_all_*` | All matches for a team (competition-specific) |
| `team_matches_mixed` | `soccer_live_all_mixed_*` | All matches for a team (all competitions) |
| `match_day` | `soccer_live_all_*` | All matches in a competition |
| `standings` | `soccer_live_standings_*` | League standings |
| `top_scorers` | `soccer_live_scorers_*` | Top scorers for a competition (auto-created) |
| `bracket` | `soccer_live_bracket_*` | Knockout bracket (auto-created for cup competitions) |
| `all_matches_today` | `soccer_live_all_today` | All matches worldwide today |
| `news` | `soccer_live_news_*` | News feed for a competition |
| `commentary` | `soccer_live_commentary_*` | Live play-by-play commentary for a match |

---

## ⚙️ Exclude from recorder

Add this to `configuration.yaml` to avoid database warnings:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.soccer_live_*
```

---

## 🔢 Finding a Team ID

Usually **not needed**: the ID is filled in automatically when you select a competition and team. Only required for manual entry.

1. **Via ESPN website**: open the team page on `espn.com` — the ID is the number in the URL:  
   `espn.com/soccer/team/_/id/`**`9723`**`/portland-timbers` → Team ID = **9723**
2. **Via ESPN API**:  
   `https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams`

---

## 📲 Push Notifications

The integration can automatically send push notifications when goals, cards, or match events occur. Configure this in the integration options:

1. Go to **Settings → Devices & Services → Soccer Live**
2. Click **Options** (gear icon)
3. Set **Notify Service** to your desired notification service:
   - `notify.mobile_app_yourphone` — iOS/Android Home Assistant app
   - `notify.telegram` — Telegram (requires notify.telegram service)
   - `notify.pushbullet` — PushBullet (requires notify.pushbullet service)
4. Save

**Notifications sent for:**
- ⚽ Goal scored
- 🟨 Yellow card issued
- 🟥 Red card issued
- 🔄 Substitution made
- 🏁 Match finished

Example notification: `"⚽ GOAL! Kramer (34') — Feyenoord 1 - 0 Sparta Rotterdam"`

### Alternative: Automations with Events

If you prefer more control, use Home Assistant automations with the exposed events instead:

---

## 🔔 Automations with Events

### Notification 15 minutes before kick-off

```yaml
alias: Football - Match starting soon
trigger:
  - platform: template
    value_template: >
      {{ state_attr('sensor.soccer_live_next_ned_1_feyenoord_rotterdam', 'next_match_minutes_until') == 15 }}
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.soccer_live_next_ned_1_feyenoord_rotterdam', 'next_match_status') == 'pre' }}
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⚽ Match starts in 15 min!"
      message: >
        {{ state_attr('sensor.soccer_live_next_ned_1_feyenoord_rotterdam', 'next_match_home_team') }}
        vs {{ state_attr('sensor.soccer_live_next_ned_1_feyenoord_rotterdam', 'next_match_away_team') }}
mode: single
```

### Notification on kick-off

```yaml
alias: Football - Match started
trigger:
  - platform: event
    event_type: soccer_live_match_started
condition:
  - condition: template
    value_template: >
      {{ trigger.event.data.home_team == 'Feyenoord Rotterdam'
         or trigger.event.data.away_team == 'Feyenoord Rotterdam' }}
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "🟢 Match started!"
      message: >
        {{ trigger.event.data.home_team }} vs {{ trigger.event.data.away_team }}
        — {{ trigger.event.data.venue }}
mode: single
```

### Notification on goal

```yaml
alias: Football - Goal notification
trigger:
  - platform: event
    event_type: soccer_live_goal
    event_data:
      team: Feyenoord Rotterdam   # omit to receive for all teams
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⚽ GOAL!"
      message: >
        {% set m = trigger.event.data.minute %}
        {{ trigger.event.data.player }}{{ " (" ~ m ~ "')" if m and m != 'N/A' else '' }} —
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
mode: queued
```

### Notification on yellow or red card

```yaml
alias: Football - Card notification
trigger:
  - platform: event
    event_type: soccer_live_yellow_card
  - platform: event
    event_type: soccer_live_red_card
action:
  - service: notify.mobile_app_my_phone
    data:
      title: >
        {{ '🟥 RED CARD!' if trigger.event_type == 'soccer_live_red_card' else '🟨 Yellow card' }}
      message: >
        {{ trigger.event.data.player }} ({{ trigger.event.data.minute }}')
        — {{ trigger.event.data.home_team }} vs {{ trigger.event.data.away_team }}
mode: queued
```

### Notification on substitution

```yaml
alias: Football - Substitution
trigger:
  - platform: event
    event_type: soccer_live_substitution
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "🔄 Substitution"
      message: >
        {{ trigger.event.data.player }} ({{ trigger.event.data.team }})
        minute {{ trigger.event.data.minute }}'
        — {{ trigger.event.data.home_team }} vs {{ trigger.event.data.away_team }}
mode: queued
```

### Notification on full time

```yaml
alias: Football - Final score
trigger:
  - platform: event
    event_type: soccer_live_match_finished
condition:
  - condition: or
    conditions:
      - condition: template
        value_template: "{{ trigger.event.data.home_team == 'Feyenoord Rotterdam' }}"
      - condition: template
        value_template: "{{ trigger.event.data.away_team == 'Feyenoord Rotterdam' }}"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⏹️ Full time"
      message: >
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
        {% if trigger.event.data.goal_scorers_str != 'N/A' %}
        · Scorers: {{ trigger.event.data.goal_scorers_str }}
        {% endif %}
mode: single
```

### Filter by competition

```yaml
# Eredivisie events only
condition:
  - condition: template
    value_template: "{{ trigger.event.data.competition_code == 'ned.1' }}"

# Or by league name
condition:
  - condition: template
    value_template: "{{ trigger.event.data.league_name == 'Dutch Eredivisie' }}"
```

### Big score alert (4+ goals in match)

```yaml
alias: Football - High scoring match
trigger:
  - platform: event
    event_type: soccer_live_goal
condition:
  - condition: template
    value_template: >
      {{ (trigger.event.data.home_score | int(0)) + (trigger.event.data.away_score | int(0)) >= 4 }}
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "🔥 High-scoring match!"
      message: >
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
mode: queued
```

### Draw alert

```yaml
alias: Football - Match ended in draw
trigger:
  - platform: event
    event_type: soccer_live_match_finished
condition:
  - condition: template
    value_template: "{{ trigger.event.data.home_score == trigger.event.data.away_score }}"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⚽ Draw!"
      message: >
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
mode: single
```

### Daily upcoming fixtures

```yaml
alias: Football - Today's fixtures
trigger:
  - platform: time
    at: "10:00:00"
condition:
  - condition: template
    value_template: "{{ state_attr('sensor.soccer_live_all_today', 'upcoming_matches_count') | int(0) > 0 }}"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⚽ Today's matches"
      message: >
        {{ (state_attr('sensor.soccer_live_all_today', 'matches') or [])[0:3] | map(attribute='home_team') | list | join(', ') }}
mode: single
```

### Goal by specific player

```yaml
alias: Football - Feyenoord goal by Giménez
trigger:
  - platform: event
    event_type: soccer_live_goal
    event_data:
      team: Feyenoord Rotterdam
condition:
  - condition: template
    value_template: "{{ 'Gimenez' in trigger.event.data.player }}"
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⚽ GIMÉNEZ SCORES!"
      message: >
        {{ trigger.event.data.player }} ({{ trigger.event.data.minute }}')
        — {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
mode: queued
```

### Red card alert (any team)

```yaml
alias: Football - Red card alert
trigger:
  - platform: event
    event_type: soccer_live_red_card
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "🟥 RED CARD!"
      message: >
        {{ trigger.event.data.team }} down to 10 men
        {{ trigger.event.data.player }} sent off ({{ trigger.event.data.minute }}')
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
mode: queued
```

---

## 📊 Available sensor attributes

**Next match** (`next_match_*`):
`home_team`, `away_team`, `home_score`, `away_score`, `date`, `datetime_iso`, `minutes_until`, `status` (`pre`/`in`/`post`), `clock`, `period`, `venue`, `home_logo`, `away_logo`, `home_form`, `away_form`

**Live match** (`live_match_*`): same fields as `next_match_*`

**Last match** (`last_match_*`):
`home_team`, `away_team`, `home_score`, `away_score`, `date`, `venue`

**Counters & booleans**:
`total_matches`, `live_matches_count`, `upcoming_matches_count`, `finished_matches_count`, `has_live_match`, `has_upcoming_match`, `has_recent_match`

---

## 📡 Available events

| Event | Fired when | Key fields |
|---|---|---|
| `soccer_live_match_started` | Kick-off (pre → in) | `home_team`, `away_team`, `venue`, `date`, `league_name`, `competition_code` |
| `soccer_live_goal` | Goal scored | `team`, `player`, `minute`, `home_score`, `away_score`, `league_name`, `competition_code` |
| `soccer_live_yellow_card` | Yellow card | `player`, `minute`, `team`, `home_team`, `away_team`, `league_name` |
| `soccer_live_red_card` | Red card | `player`, `minute`, `team`, `home_team`, `away_team`, `league_name` |
| `soccer_live_substitution` | Substitution | `player`, `minute`, `team`, `home_team`, `away_team`, `league_name` |
| `soccer_live_match_finished` | Full time | `home_score`, `away_score`, `goal_scorers`, `goal_scorers_str`, `league_name` |

---

## 🗂️ Sensor attribute data contract

These attributes are guaranteed to be present when available. Card developers can rely on this structure.

### Match object (inside `matches`, `previous_matches`, `upcoming_matches`)

| Attribute | Type | Description |
|---|---|---|
| `home_team` / `away_team` | string | Team names |
| `home_logo` / `away_logo` | string | Logo URLs |
| `home_score` / `away_score` | int\|str | Score or `N/A` |
| `state` | string | `pre` / `in` / `post` |
| `date` | string | `DD-MM-YYYY HH:MM` |
| `venue` / `venue_city` | string | Stadium info |
| `competition_name` / `competition_logo` | string | Competition identity |
| `broadcasts` | list | TV/streaming channels |
| `neutral_site` | bool | Neutral venue |
| `attendance` | int | Stadium attendance |
| `links` | dict | ESPN links: `stats`, `commentary`, `video`, `summary` |
| `has_stats` | bool | Boxscore available |
| `has_commentary` | bool | Play-by-play available |
| `clock` | string | Match clock (live) |

### Enriched team_match sensor (via summary endpoint)

Available after kick-off when `enable_summary_enrichment` is on:

| Attribute | Type | Description |
|---|---|---|
| `home_statistics` / `away_statistics` | dict | Raw ESPN stat keys → values |
| `key_events` | list | Goals, cards, subs with `clock`, `type`, `team`, `athletes` |
| `lineup_home` / `lineup_away` | list | Players with `position`, `jersey`, `headshot` |
| `head_to_head` | list | Recent H2H matches |
| `home_standing_summary` / `away_standing_summary` | string | League position |
| `home_record_summary` / `away_record_summary` | string | Season record |
| `last_five_home` / `last_five_away` | string | Form string (e.g. `WDWLW`) |

### Top-level computed attributes (next_match_* sensors)

`next_match_home_team`, `next_match_away_team`, `next_match_date`, `next_match_datetime_iso`, `next_match_minutes_until`, `next_match_status`, `next_match_venue`, `next_match_broadcasts`, `next_match_has_stats`, `next_match_has_commentary`, `next_match_links`, `next_match_attendance`, `next_match_neutral_site`

---

## 📜 License

GPL-3.0 — data via ESPN public APIs.
