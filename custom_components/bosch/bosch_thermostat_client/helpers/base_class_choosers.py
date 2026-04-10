"""Helpers to Choose Main class"""
from bosch_thermostat_client.const import IVT
from bosch_thermostat_client.gateway import IVTGateway, NefitGateway


def gateway_chooser(device_type=IVT):
    return IVTGateway if device_type == IVT else NefitGateway
