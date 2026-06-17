import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import logging
import aiohttp
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OPTION_SELECT_LEAGUE = "League"
OPTION_SELECT_TEAM = "Team"
OPTION_MANUAL_TEAM = "Manual entry"
OPTION_ALL_TODAY = "All matches today"
OPTION_NEWS = "News"
OPTION_COMMENTARY = "Live Commentary"

@config_entries.HANDLERS.register(DOMAIN)
class SoccerLiveConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._errors = {}
        self._data = {}
        self._teams = []

    async def async_step_user(self, user_input=None):
        self._errors = {}

        if user_input is not None:
            selection = user_input.get("selection")

            if selection == OPTION_SELECT_LEAGUE:
                self._data.update(user_input)
                return await self.async_step_league()

            elif selection == OPTION_SELECT_TEAM:
                self._data.update(user_input)
                return await self.async_step_select_competition_for_team()
            
            elif selection == OPTION_ALL_TODAY:
                self._data.update(user_input)
                self._data["competition_code"] = "99999"  # Dummy code for the "all matches today" sensor
                return self.async_create_entry(
                    title="All matches today",
                    data=self._data,
                )

            elif selection == OPTION_NEWS:
                self._data.update(user_input)
                return await self.async_step_news_competition()

            elif selection == OPTION_MANUAL_TEAM:
                self._data.update(user_input)
                return await self.async_step_manual_team()

            elif selection == OPTION_COMMENTARY:
                self._data.update(user_input)
                return await self.async_step_commentary()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("selection", default=OPTION_SELECT_LEAGUE): vol.In([OPTION_SELECT_LEAGUE, OPTION_SELECT_TEAM, OPTION_ALL_TODAY, OPTION_NEWS, OPTION_MANUAL_TEAM, OPTION_COMMENTARY]),
            }),
            errors=self._errors,
        )

    async def async_step_news_competition(self, user_input=None):
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            competition_name = await self._get_competition_name(competition_code)
            self._data.update({
                "competition_code": competition_code,
                "name": f"News {competition_name}",
                "selection": "News",
            })
            return self.async_create_entry(
                title=f"News {competition_name}",
                data=self._data,
            )

        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}
        return self.async_show_form(
            step_id="news_competition",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
        )

    async def async_step_league(self, user_input=None):
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            competition_name = await self._get_competition_name(competition_code)
            self._data.update({"competition_code": competition_code, "name": competition_name})

            # Calendar dates are now resolved dynamically by the sensor on each
            # update via _get_calendar_data, so the user is no longer prompted.
            return self.async_create_entry(
                title=self._data.get("name", "Soccer Live"),
                data=self._data,
            )

        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}

        return self.async_show_form(
            step_id="league",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
        )

    async def async_step_select_competition_for_team(self, user_input=None):
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            self._data.update({"competition_code": competition_code})

            await self._get_teams(competition_code)
            return await self.async_step_team()

        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}

        return self.async_show_form(
            step_id="select_competition_for_team",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
        )

    async def async_step_team(self, user_input=None):
        if user_input is not None:
            team_name = user_input["team_name"]
            competition_code = self._data.get("competition_code", "N/A")
            competition_name = await self._get_competition_name(competition_code)

            # Find the team ID for the selected team name
            selected_team = next((team for team in self._teams if team["displayName"] == team_name), None)
            team_id = selected_team["id"] if selected_team else None

            # Store team_id and team_name
            self._data.update({"team_name": team_name, "team_id": team_id, "name": f"Team {competition_name} {team_name}"})

            # Season dates are resolved dynamically by the sensor — no prompt needed.
            return self.async_create_entry(
                title=self._data.get("name", "Soccer Live"),
                data=self._data,
            )

        team_options = {team['displayName']: team['displayName'] for team in sorted(self._teams, key=lambda t: t['displayName'])}

        return self.async_show_form(
            step_id="team",
            data_schema=vol.Schema({
                vol.Required("team_name"): vol.In(team_options),
            }),
            errors=self._errors,
        )

    async def async_step_commentary(self, user_input=None):
        if user_input is not None:
            competition_code = user_input.get("competition_code")
            competition_name = await self._get_competition_name(competition_code)
            self._data.update({
                "competition_code": competition_code,
                "name": f"Commentary {competition_name}",
                "selection": "Live Commentary",
            })
            return self.async_create_entry(
                title=f"Commentary {competition_name}",
                data=self._data,
            )
        competitions = await self._get_competitions()
        sorted_competitions = {k: v for k, v in sorted(competitions.items(), key=lambda item: item[1])}
        return self.async_show_form(
            step_id="commentary",
            data_schema=vol.Schema({
                vol.Required("competition_code"): vol.In(sorted_competitions),
            }),
            errors=self._errors,
        )

    async def async_step_manual_team(self, user_input=None):
        if user_input is not None:
            team_id = user_input["manual_team_id"]
            competition_code = self._data.get("competition_code", "N/A")
            if competition_code and competition_code != "N/A":
                competition_name = await self._get_competition_name(competition_code)
            else:
                competition_name = "Vrije invoer"
            display_name_input = user_input.get("name", "")
            display_name_normalized = display_name_input.replace(" ", "_").lower()

            display_name = display_name_input if display_name_input else team_id
            self._data.update({
                "team_id": team_id,
                "team_name": display_name,
                "name": f"Team {competition_name} {team_id} {display_name_normalized}",
            })

            # Season dates are resolved dynamically by the sensor — no prompt needed.
            return self.async_create_entry(
                title=self._data.get("name", "Soccer Live"),
                data=self._data,
            )

        return self.async_show_form(
            step_id="manual_team",
            data_schema=vol.Schema({
                vol.Required("manual_team_id"): str,
                vol.Optional("name", default=""): str,
            }),
            errors=self._errors,
        )



    async def _get_competitions(self):
        url = "https://site.api.espn.com/apis/site/v2/leagues/dropdown?lang=en&region=us&calendartype=whitelist&limit=200&sport=soccer"
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status()
                    competitions_data = await response.json()
                    return {league['slug']: league['name'] for league in competitions_data.get("leagues", [])}
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error loading competitions: {e}")
            return {}

    async def _get_competition_name(self, competition_code):
        """Return the competition display name for the given competition code."""
        competitions = await self._get_competitions()
        return competitions.get(competition_code, "Unknown competition")

    async def _get_teams(self, competition_code):
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{competition_code}/teams"
        try:
            session = async_get_clientsession(self.hass)
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    response.raise_for_status()
                    teams_data = await response.json()
                
                    leagues = teams_data.get("sports", [{}])[0].get("leagues", [{}])
                    if not leagues:
                        self._teams = []
                        return

                    self._teams = [
                        {"id": team["team"]["id"], "displayName": team["team"]["displayName"]}
                        for league in leagues for team in league.get("teams", [])
                    ]
        except aiohttp.ClientError as e:
            _LOGGER.error(f"Error loading teams for {competition_code}: {e}")
            self._teams = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SoccerLiveOptionsFlow()


class SoccerLiveOptionsFlow(config_entries.OptionsFlow):

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            user_input.pop("info", None)
            return self.async_create_entry(title="", data=user_input)

        today = datetime.now()

        start_date = self.config_entry.options.get(
            "start_date", self.config_entry.data.get("start_date", (today - relativedelta(months=3)).strftime("%Y-%m-%d"))
        )
        end_date = self.config_entry.options.get(
            "end_date", self.config_entry.data.get("end_date", (today + relativedelta(months=4)).strftime("%Y-%m-%d"))
        )
        recent_match_hours = self.config_entry.options.get("recent_match_hours", 24)
        scan_interval = self.config_entry.options.get("scan_interval", 3)
        notify_service = self.config_entry.options.get("notify_service", "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional("scan_interval", default=scan_interval): vol.In([1, 2, 3, 5, 10]),
                vol.Optional("recent_match_hours", default=recent_match_hours): vol.In([6, 12, 24, 48]),
                vol.Optional("start_date", default=start_date): str,
                vol.Optional("end_date", default=end_date): str,
                vol.Optional("notify_service", default=notify_service): str,
            }),
        )
        
        
