"""Config flow to configure esphome component."""
import logging

import voluptuous as vol
from bosch_thermostat_client import gateway_chooser
from bosch_thermostat_client.const import HTTP, XMPP
from bosch_thermostat_client.const.easycontrol import EASYCONTROL
from bosch_thermostat_client.const.ivt import IVT, IVT_MBLAN
from bosch_thermostat_client.const.nefit import NEFIT
from bosch_thermostat_client.connectors.oauth2 import Oauth2Connector
from bosch_thermostat_client.exceptions import (
    DeviceException,
    EncryptionException,
    FirmwareException,
    UnknownDevice,
)
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_ADDRESS, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import get_url, NoURLAvailableError

from . import create_notification_firmware
from .const import (
    ACCESS_KEY,
    ACCESS_TOKEN,
    CONF_DEVICE_TYPE,
    CONF_PROTOCOL,
    DOMAIN,
    OAUTH_CALLBACK_PATH,
    REFRESH_TOKEN,
    TOKEN_EXPIRES_AT,
    UUID,
)

DEVICE_TYPE = [NEFIT, IVT, EASYCONTROL, IVT_MBLAN]
PROTOCOLS = [HTTP, XMPP]


_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class BoschFlowHandler(config_entries.ConfigFlow):
    """Handle a bosch config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize Bosch flow."""
        self._choose_type = None
        self._host = None
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at = None
        self._password = None
        self._protocol = None
        self._device_type = None
        self._oauth_connector = None
        self._ha_redirect_uri = None
        self._pending_oauth_code = None
        self._reauth_entry = None

    async def async_step_user(self, user_input=None):
        """Handle flow initiated by user."""
        return await self.async_step_choose_type(user_input)

    async def async_step_choose_type(self, user_input=None):
        """Choose if setup is for IVT, IVT/MBLAN, NEFIT or EASYCONTROL."""
        errors = {}
        if user_input is not None:
            self._choose_type = user_input[CONF_DEVICE_TYPE]
            if self._choose_type == IVT:
                return self.async_show_form(
                    step_id="protocol",
                    data_schema=vol.Schema(
                        {
                            vol.Required(CONF_PROTOCOL): vol.All(
                                vol.Upper, vol.In(PROTOCOLS)
                            ),
                        }
                    ),
                    errors=errors,
                )
            elif self._choose_type == EASYCONTROL:
                return self.async_show_form(
                    step_id="easycontrol_serial",
                    data_schema=vol.Schema(
                        {vol.Required(CONF_ADDRESS): str}
                    ),
                    errors=errors,
                )
            elif self._choose_type in (NEFIT, IVT_MBLAN):
                return await self.async_step_protocol({CONF_PROTOCOL: XMPP})
        return self.async_show_form(
            step_id="choose_type",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): vol.All(
                        vol.Upper, vol.In(DEVICE_TYPE)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_protocol(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._protocol = user_input[CONF_PROTOCOL]
            return self.async_show_form(
                step_id=f"{self._protocol.lower()}_config",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_ADDRESS): str,
                        vol.Required(CONF_ACCESS_TOKEN): str,
                        vol.Optional(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )
        return self.async_show_form(
            step_id="protocol",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PROTOCOL): vol.All(vol.Upper, vol.In(PROTOCOLS)),
                }
            ),
            errors=errors,
        )

    async def async_step_http_config(self, user_input=None):
        if user_input is not None:
            self._host = user_input[CONF_ADDRESS]
            self._access_token = user_input[CONF_ACCESS_TOKEN]
            self._password = user_input.get(CONF_PASSWORD)
            return await self.configure_gateway(
                device_type=self._choose_type,
                session=async_get_clientsession(self.hass, verify_ssl=False),
                session_type=self._protocol,
                host=self._host,
                access_token=self._access_token,
                password=self._password,
            )

    async def async_step_xmpp_config(self, user_input=None):
        if user_input is not None:
            self._host = user_input[CONF_ADDRESS]
            self._access_token = user_input[CONF_ACCESS_TOKEN]
            self._password = user_input.get(CONF_PASSWORD)
            if "127.0.0.1" in user_input[CONF_ADDRESS]:
                return await self.configure_gateway(
                    device_type=self._choose_type,
                    session=async_get_clientsession(self.hass, verify_ssl=False),
                    session_type=HTTP,
                    host=self._host,
                    access_token=self._access_token,
                    password=self._password,
                )
            return await self.configure_gateway(
                device_type=self._choose_type,
                session_type=self._protocol,
                host=self._host,
                access_token=self._access_token,
                password=self._password,
            )

    def _build_ha_redirect_uri(self):
        """Return HA's OAuth callback URL, preferring external (Nabu Casa/DuckDNS) if available."""
        try:
            ha_base = get_url(self.hass, prefer_external=True)
        except NoURLAvailableError:
            ha_base = get_url(self.hass)
        return f"{ha_base}{OAUTH_CALLBACK_PATH}"

    async def async_step_easycontrol_serial(self, user_input=None):
        """Step 1 of EasyControl POINTT OAuth: enter device serial number.

        On submission, opens the Bosch SingleKey ID login page in the user's
        browser via HA's async_external_step mechanism. The login result is
        captured by BoschOAuthCallbackView and delivered as user_input to
        async_step_easycontrol_oauth, so the user never has to copy/paste a URL.
        """
        errors = {}
        if user_input is not None:
            self._host = user_input[CONF_ADDRESS].strip()
            session = async_get_clientsession(self.hass)
            self._oauth_connector = Oauth2Connector(
                host=self._host,
                access_token="",
                loop=session,
            )
            self._ha_redirect_uri = self._build_ha_redirect_uri()
            auth_url = self._oauth_connector.build_auth_url(
                redirect_uri=self._ha_redirect_uri,
                state=self.flow_id,  # echoed back by OAuth server
            )
            return self.async_external_step(
                step_id="easycontrol_oauth",
                url=auth_url,
            )
        return self.async_show_form(
            step_id="easycontrol_serial",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )

    async def async_step_easycontrol_oauth(self, user_input=None):
        """Step 2: Receives the auth code delivered by BoschOAuthCallbackView.

        Called automatically via hass.config_entries.flow.async_configure() when
        the OAuth redirect lands on /api/bosch_easycontrol/callback.
        user_input contains {"code": "...", "error": None | "access_denied"}.
        """
        if user_input is None:
            # Frontend is polling before the callback has arrived — keep waiting.
            return self.async_external_step(
                step_id="easycontrol_oauth",
                url=self._oauth_connector.build_auth_url(
                    redirect_uri=self._ha_redirect_uri,
                    state=self.flow_id,
                ),
            )

        error = user_input.get("error")
        if error:
            _LOGGER.warning("OAuth login returned error: %s", error)
            return self.async_abort(reason="oauth_error")

        code = user_input.get("code")
        if not code:
            return self.async_abort(reason="oauth_error")

        self._pending_oauth_code = code
        # Mark the external step done — HA closes the browser tab and
        # immediately advances to easycontrol_exchange.
        return self.async_external_step_done(next_step_id="easycontrol_exchange")

    async def async_step_easycontrol_exchange(self, user_input=None):
        """Step 2b: Exchange the auth code for tokens (runs after external step)."""
        success = await self._oauth_connector.exchange_code_for_tokens(
            self._pending_oauth_code
        )
        if not success:
            return self.async_abort(reason="cannot_connect")

        self._access_token = self._oauth_connector._access_token
        self._refresh_token = self._oauth_connector._refresh_token
        self._token_expires_at = self._oauth_connector._token_expires_at

        # Check if the gateway is already claimed
        session = async_get_clientsession(self.hass)
        try:
            from aiohttp import ClientTimeout
            url = Oauth2Connector.POINTTAPI_BASE_URL
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with session.get(url, headers=headers, timeout=ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    gateways = await resp.json()
                    device_ids = [gw.get("deviceId") for gw in gateways]
                    if self._host in device_ids:
                        _LOGGER.debug("Gateway %s already claimed", self._host)
                        return await self._easycontrol_create_entry()
        except Exception as err:
            _LOGGER.debug("Gateway list check failed: %s", err)

        # Gateway not yet claimed — ask for device label credentials
        return self.async_show_form(
            step_id="easycontrol_claim",
            data_schema=vol.Schema({
                vol.Required("access_code"): str,
                vol.Required("user_password"): str,
            }),
        )

    async def async_step_easycontrol_claim(self, user_input=None):
        """Step 3 of EasyControl POINTT OAuth: claim the gateway."""
        errors = {}
        if user_input is not None:
            import json as json_mod
            session = async_get_clientsession(self.hass)
            claim_url = f"{Oauth2Connector.POINTTAPI_BASE_URL}"
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            }
            payload = {
                "deviceId": self._host,
                "gatewayPassword": user_input["access_code"],
                "userPassword": user_input["user_password"],
            }

            try:
                from aiohttp import ClientTimeout
                async with session.post(
                    claim_url,
                    headers=headers,
                    json=payload,
                    timeout=ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 201:
                        _LOGGER.info("Successfully claimed gateway %s", self._host)
                        return await self._easycontrol_create_entry()
                    else:
                        body = await resp.text()
                        _LOGGER.error(
                            "Gateway claiming failed: HTTP %s - %s", resp.status, body
                        )
                        errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.error("Gateway claiming error: %s", err)
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="easycontrol_claim",
            data_schema=vol.Schema({
                vol.Required("access_code"): str,
                vol.Required("user_password"): str,
            }),
            errors=errors,
        )

    async def _easycontrol_create_entry(self):
        """Create config entry after successful OAuth + claiming."""
        from bosch_thermostat_client.gateway.oauth2 import Oauth2Gateway

        access_token = self._access_token
        refresh_token = self._refresh_token
        token_expires_at = self._token_expires_at

        try:
            gateway = Oauth2Gateway(
                session=async_get_clientsession(self.hass),
                device_type=EASYCONTROL,
                host=self._host,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=(
                    token_expires_at.isoformat() if token_expires_at else None
                ),
            )
            try:
                uuid = await gateway.check_connection()
            except (FirmwareException, UnknownDevice) as err:
                create_notification_firmware(hass=self.hass, msg=err)
                uuid = gateway.uuid
        except (DeviceException, EncryptionException) as err:
            _LOGGER.error("Cannot connect to EasyControl %s: %s", self._host, err)
            return self.async_abort(reason="faulty_credentials")
        except Exception as err:
            _LOGGER.error("Unexpected error connecting EasyControl %s: %s", self._host, err)
            return self.async_abort(reason="unknown")

        if uuid:
            await self.async_set_unique_id(str(uuid))
            self._abort_if_unique_id_configured()

        new_token_data = {
            ACCESS_TOKEN: access_token,
            REFRESH_TOKEN: refresh_token,
            TOKEN_EXPIRES_AT: (
                token_expires_at.isoformat() if token_expires_at else None
            ),
        }

        # Re-auth path: update existing entry and reload instead of creating new
        if self._reauth_entry is not None:
            self.hass.config_entries.async_update_entry(
                self._reauth_entry,
                data={**self._reauth_entry.data, **new_token_data},
            )
            await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            return self.async_abort(reason="reauth_successful")

        # First-time setup
        return self.async_create_entry(
            title=gateway.device_name or "Bosch EasyControl",
            data={
                CONF_ADDRESS: self._host,
                UUID: uuid,
                ACCESS_KEY: "",
                CONF_DEVICE_TYPE: EASYCONTROL,
                CONF_PROTOCOL: HTTP,
                **new_token_data,
            },
        )

    async def async_step_reauth(self, entry_data):
        """Triggered when TokenExpiredException fires in async_init_bosch.

        Stores the existing config entry and shows a confirmation form before
        re-opening the Bosch login page.
        """
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        self._host = self._reauth_entry.data.get(CONF_ADDRESS)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"device_id": self._host},
        )

    async def async_step_reauth_confirm(self, user_input=None):
        """User confirms — restart the OAuth external step to refresh tokens."""
        if user_input is not None:
            session = async_get_clientsession(self.hass)
            self._oauth_connector = Oauth2Connector(
                host=self._host,
                access_token="",
                loop=session,
            )
            self._ha_redirect_uri = self._build_ha_redirect_uri()
            auth_url = self._oauth_connector.build_auth_url(
                redirect_uri=self._ha_redirect_uri,
                state=self.flow_id,
            )
            return self.async_external_step(
                step_id="easycontrol_oauth",
                url=auth_url,
            )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"device_id": self._host},
        )

    async def configure_gateway(
        self, device_type, session_type, host, access_token, password=None, session=None
    ):
        try:
            BoschGateway = gateway_chooser(device_type)
            device = BoschGateway(
                session_type=session_type,
                host=host,
                access_token=access_token,
                password=password,
                session=session,
            )
            try:
                uuid = await device.check_connection()
            except (FirmwareException, UnknownDevice) as err:
                create_notification_firmware(hass=self.hass, msg=err)
                uuid = device.uuid
            if uuid:
                await self.async_set_unique_id(uuid)
                self._abort_if_unique_id_configured()
        except (DeviceException, EncryptionException) as err:
            _LOGGER.error("Wrong IP or credentials at %s - %s", host, err)
            return self.async_abort(reason="faulty_credentials")
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.error("Error connecting Bosch at %s - %s", host, err)
        else:
            _LOGGER.debug("Adding Bosch entry.")
            return self.async_create_entry(
                title=device.device_name or "Unknown model",
                data={
                    CONF_ADDRESS: device.host,
                    UUID: uuid,
                    ACCESS_KEY: device.access_key,
                    ACCESS_TOKEN: device.access_token,
                    CONF_DEVICE_TYPE: self._choose_type,
                    CONF_PROTOCOL: session_type,
                },
            )

    async def async_step_discovery(self, discovery_info=None):
        """Handle a flow discovery."""
        _LOGGER.debug("Discovered Bosch unit : %s", discovery_info)

    @staticmethod
    @callback
    def async_get_options_flow(entry: config_entries.ConfigEntry):
        """Get option flow."""
        return OptionsFlowHandler(entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for new API."""

    def __init__(self, entry: config_entries.ConfigEntry):
        """Initialize option."""
        self.entry = entry

    async def async_step_init(self, user_input=None):
        """Display option dialog."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        new_stats_api = self.entry.options.get("new_stats_api", False)
        optimistic_mode = self.entry.options.get("optimistic_mode", False)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("new_stats_api", default=new_stats_api): bool,
                    vol.Optional("optimistic_mode", default=optimistic_mode): bool,
                }
            ),
        )
