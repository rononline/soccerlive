"""Live-event detection and dispatch for :class:`SoccerLiveSensor`.

This mixin groups the ``_detect_and_dispatch_*`` / ``_dispatch_*`` helpers that
compare successive match snapshots and fire the Home Assistant bus events for
goals, cards, substitutions, phase changes and full time. Split out of
``sensor.py`` to keep that module smaller; they rely only on ``self`` and carry
no shared class state.
"""

import logging
import re

_LOGGER = logging.getLogger(__name__)

class EventDispatchMixin:
    def _detect_and_dispatch_goals(self, matches, events: list):
        live_matches = [m for m in matches if m.get("state") == "in"]
        for match in live_matches:
            match_id = match.get("event_id") or f"{match.get('home_team', 'N/A')}_{match.get('away_team', 'N/A')}"
            home_score = match.get("home_score", 0)
            away_score = match.get("away_score", 0)
            try:
                home_score = int(home_score) if home_score != "N/A" else 0
                away_score = int(away_score) if away_score != "N/A" else 0
            except (ValueError, TypeError):
                home_score = 0
                away_score = 0
            if match_id not in self._previous_scores:
                self._previous_scores[match_id] = {
                    "home": home_score,
                    "away": away_score,
                    "match_details": match.get("match_details", []).copy()
                }
                continue
            prev_home = self._previous_scores[match_id]["home"]
            prev_away = self._previous_scores[match_id]["away"]
            curr_details = match.get("match_details", [])
            if match_id not in self._dispatched_goal_details:
                self._dispatched_goal_details[match_id] = set()
            dispatched = self._dispatched_goal_details[match_id]

            home_abbrev = match.get("home_abbrev", "")
            away_abbrev = match.get("away_abbrev", "")

            # Rich providers may return several historical goal incidents in the
            # first live response after a delayed refresh. Reconstruct each
            # score-at-event so notifications never label every scorer with the
            # latest aggregate score (for example two different 2-1 alerts).
            key_goals = self._new_key_goal_events(
                match, dispatched, prev_home, prev_away, home_score, away_score
            )
            if key_goals:
                for goal in key_goals:
                    side = goal["side"]
                    scoring_team = match.get(f"{side}_team", "N/A")
                    opponent_side = "away" if side == "home" else "home"
                    self._dispatch_goal_event(
                        scoring_team,
                        match.get(f"{opponent_side}_team", "N/A"),
                        1,
                        goal["home_score"],
                        goal["away_score"],
                        match,
                        [{"player": goal["player"], "minute": goal["minute"]}],
                        events,
                    )
                    dispatched.add(goal["key"])
                # The score increases have been emitted incident-by-incident;
                # keep the existing branches only for corrections/fallbacks.
                prev_home = home_score
                prev_away = away_score

            pending = self._pending_goal_scores.setdefault(match_id, {})
            defer_home = defer_away = False
            if home_score > prev_home:
                goals_scored = home_score - prev_home
                home_strings = self._pick_goal_strings(curr_details, dispatched, home_abbrev, goals_scored)
                goal_scorers = self._extract_goal_scorers_from_details(home_strings, goals_scored)
                have_scorer = any(self._real_scorer_name((g or {}).get("player")) for g in goal_scorers)
                if not have_scorer and pending.get("home", 0) < self._MAX_GOAL_DEFER:
                    # Scorer not known yet — hold this goal so it can arrive.
                    pending["home"] = pending.get("home", 0) + 1
                    defer_home = True
                else:
                    pending.pop("home", None)
                    synthetic_key = f"h_{home_score}"
                    if home_strings or synthetic_key not in dispatched:
                        self._dispatch_goal_event(match.get("home_team", "N/A"), match.get("away_team", "N/A"), goals_scored, home_score, away_score, match, goal_scorers, events)
                        dispatched.update(home_strings)
                        dispatched.add(synthetic_key)
            else:
                pending.pop("home", None)  # score reverted/unchanged — drop any hold
            if home_score < prev_home:
                self._dispatch_goal_cancelled_event(
                    match, "home", prev_home - home_score, prev_home, prev_away, events
                )
                dispatched.difference_update({
                    key for key in dispatched
                    if str(key).startswith("h_") and str(key)[2:].isdigit()
                    and int(str(key)[2:]) > home_score
                })
            if away_score > prev_away:
                goals_scored = away_score - prev_away
                away_strings = self._pick_goal_strings(curr_details, dispatched, away_abbrev, goals_scored)
                goal_scorers = self._extract_goal_scorers_from_details(away_strings, goals_scored)
                have_scorer = any(self._real_scorer_name((g or {}).get("player")) for g in goal_scorers)
                if not have_scorer and pending.get("away", 0) < self._MAX_GOAL_DEFER:
                    pending["away"] = pending.get("away", 0) + 1
                    defer_away = True
                else:
                    pending.pop("away", None)
                    synthetic_key = f"a_{away_score}"
                    if away_strings or synthetic_key not in dispatched:
                        self._dispatch_goal_event(match.get("away_team", "N/A"), match.get("home_team", "N/A"), goals_scored, home_score, away_score, match, goal_scorers, events)
                        dispatched.update(away_strings)
                        dispatched.add(synthetic_key)
            else:
                pending.pop("away", None)
            if away_score < prev_away:
                self._dispatch_goal_cancelled_event(
                    match, "away", prev_away - away_score, prev_home, prev_away, events
                )
                dispatched.difference_update({
                    key for key in dispatched
                    if str(key).startswith("a_") and str(key)[2:].isdigit()
                    and int(str(key)[2:]) > away_score
                })
            # Keep the previous score for a deferred side so the goal is
            # re-detected next poll (once the scorer arrives); always refresh
            # match_details so the scorer string can be picked up then.
            if not defer_home:
                self._previous_scores[match_id]["home"] = home_score
            if not defer_away:
                self._previous_scores[match_id]["away"] = away_score
            self._previous_scores[match_id]["match_details"] = curr_details.copy()

    @staticmethod
    def _new_key_goal_events(
        match, dispatched, previous_home, previous_away, current_home, current_away
    ):
        """Return undispatched goal incidents with reconstructed running scores."""
        if current_home <= previous_home and current_away <= previous_away:
            return []
        home_name = str(match.get("home_team") or "").casefold()
        away_name = str(match.get("away_team") or "").casefold()
        home_id = str(match.get("home_id") or "")
        away_id = str(match.get("away_id") or "")

        def minute_number(item):
            raw = str(item.get("minute") or item.get("clock") or "0")
            try:
                return sum(int(part) for part in raw.replace("'", "").split("+"))
            except ValueError:
                return 0

        goals = []
        for index, item in enumerate(match.get("key_events") or []):
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or item.get("type_text") or "").casefold()
            if not (item.get("scoring_play") or "goal" in kind):
                continue
            goals.append((minute_number(item), index, item))
        goals.sort(key=lambda value: (value[0], value[1]))
        if not goals:
            return []

        running_home = running_away = 0
        result = []
        for _, index, item in goals:
            team_name = str(item.get("team") or "").casefold()
            team_id = str(item.get("team_id") or "")
            side = (
                "home" if (team_id and team_id == home_id) or team_name == home_name
                else "away" if (team_id and team_id == away_id) or team_name == away_name
                else None
            )
            if side is None:
                return []
            if side == "home":
                running_home += 1
            else:
                running_away += 1
            key = "ke:{}:{}:{}:{}".format(
                item.get("id") or item.get("event_id") or index,
                item.get("minute") or item.get("clock") or "",
                item.get("player") or "",
                side,
            )
            if key in dispatched:
                continue
            changed_after_previous = (
                side == "home" and running_home > previous_home
                or side == "away" and running_away > previous_away
            )
            within_current = running_home <= current_home and running_away <= current_away
            if changed_after_previous and within_current:
                result.append({
                    "key": key,
                    "side": side,
                    "player": item.get("player") or "N/A",
                    "minute": item.get("minute") or item.get("clock") or "N/A",
                    "home_score": running_home,
                    "away_score": running_away,
                })
        return result

    def _dispatch_goal_cancelled_event(
        self, match, side, removed, previous_home, previous_away, events
    ):
        """Collect a score-correction event, commonly caused by VAR."""
        team = match.get(f"{side}_team", "N/A")
        events.append(("soccer_live_goal_cancelled", {
            "event_id": match.get("event_id"),
            "team": team,
            "goals_removed": removed,
            "reason": "score_correction",
            "home_team": match.get("home_team", "N/A"),
            "away_team": match.get("away_team", "N/A"),
            "previous_home_score": previous_home,
            "previous_away_score": previous_away,
            "home_score": match.get("home_score", 0),
            "away_score": match.get("away_score", 0),
            "clock": match.get("clock", "N/A"),
            "league_name": match.get("league_name", "N/A"),
            "date": match.get("date"),
            "date_iso": match.get("date_iso"),
            "competition_code": self._code,
            "sensor_name": self._name,
        }))

    @staticmethod
    def _is_scored_goal_detail(d):
        """Whether a match-detail string represents a goal that changed the score.

        ESPN writes scored penalties as "Penalty - Scored", API-Football as
        "Goal - Penalty"; both must be attributable. Disallowed goals and missed
        penalties never changed the score and are excluded."""
        if "Disallowed" in d or "Missed" in d:
            return False
        return "Goal" in d or "Penalty - Scored" in d

    def _pick_goal_strings(self, curr_details, dispatched, team_abbrev, count):
        """Return up to `count` new goal strings for a team.
        Filters by [ABBREV] tag when available; falls back to positional order.
        Uses the most-recent strings ([-count:]) so a late-arriving string from a
        previous goal is not attributed to the next goal. Disallowed goals and
        missed penalties are excluded so they cannot pollute future attribution."""
        all_new = [d for d in curr_details if self._is_scored_goal_detail(d) and d not in dispatched]
        if team_abbrev:
            tagged = [d for d in all_new if f"[{team_abbrev}]" in d]
            if tagged:
                return tagged[-count:]
        return all_new[-count:]

    def _extract_goal_scorers_from_details(self, goal_strings, goals_count):
        """Parse player name and minute from pre-filtered goal detail strings.
        Return a list of dicts with {player, minute}."""
        new_goals = []
        for detail in goal_strings:
            # Format: "Goal - 38': Bryan Mbeumo"
            try:
                parts = detail.split("': ")
                if len(parts) == 2:
                    player_name = parts[1].strip()
                    minute = parts[0].split(" - ")[-1].strip() if " - " in parts[0] else "N/A"
                    new_goals.append({"player": player_name, "minute": minute})
            except Exception as e:
                _LOGGER.debug(f"Error extracting player name: {e}")
        return new_goals[:goals_count]

    def _dispatch_goal_event(self, scoring_team, opponent_team, goals_count, home_score, away_score, match, goal_scorers=None, events: list | None = None):
        """Build and collect a goal event."""
        try:
            # goal_scorers is a list of {player, minute} dicts.
            # Also accepts plain strings for backwards compatibility.
            first = goal_scorers[0] if goal_scorers and len(goal_scorers) > 0 else None
            if isinstance(first, dict):
                player_name = self._real_scorer_name(first.get("player"))
                minute = first.get("minute", "N/A")
            elif isinstance(first, str):
                player_name = self._real_scorer_name(first)
                minute = "N/A"
            else:
                player_name = ""
                minute = "N/A"

            # Drop placeholder names ("<TBD>") so consumers see an empty scorer
            # (and can show their own "unknown" label) rather than the raw token.
            players = [
                self._real_scorer_name(g.get("player") if isinstance(g, dict) else g)
                for g in (goal_scorers or [])
            ]
            players = [name for name in players if name]

            event_data = {
                "event_id": match.get("event_id"),
                "team": scoring_team,
                "opponent": opponent_team,
                "goals_scored": goals_count,
                "player": player_name,
                "minute": minute,
                "players": players,
                "home_team": match.get("home_team", "N/A"),
                "away_team": match.get("away_team", "N/A"),
                "home_score": home_score,
                "away_score": away_score,
                "venue": match.get("venue", "N/A"),
                "match_status": match.get("status", "N/A"),
                "season_info": match.get("season_info", "N/A"),
                "league_name": match.get("league_name", "N/A"),
                "date": match.get("date"),
                "date_iso": match.get("date_iso"),
                "competition_code": self._code,
                "sensor_name": self._name,
            }
            if events is not None:
                events.append(("soccer_live_goal", event_data))
            _LOGGER.info(f"Goal detected: {scoring_team} scores (total: {goals_count}). Player: {player_name} ({minute}). Score: {home_score}-{away_score}")
        except Exception as e:
            _LOGGER.error(f"Error dispatching goal event: {e}")

    def _detect_and_dispatch_cards(self, matches, events: list):
        live_matches = [m for m in matches if m.get("state") == "in"]
        for match in live_matches:
            match_id = match.get("event_id") or f"{match.get('home_team', 'N/A')}_{match.get('away_team', 'N/A')}"
            match_details = match.get("match_details", [])
            if match_id not in self._previous_match_details:
                self._previous_match_details[match_id] = match_details.copy()
                continue
            prev_details = self._previous_match_details[match_id]
            for detail in match_details:
                if detail not in prev_details:
                    if "Yellow Card" in detail:
                        self._dispatch_card_event("yellow", detail, match, events)
                    elif "Red Card" in detail:
                        self._dispatch_card_event("red", detail, match, events)
                    elif "Substitution" in detail:
                        self._dispatch_substitution_event(detail, match, events)
            self._previous_match_details[match_id] = match_details.copy()

    def _dispatch_card_event(self, card_type, detail_str, match, events: list | None = None):
        """Build and collect a card event."""
        try:
            # Parse: "Yellow Card [TOT] - 27': Destiny Udogie" or "Red Card - 29': Cristian Romero"
            parts = detail_str.split("': ")
            minute = parts[0].split(" - ")[1] if " - " in parts[0] else "N/A"
            player = parts[1] if len(parts) > 1 else "N/A"

            team_match = re.search(r'\[([^\]]+)\]', detail_str)
            team = team_match.group(1) if team_match else "N/A"

            event_type = f"soccer_live_{card_type}_card"
            event_data = {
                "card_type": card_type.upper(),
                "player": player,
                "minute": minute,
                "team": team,
                "home_team": match.get("home_team", "N/A"),
                "away_team": match.get("away_team", "N/A"),
                "home_score": match.get("home_score", "N/A"),
                "away_score": match.get("away_score", "N/A"),
                "venue": match.get("venue", "N/A"),
                "match_status": match.get("status", "N/A"),
                "season_info": match.get("season_info", "N/A"),
                "league_name": match.get("league_name", "N/A"),
                "date": match.get("date"),
                "date_iso": match.get("date_iso"),
                "competition_code": self._code,
                "sensor_name": self._name,
            }
            if events is not None:
                events.append((event_type, event_data))
            _LOGGER.info(f"Card detected: {card_type.upper()} at {minute} | {player}")
        except Exception as e:
            _LOGGER.error(f"Error dispatching card event: {e}")

    def _dispatch_substitution_event(self, detail_str, match, events: list | None = None):
        """Dispatch a substitution event."""
        try:
            parts = detail_str.split("': ")
            minute = parts[0].split(" - ")[1] if " - " in parts[0] else "N/A"
            player = parts[1] if len(parts) > 1 else "N/A"
            team_match = re.search(r'\[([^\]]+)\]', detail_str)
            team = team_match.group(1) if team_match else "N/A"
            event_data = {
                "player": player,
                "minute": minute,
                "team": team,
                "home_team": match.get("home_team", "N/A"),
                "away_team": match.get("away_team", "N/A"),
                "home_score": match.get("home_score", "N/A"),
                "away_score": match.get("away_score", "N/A"),
                "league_name": match.get("league_name", "N/A"),
                "competition_code": self._code,
                "sensor_name": self._name,
            }
            if events is not None:
                events.append(("soccer_live_substitution", event_data))
            _LOGGER.info(f"Substitution: {player} ({team}) at {minute}")
        except Exception as e:
            _LOGGER.error(f"Error dispatching substitution event: {e}")

    def _detect_and_dispatch_match_started(self, matches, events: list):
        """Dispatch an event when a match transitions from pre to in."""
        for match in matches:
            match_id = match.get("event_id") or f"{match.get('home_team', 'N/A')}_{match.get('away_team', 'N/A')}"
            current_state = match.get("state")
            prev_state = self._previous_match_states.get(match_id)
            if current_state == "in" and prev_state == "pre":
                event_data = {
                    "event_id": match.get("event_id"),
                    "match_phase": "first_half",
                    "home_team": match.get("home_team", "N/A"),
                    "away_team": match.get("away_team", "N/A"),
                    "home_logo": match.get("home_logo", "N/A"),
                    "away_logo": match.get("away_logo", "N/A"),
                    "venue": match.get("venue", "N/A"),
                    "date": match.get("date", "N/A"),
                    "league_name": match.get("league_name", "N/A"),
                    "competition_code": self._code,
                    "sensor_name": self._name,
                }
                events.append(("soccer_live_match_started", event_data))
                _LOGGER.info(f"Match started: {match.get('home_team', 'N/A')} vs {match.get('away_team', 'N/A')}")
            if current_state:
                self._previous_match_states[match_id] = current_state

    def _detect_and_dispatch_phase_events(self, matches, events: list):
        """Fire a bus event on the transition into a notable phase (halftime,
        second half, postponed, cancelled). The first-observation guard
        (previous is not None) avoids false alerts on restart, matching the
        club-change/lineup pattern. match_started/match_finished are handled by
        state, so their phases are excluded from PHASE_EVENTS to avoid doubles."""
        from .match_contract import match_phase, phase_event
        for match in matches:
            match_id = str(match.get("event_id") or f"{match.get('home_team')}_{match.get('away_team')}")
            phase = match_phase(match)
            previous = self._previous_match_phases.get(match_id)
            event_name = phase_event(phase)
            if event_name and previous is not None and previous != phase:
                events.append((event_name, {
                    "event_id": match.get("event_id"),
                    "match_phase": phase,
                    "home_team": match.get("home_team"),
                    "away_team": match.get("away_team"),
                    "home_score": match.get("home_score"),
                    "away_score": match.get("away_score"),
                    "league_name": match.get("league_name"),
                    "competition_code": self._code,
                    "sensor_name": self._name,
                }))
            self._previous_match_phases[match_id] = phase

    def _detect_and_dispatch_match_finished(self, matches, events: list):
        finished_matches = [m for m in matches if m.get("state") == "post"]
        for match in finished_matches:
            match_id = match.get("event_id") or f"{match.get('home_team', 'N/A')}_{match.get('away_team', 'N/A')}"
            if match_id not in self._match_finished_dispatched:
                prev_state = self._previous_match_states.get(match_id)
                if prev_state is not None and prev_state != "post":
                    # Known in→post transition — fire the event
                    self._dispatch_match_finished_event(match, events)
                    _LOGGER.info(f"Match-finished event collected for: {match_id}")
                else:
                    # First poll already shows post: historical match, skip notification
                    _LOGGER.debug(f"Skipping match_finished for {match_id} (first seen already finished)")
                # Always mark dispatched to prevent firing again in future polls
                self._match_finished_dispatched.add(match_id)
                self._match_finished_list.append(match_id)
            self._previous_match_states[match_id] = "post"

    def _dispatch_match_finished_event(self, match, events: list | None = None):
        """Build and collect a match finished event."""
        try:
            # Extract goal scorers from match details
            goal_scorers = self._extract_all_goal_scorers(match.get("match_details", []))
            
            event_data = {
                "event_id": match.get("event_id"),
                "match_phase": "finished",
                "home_team": match.get("home_team", "N/A"),
                "away_team": match.get("away_team", "N/A"),
                "home_score": match.get("home_score", "N/A"),
                "away_score": match.get("away_score", "N/A"),
                "final_status": match.get("status", "N/A"),
                "venue": match.get("venue", "N/A"),
                "match_status": match.get("status", "N/A"),
                "date": match.get("date", "N/A"),
                "competition_code": self._code,
                "season_info": match.get("season_info", "N/A"),
                "league_name": match.get("league_name", "N/A"),
                "goal_scorers": goal_scorers,
                "goal_scorers_str": ", ".join(goal_scorers) if goal_scorers else "N/A",
                "sensor_name": self._name,
            }
            if events is not None:
                events.append(("soccer_live_match_finished", event_data))
            _LOGGER.info(f"Match finished: {match.get('home_team', 'N/A')} {match.get('home_score', '?')} - {match.get('away_score', '?')} {match.get('away_team', 'N/A')}. Scorers: {', '.join(goal_scorers)}")
        except Exception as e:
            _LOGGER.error(f"Error dispatching match finished event: {e}")

    def _extract_all_goal_scorers(self, match_details):
        """Extract all goal scorer names from match_details."""
        goal_scorers = []
        
        for detail in match_details:
            if "Goal" in detail and "Disallowed" not in detail:
                # Format: "Goal - 38': Bryan Mbeumo"
                try:
                    parts = detail.split("': ")
                    if len(parts) == 2:
                        player_name = parts[1].strip()
                        goal_scorers.append(player_name)
                except Exception as e:
                    _LOGGER.debug(f"Error extracting player name: {e}")
        
        return goal_scorers
