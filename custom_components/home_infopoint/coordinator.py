"""DataUpdateCoordinator for Home.InfoPoint."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import HomeInfoPointClient
from .const import DOMAIN, CONF_USERNAME, CONF_PASSWORD, CONF_URL

_LOGGER = logging.getLogger(__name__)


class HomeInfoPointDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Home.InfoPoint data."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.api = HomeInfoPointClient(
            async_get_clientsession(hass),
            entry.data[CONF_USERNAME],
            entry.data[CONF_PASSWORD],
            entry.data[CONF_URL],
        )

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Disable automatic polling
            update_interval=None,
        )
        
        # Schedule daily update at 17:50
        # Assuming HA is configured with the correct timezone (Berlin)
        from homeassistant.helpers.event import async_track_time_change
        
        self.unsub_schedule = async_track_time_change(
            hass, 
            self._async_scheduled_update, 
            hour=17, 
            minute=50, 
            second=0
        )

    async def _async_scheduled_update(self, now):
        """Trigger update from schedule."""
        _LOGGER.debug(f"Triggering scheduled update at {now}")
        await self.async_request_refresh()

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            return await self.api.get_data()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
