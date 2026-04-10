from bosch_thermostat_client.circuits.easycontrol.base import EasycontrolCircuit
from ..circuit import CircuitWithSchedule
from bosch_thermostat_client.const import (
    NAME,
)
from bosch_thermostat_client.const.easycontrol import CIRCUIT_TYPES


class EasyDhwCircuit(CircuitWithSchedule, EasycontrolCircuit):
    def __init__(
        self, connector, attr_id, db, _type, bus_type, current_date=None, **kwargs
    ):
        super().__init__(
            connector=connector,
            attr_id=attr_id,
            db=db,
            _type=CIRCUIT_TYPES[_type],
            bus_type=bus_type,
            current_date=current_date,
        )

    @property
    def name(self):
        name = self.get_value(NAME)
        return name if name else super().name

    @property
    def support_presets(self):
        return False

    @property
    def setpoint(self):
        return CircuitWithSchedule.setpoint.fget(self)

    @property
    def support_target_temp(self):
        return True
