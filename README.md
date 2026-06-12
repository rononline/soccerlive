# ⚽ Football Live — Home Assistant Integration

Real-time football data in Home Assistant via the ESPN API.  
Fork of [Calcio Live](https://github.com/Bobsilvio/calcio-live) by @Bobsilvio — extended with multi-language support, new sensors, events and various bug fixes.

---

## 📦 Installation via HACS

1. Add the repository as a **custom repository** in HACS:  
   `https://github.com/rononline/voetbal-live` — category: **Integration**
2. Install **Voetbal Live** via HACS
3. Restart Home Assistant
4. Go to **Settings → Integrations → Add Integration** and search for `Voetbal Live`

> Also install the companion cards: [Football Live Card](https://github.com/rononline/voetbal-live-card)

---

## 🗃️ Sensor types

Sensors are created automatically depending on your selection:

| Sensor type | Name | Description |
|---|---|---|
| `team_match` | `calciolive_next_*` | Next / current match for a team |
| `team_matches` | `calciolive_all_*` | All matches for a team (competition-specific) |
| `team_matches_mixed` | `calciolive_all_mixed_*` | All matches for a team (all competitions) |
| `match_day` | `calciolive_all_*` | All matches in a competition |
| `standings` | `calciolive_classifica_*` | League standings |
| `top_scorers` | `calciolive_cannonieri_*` | Top scorers for a competition (auto-created) |
| `bracket` | `calciolive_bracket_*` | Knockout bracket (auto-created for cup competitions) |
| `all_matches_today` | `calciolive_all_today` | All matches worldwide today |
| `news` | `calciolive_news_*` | News feed for a competition |

---

## ⚙️ Exclude from recorder

Add this to `configuration.yaml` to avoid database warnings:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.calciolive_*
```

---

## 🔢 Finding a Team ID

Usually **not needed**: the ID is filled in automatically when you select a competition and team. Only required for manual entry.

1. **Via ESPN website**: open the team page on `espn.com` — the ID is the number in the URL:  
   `espn.com/soccer/team/_/id/`**`9723`**`/portland-timbers` → Team ID = **9723**
2. **Via ESPN API**:  
   `https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams`

---

## 🔔 Automations

### Notification 15 minutes before kick-off

```yaml
alias: Football - Match starting soon
trigger:
  - platform: template
    value_template: >
      {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_minutes_until') == 15 }}
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_status') == 'pre' }}
action:
  - service: notify.mobile_app_my_phone
    data:
      title: "⚽ Match starts in 15 min!"
      message: >
        {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_home_team') }}
        vs {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_away_team') }}
mode: single
```

### Notification on kick-off

```yaml
alias: Football - Match started
trigger:
  - platform: event
    event_type: calcio_live_match_started
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
    event_type: calcio_live_goal
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
    event_type: calcio_live_yellow_card
  - platform: event
    event_type: calcio_live_red_card
action:
  - service: notify.mobile_app_my_phone
    data:
      title: >
        {{ '🟥 RED CARD!' if trigger.event_type == 'calcio_live_red_card' else '🟨 Yellow card' }}
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
    event_type: calcio_live_substitution
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
    event_type: calcio_live_match_finished
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
| `calcio_live_match_started` | Kick-off (pre → in) | `home_team`, `away_team`, `venue`, `date`, `league_name`, `competition_code` |
| `calcio_live_goal` | Goal scored | `team`, `player`, `minute`, `home_score`, `away_score`, `league_name`, `competition_code` |
| `calcio_live_yellow_card` | Yellow card | `player`, `minute`, `team`, `home_team`, `away_team`, `league_name` |
| `calcio_live_red_card` | Red card | `player`, `minute`, `team`, `home_team`, `away_team`, `league_name` |
| `calcio_live_substitution` | Substitution | `player`, `minute`, `team`, `home_team`, `away_team`, `league_name` |
| `calcio_live_match_finished` | Full time | `home_score`, `away_score`, `goal_scorers`, `goal_scorers_str`, `league_name` |

---

## 📜 License

GPL-3.0 — data via ESPN public APIs.
