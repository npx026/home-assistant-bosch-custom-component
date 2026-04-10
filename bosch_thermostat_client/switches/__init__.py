"""
Switches of Bosch thermostat.
"""
from bosch_thermostat_client.const import (
    DEFAULT_STEP,
    ID,
    NAME,
    SELECT,
    TYPE,
    NUMBER,
    TURN_ON,
    TURN_OFF,
    BINARY,
)
from bosch_thermostat_client.const.ivt import ALLOWED_VALUES
from bosch_thermostat_client.const.easycontrol import USED, FALSE, TRUE
from bosch_thermostat_client.helper import BoschEntities

from bosch_thermostat_client.exceptions import DeviceException
from bosch_thermostat_client.switches.select import SelectSwitch
from .switch import Switch
from .boolean import BinarySwitch
from .number import NumberSwitch


class Switches(BoschEntities):
    """Sensors object containing multiple Sensor objects."""

    def __init__(self, connector, uri_prefix=None, parent=None):
        """
        Initialize sensors.

        :param dict requests: { GET: get function, SUBMIT: submit function}
        """
        self._connector = connector
        super().__init__(connector.get)
        self._items = {}
        self._number_switches = {}
        self._selects = {}
        self._uri_prefix = uri_prefix
        self._bases = {}
        self._parent = parent

    async def initialize(self, switches):
        if not switches:
            return

        def get_switch_type(switch, retrieved):
            _switch_type = switch.get(TYPE, False)
            if _switch_type == BINARY and (
                retrieved.get(USED, False) or switch.get(TURN_ON)
            ):
                return self._items, BinarySwitch
            elif _switch_type == NUMBER:
                return self._number_switches, NumberSwitch
            elif _switch_type == SELECT:
                return self._selects, SelectSwitch
            elif ALLOWED_VALUES in retrieved:
                return self._items, Switch
            return None, None

        async def prepare_switch(switch_id, switch, uri):
            retrieved = await self._get(uri)

            items, ChoosenSwitch = get_switch_type(switch=switch, retrieved=retrieved)
            if items is not None and ChoosenSwitch:
                items[switch_id] = ChoosenSwitch(
                    connector=self._connector,
                    attr_id=switch_id,
                    name=switch[NAME],
                    path=uri,
                    result=retrieved,
                    on_turn_on=switch.get(TURN_ON, TRUE),
                    on_turn_off=switch.get(TURN_OFF, FALSE),
                    default_step=switch.get(DEFAULT_STEP),
                    parent=self._parent,
                )

        for switch_id, switch in switches.items():
            try:
                _base = switch.get("base")
                if _base:
                    if _base in self._bases:
                        base = self._bases[_base]
                    else:
                        base = await self._get(_base)
                        self._bases[_base] = base
                    for ref in base.get("references", []):
                        ref_id = ref.get(ID)
                        if not ref_id:
                            continue
                        uri = (
                            f"{self._uri_prefix}{ref_id}{switch[ID]}"
                            if self._uri_prefix
                            else f"{ref_id}{switch[ID]}"
                        )
                        name = ref_id.split("/")[-1]
                        _switch = {
                            **switch,
                            ID: f"{ref_id}{switch[ID]}",
                            NAME: f"{switch[NAME]} {name}",
                        }
                        await prepare_switch(
                            switch_id=f"{name}{switch[ID]}", switch=_switch, uri=uri
                        )
                else:
                    uri = (
                        f"{self._uri_prefix}/{switch[ID]}"
                        if self._uri_prefix
                        else switch[ID]
                    )
                    await prepare_switch(switch_id=switch_id, switch=switch, uri=uri)

            except DeviceException:
                pass

    def __iter__(self):
        return iter(self._items.values())

    @property
    def switches(self):
        """Get switches list."""
        return self.get_items().values()

    @property
    def selects(self):
        """Get selects list."""
        return self._selects.values()

    @property
    def number_switches(self):
        """Get number switches."""
        return self._number_switches.values()
