# ⚽ Voetbal Live — Home Assistant Integratie

Realtime voetbaldata in Home Assistant via de ESPN API.  
Fork van [Calcio Live](https://github.com/Bobsilvio/calcio-live) door @Bobsilvio — uitgebreid met Nederlandse vertaling en diverse bugfixes.

---

## 📦 Installatie via HACS

1. Voeg de repository toe als **custom repository** in HACS:  
   `https://github.com/rononline/voetbal-live` — categorie: **Integratie**
2. Installeer **Voetbal Live** via HACS
3. Herstart Home Assistant
4. Ga naar **Instellingen → Integraties → Integratie toevoegen** en zoek op `Voetbal Live`

> Installeer ook de bijbehorende kaarten: [Voetbal Live Card](https://github.com/rononline/voetbal-live-card)

---

## 🗃️ Sensortypes

Na het instellen worden automatisch sensoren aangemaakt, afhankelijk van je keuze:

| Sensortype | Naam | Beschrijving |
|---|---|---|
| `team_match` | `calciolive_next_*` | Volgende / huidige wedstrijd van een team |
| `team_matches` | `calciolive_all_*` | Alle wedstrijden van een team (competitie-specifiek) |
| `team_matches_mixed` | `calciolive_all_mixed_*` | Alle wedstrijden van een team (alle competities) |
| `match_day` | `calciolive_all_*` | Alle wedstrijden van een competitie |
| `standings` | `calciolive_classifica_*` | Stand van een competitie |
| `bracket` | `calciolive_bracket_*` | KO-schema (automatisch voor bekertoernooien) |
| `all_matches_today` | `calciolive_all_today` | Alle wedstrijden van vandaag wereldwijd |
| `news` | `calciolive_news_*` | Nieuwsfeed van een competitie |

---

## ⚙️ Recorder uitsluiten

Voeg dit toe aan `configuration.yaml` om database-waarschuwingen te voorkomen:

```yaml
recorder:
  exclude:
    entity_globs:
      - sensor.calciolive_*
```

---

## 🔢 Team ID vinden

In de meeste gevallen **niet nodig**: bij het kiezen van competitie + team wordt het ID automatisch ingevuld. Alleen nodig bij handmatige invoer (bijv. voor de *mixed* sensor).

1. **Via ESPN-website**: open de teampagina op `espn.com` — het ID staat in de URL:  
   `espn.com/soccer/team/_/id/`**`9723`**`/portland-timbers` → Team ID = **9723**
2. **Via ESPN API**:  
   `https://site.api.espn.com/apis/site/v2/sports/soccer/all/teams`

---

## 🔔 Automaties

### Melding 15 minuten voor aanvang

```yaml
alias: Voetbal - Melding voor aanvang
trigger:
  - platform: template
    value_template: >
      {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_minutes_until') == 15 }}
condition:
  - condition: template
    value_template: >
      {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_status') == 'pre' }}
action:
  - service: notify.mobile_app_mijn_telefoon
    data:
      title: "⚽ Wedstrijd begint over 15 min!"
      message: >
        {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_home_team') }}
        vs {{ state_attr('sensor.calciolive_next_ned_1_feyenoord_rotterdam', 'next_match_away_team') }}
mode: single
```

### Melding bij doelpunt

```yaml
alias: Voetbal - Doelpunt melding
trigger:
  - platform: event
    event_type: calcio_live_goal
    event_data:
      team: Feyenoord Rotterdam   # weglaten voor alle teams
action:
  - service: notify.mobile_app_mijn_telefoon
    data:
      title: "⚽ DOELPUNT!"
      message: >
        {% set m = trigger.event.data.minute %}
        {{ trigger.event.data.player }}{{ " (" ~ m ~ "')" if m and m != 'N/A' else '' }} —
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
mode: queued
```

### Melding bij gele of rode kaart

```yaml
alias: Voetbal - Kaart melding
trigger:
  - platform: event
    event_type: calcio_live_yellow_card
  - platform: event
    event_type: calcio_live_red_card
action:
  - service: notify.mobile_app_mijn_telefoon
    data:
      title: >
        {{ '🟥 RODE KAART!' if trigger.event_type == 'calcio_live_red_card' else '🟨 Gele kaart' }}
      message: >
        {{ trigger.event.data.player }} ({{ trigger.event.data.minute }}')
        — {{ trigger.event.data.home_team }} vs {{ trigger.event.data.away_team }}
mode: queued
```

### Melding bij einde wedstrijd

```yaml
alias: Voetbal - Eindstand melding
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
  - service: notify.mobile_app_mijn_telefoon
    data:
      title: "⏹️ Wedstrijd afgelopen"
      message: >
        {{ trigger.event.data.home_team }} {{ trigger.event.data.home_score }}
        - {{ trigger.event.data.away_score }} {{ trigger.event.data.away_team }}
        {% if trigger.event.data.goal_scorers_str != 'N/A' %}
        · Doelpuntenmakers: {{ trigger.event.data.goal_scorers_str }}
        {% endif %}
mode: single
```

### Filteren op competitie

```yaml
# Alleen Eredivisie-events
condition:
  - condition: template
    value_template: "{{ trigger.event.data.competition_code == 'ned.1' }}"

# Of op leanaam
condition:
  - condition: template
    value_template: "{{ trigger.event.data.league_name == 'Dutch Eredivisie' }}"
```

---

## 📊 Beschikbare sensor-attributen

**Volgende wedstrijd** (`next_match_*`):
`home_team`, `away_team`, `home_score`, `away_score`, `date`, `datetime_iso`, `minutes_until`, `status` (`pre`/`in`/`post`), `clock`, `period`, `venue`, `home_logo`, `away_logo`, `home_form`, `away_form`

**Live wedstrijd** (`live_match_*`): zelfde velden als `next_match_*`

**Laatste wedstrijd** (`last_match_*`):
`home_team`, `away_team`, `home_score`, `away_score`, `date`, `venue`

**Tellers & booleans**:
`total_matches`, `live_matches_count`, `upcoming_matches_count`, `finished_matches_count`, `has_live_match`, `has_upcoming_match`, `has_recent_match`

---

## 📡 Beschikbare events

| Event | Wanneer | Belangrijkste velden |
|---|---|---|
| `calcio_live_goal` | Bij elk doelpunt | `team`, `player`, `minute`, `home_score`, `away_score`, `league_name`, `competition_code` |
| `calcio_live_yellow_card` | Bij gele kaart | `player`, `minute`, `home_team`, `away_team`, `league_name` |
| `calcio_live_red_card` | Bij rode kaart | `player`, `minute`, `home_team`, `away_team`, `league_name` |
| `calcio_live_match_finished` | Bij eindsignaal | `home_score`, `away_score`, `goal_scorers`, `goal_scorers_str`, `league_name` |

---

## 📜 Licentie

MIT — data via ESPN publieke API's.
