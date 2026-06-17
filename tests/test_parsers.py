"""Parser tests — validate that ESPN data shapes produce expected attributes.

Run with:  python -m pytest tests/ -v
"""
import json
import importlib.util
from pathlib import Path
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
ROOT     = Path(__file__).parent.parent

def _load_parser(name):
    """Import a parser module directly, bypassing HA's __init__.py."""
    path = ROOT / "custom_components" / "soccer_live" / "parsers" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod  = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_scoreboard = _load_parser("scoreboard")
_standings  = _load_parser("standings")
process_match_data = _scoreboard.process_match_data
standings_data     = _standings.standings_data

class _MockHass:
    class config:
        time_zone = "Europe/Amsterdam"


# ---------------------------------------------------------------------------
# Scoreboard parser
# process_match_data(data, hass) → dict with key "matches" (list)
# ---------------------------------------------------------------------------

class TestScoreboardParser:
    def _load(self, name="scoreboard_minimal.json"):
        return json.loads((FIXTURES / name).read_text())

    def _parse(self, data=None, **kwargs):
        return process_match_data(data or self._load(), _MockHass(), **kwargs)

    def test_returns_dict_with_matches(self):
        result = self._parse()
        assert isinstance(result, dict)
        assert "matches" in result
        assert isinstance(result["matches"], list)

    def test_matches_not_empty(self):
        result = self._parse()
        assert len(result["matches"]) == 1

    def test_match_has_required_keys(self):
        match = self._parse()["matches"][0]
        required = {"home_team", "away_team", "home_score", "away_score", "state", "date"}
        missing = required - match.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_match_teams(self):
        match = self._parse()["matches"][0]
        assert match["home_team"] == "Ajax"
        assert match["away_team"] == "PSV"

    def test_match_state_scheduled(self):
        match = self._parse()["matches"][0]
        assert match["state"] == "pre"

    def test_broadcasts_extracted(self):
        match = self._parse()["matches"][0]
        assert isinstance(match.get("broadcasts", []), list)

    def test_has_stats_and_commentary_flags(self):
        match = self._parse()["matches"][0]
        assert match.get("has_stats") is False
        assert match.get("has_commentary") is False

    def test_graceful_on_empty_data(self):
        result = process_match_data({}, _MockHass())
        assert isinstance(result, dict)
        assert result.get("matches") == []

    def test_graceful_on_no_events(self):
        result = process_match_data({"leagues": [], "events": []}, _MockHass())
        assert result["matches"] == []


# ---------------------------------------------------------------------------
# Standings parser
# standings_data(data) → dict with key "standings_groups" (list of groups)
# Each group: {"name": str, "entries": [{"team_name", "rank", "points", ...}]}
# ---------------------------------------------------------------------------

class TestStandingsParser:
    def _load(self, name="standings_minimal.json"):
        return json.loads((FIXTURES / name).read_text())

    def _parse(self, data=None):
        return standings_data(data or self._load())

    def test_returns_dict_with_groups(self):
        result = self._parse()
        assert isinstance(result, dict)
        assert "standings_groups" in result
        assert isinstance(result["standings_groups"], list)

    def test_has_one_group(self):
        groups = self._parse()["standings_groups"]
        assert len(groups) == 1

    def test_group_has_standings(self):
        group = self._parse()["standings_groups"][0]
        assert "standings" in group
        assert len(group["standings"]) >= 1

    def test_entry_has_required_keys(self):
        entry = self._parse()["standings_groups"][0]["standings"][0]
        required = {"team_name", "rank", "wins", "losses", "points", "games_played"}
        missing = required - entry.keys()
        assert not missing, f"Missing keys: {missing}"

    def test_entry_team_name(self):
        entry = self._parse()["standings_groups"][0]["standings"][0]
        assert entry["team_name"] == "Ajax"

    def test_entry_rank_and_points(self):
        entry = self._parse()["standings_groups"][0]["standings"][0]
        assert entry["rank"] == 1
        assert entry["points"] == "65"

    def test_zone_info_extracted(self):
        entry = self._parse()["standings_groups"][0]["standings"][0]
        assert entry.get("zone_color") == "#007AC0"
        assert "Champions" in entry.get("zone_label", "")

    def test_graceful_on_empty_data(self):
        result = standings_data({})
        assert isinstance(result, dict)
        assert result.get("standings_groups") == []
