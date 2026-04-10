import logging
from bosch_thermostat_client.const import (
    RESULT,
    SELECT,
    URI,
    VALUE,
)
from bosch_thermostat_client.const.ivt import ALLOWED_VALUES
from .switch import BaseSwitch

_LOGGER = logging.getLogger(__name__)


class SelectSwitch(BaseSwitch):
    """Number switch object."""

    _type = SELECT
    _allowed_types = SELECT

    def check_state(self, value):
        return value

    @property
    def options(self):
        return self._data[self.attr_id].get(RESULT, {}).get(ALLOWED_VALUES, [])

    async def set_value(self, value: str):
        if value in self.options:
            _LOGGER.debug("Trying to set value %s.", value)
            await self._connector.put(self._data[self.attr_id][URI], value)
            self._data[self.attr_id][RESULT][VALUE] = value
            _LOGGER.debug("Device accepted new value %s.", value)
