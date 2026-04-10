from __future__ import annotations
import logging
from typing import Any
from bosch_thermostat_client.const import (
    RESULT,
    URI,
    TYPE,
    VALUE,
    REGULAR,
)
from bosch_thermostat_client.const.ivt import ALLOWED_VALUES, INVALID
from bosch_thermostat_client.helper import BoschSingleEntity

_LOGGER = logging.getLogger(__name__)

ON_STATES = ["start", "on", "active"]
OFF_STATES = ["stop", "off"]


class BaseSwitch(BoschSingleEntity):
    """Base class for switch."""

    _type = REGULAR

    def __init__(self, attr_id, path, result, **kwargs):
        """
        Single switch init.

        :param dics requests: { GET: get function, SUBMIT: submit function}
        :param str name: name of the switches
        :param str path: path to retrieve data from switch.
        :param str obj: result retrieved during initialization.
        """
        super().__init__(attr_id=attr_id, path=path, **kwargs)
        self._data = {attr_id: {RESULT: {}, URI: path, TYPE: self._type}}
        self.process_results(result, attr_id)

    @property
    def state(self) -> Any:
        """Retrieve state of the switch."""
        result = self._data[self.attr_id].get(RESULT)
        if result:
            return self.check_state(result.get(VALUE, INVALID))
        return False

    def check_state(self, value):
        raise NotImplementedError


class Switch(BaseSwitch):
    """Single switch object."""

    _type = REGULAR
    _allowed_types = REGULAR

    async def turn_on(self) -> None:
        await self._turn_action(ON_STATES)

    async def turn_off(self) -> None:
        await self._turn_action(OFF_STATES)

    async def _turn_action(self, states) -> None:
        allowed = self._data[self.attr_id].get(RESULT, {}).get(ALLOWED_VALUES, [])
        _LOGGER.debug("Trying to toggle %s. Allowed values %s", states, allowed)
        for state in states:
            if state in allowed:
                await self._connector.put(self._data[self.attr_id][URI], state)
                self._data[self.attr_id][RESULT][VALUE] = state
                return

    def check_state(self, value):
        return True if value in ON_STATES else False
