"""Bosch Indego Mower integration."""
import asyncio
import datetime
import json
import logging
import random
from sh import sed
from datetime import timedelta
from ssl import HAS_NPN



import homeassistant.util.dt
import voluptuous as vol
from aiohttp import ClientResponseError, ServerTimeoutError, TooManyRedirects
from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_ICON,
    CONF_ID,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_USERNAME,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLTAGE,
    DEVICE_CLASS_TIMESTAMP,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    STATE_ON,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from homeassistant.helpers.event import async_call_later
from homeassistant.util.dt import utcnow
from pyIndego import IndegoAsyncClient
from svgutils.transform import fromfile, fromstring

from .binary_sensor import IndegoBinarySensor
from .const import (
    BINARY_SENSOR_TYPE,
    CONF_ATTR,
    # CONF_POLLING,
    CONF_SEND_COMMAND,
    CONF_SMARTMOWING,
    CONF_DOWNLAD_MAP,
    CONF_DELETE_ALERT,
    CONF_READ_ALERT,
    DEFAULT_NAME,
    DEFAULT_NAME_COMMANDS,
    DEFAULT_MAP_NAME,
    DOMAIN,
    ENTITY_ALERT,
    ENTITY_LAST_COMPLETED,
    ENTITY_LAWN_MOWED,
    ENTITY_MOWER_STATE,
    ENTITY_MOWER_STATE_DETAIL,
    ENTITY_NEXT_MOW,
    ENTITY_ONLINE,
    ENTITY_UPDATE_AVAILABLE,
    ENTITY_FIRMWARE,
    ENTITY_MODELNUMBER,
    ENTITY_NEEDSSERVICE,
    ENTITY_SERIAL,
    ENTITY_SERVICECOUNTER,
    ENTITY_NAME,
    ENTITY_TIMEZONE,
    ENTITY_LATITUDE,
    ENTITY_LONGITUDE,
    ENTITY_YSVGPOS,
    ENTITY_YPOS,
    ENTITY_XSVGPOS,
    ENTITY_XPOS,
    ENTITY_BATTERY_PERCENT_ADJUSTED,
    ENTITY_BATTERY_PRECENT,
    ENTITY_BATTERY_CYCLES,
    ENTITY_BATTERY_AMBIENTE_TEMP,
    ENTITY_BATTERY_TEMP,
    ENTITY_BATTERY_DISCHARGE,
    ENTITY_BATTERY_VOLTAGE,
    ENTITY_RUNTIME_TOTAL_CHARGING,
    ENTITY_RUNTIME_TOTAL_MOWING,
    ENTITY_RUNTIME_TOTAL_OPERATION,
    ENTITY_RUNTIME_LAST_CHARGING,
    ENTITY_RUNTIME_LAST_MOWING,
    ENTITY_RUNTIME_LAST_OPERATION,
    ENTITY_MCC,
    ENTITY_MNC,
    ENTITY_RSSI,
    ENTITY_CURRMODE,
    ENTITY_CONFIGMODE,
    ENTITY_STEEREDRSSI,
    ENTITY_NETWORKCOUNT,
    ENTITY_COUNTRY,
    ENTITY_DISPLAYNAME,
    ENTITY_EMAIL,
    ENTITY_LANGUAGE,
    ENTITY_OPTIN,
    ENTITY_OPTINAPP,
    INDEGO_COMPONENTS,
    SENSOR_TYPE,
    SERVICE_NAME_COMMAND,
    SERVICE_NAME_DELETE_ALERT,
    SERVICE_NAME_SMARTMOW,
    SERVICE_NAME_DOWNLOAD_MAP,
    SERVICE_NAME_READ_ALERT,
    SERVICE_NAME_DELETE_ALERT_ALL,
    SERVICE_NAME_READ_ALERT_ALL,
    ENTITY_INNERBOUNDS,
    ENTITY_SIZE,
    ENTITY_SIGNALID,
    ENTITY_ID,
    ENTITY_MAPCELLSIZE,
    ENTITY_STOPS,
    ENTITY_BUMPS,
    ENTITY_HMIKEYSN,
    ENTITY_ALARM_MODE,
    ENTITY_BUMP_SENSITIVITY,
    ENTITY_WIRE_ID,
    ENTITY_IS_PIN_SET,
    ENTITY_BORDER_CUT,
    ENTITY_REGION,
    ENTITY_MODEL_DESCRIPTION,
    ENTITY_MODEL_VOLTAGE_MAX,
    ENTITY_MODEL_VOLTAGE_MIN,
    ENTITY_MOWING_MODE_DESCRIPTION,
    ENTITIY_MOW_TRIG,
    ENTITY_MAPSVGCACHETS,
    ENTITY_MAP_UPDATE_AVAILABLE,
    ENTITY_MOWMODE,
    ENTITY_STATE,
    ENTITY_CONFIG_CHANGE,
    ENTITY_HAS_INTEGRITY_CHECK,
    ENTITY_HAS_AUTO_CAL,
    ENTITY_HAS_MAP,
    ENTITY_HAS_PIN,
    ENTITY_HAS_OWNER,
    ENTITY_AUTOLOCK,
    ENTITY_ENABLED,
    ENTITY_GARDEN_LASTMOW,
    ENTITY_GARDEN_NAME,
    ENTITY_ALERT_COUNT,
    ENTITY_ALERT_ID,
    ENTITY_ALERT_ERROR_CODE,
    ENTITY_ALERT_HEADLINE,
    ENTITY_ALERT_DATE,
    ENTITY_ALERT_MESSAGE,
    ENTITY_ALERT_READ_STATUS,
    ENTITY_ALERT_FLAG,
    ENTITY_ALERT_PUSH,
    ENTITY_ALERT_DESCRIPTION,
)
from .sensor import IndegoSensor

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_PASSWORD): cv.string,
                vol.Optional(CONF_ID, default=None): cv.string,
                # vol.Optional(CONF_POLLING, default=False): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SERVICE_SCHEMA_COMMAND = vol.Schema({vol.Required(CONF_SEND_COMMAND): cv.string})

SERVICE_SCHEMA_SMARTMOWING = vol.Schema({vol.Required(CONF_SMARTMOWING): cv.string})

SERVICE_SCHEMA_DELETE_ALERT = vol.Schema({vol.Required(CONF_DELETE_ALERT): cv.positive_int})

SERVICE_SCHEMA_READ_ALERT = vol.Schema({vol.Required(CONF_READ_ALERT): cv.positive_int})

SERVICE_SCHEMA_DELETE_ALERT_ALL = vol.Schema({vol.Required(CONF_DELETE_ALERT): cv.string})

SERVICE_SCHEMA_READ_ALERT_ALL = vol.Schema({vol.Required(CONF_READ_ALERT): cv.string})

SERVICE_SCHEMA_DOWNLOAD_MAP = vol.Schema(
    {vol.Optional(CONF_DOWNLAD_MAP, default=DEFAULT_MAP_NAME): cv.string}
)


def FUNC_ICON_MOWER_ALERT(state):
    if state:
        if int(state) > 0 or state == STATE_ON:
            return "mdi:alert-outline"
    return "mdi:check-circle-outline"


ENTITY_DEFINITIONS = {
      ENTITY_ONLINE: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "online",
        CONF_ICON: "mdi:cloud-check",
        CONF_DEVICE_CLASS: DEVICE_CLASS_CONNECTIVITY,
        CONF_ATTR: [],
    },
    ENTITY_UPDATE_AVAILABLE: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "update available",
        CONF_ICON: "mdi:download-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
        ENTITY_FIRMWARE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "firmware",
        CONF_ICON: "mdi:source-branch",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MODELNUMBER: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "model number",
        CONF_ICON: "mdi:numeric",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_ALERT: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "alert",
        CONF_ICON: FUNC_ICON_MOWER_ALERT,
        CONF_DEVICE_CLASS: DEVICE_CLASS_PROBLEM,
        CONF_ATTR: ["alerts_count"],
    },
    ENTITY_MOWER_STATE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mower state",
        CONF_ICON: "mdi:robot-mower-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: ["last_updated", "model", "serial", "firmware"],
    },
    ENTITY_MOWER_STATE_DETAIL: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mower state detail",
        CONF_ICON: "mdi:robot-mower-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [
            "last_updated",
            "state_number",
            "state_description",
            "model_number",
        ],
    },
    ENTITY_BATTERY_PRECENT: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery %",
        CONF_ICON: "battery",
        CONF_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
        CONF_UNIT_OF_MEASUREMENT: "%",
        CONF_ATTR: [],
    },
    ENTITY_BATTERY_PERCENT_ADJUSTED: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery adjusted %",
        CONF_ICON: "battery",
        CONF_DEVICE_CLASS: DEVICE_CLASS_BATTERY,
        CONF_UNIT_OF_MEASUREMENT: "%",
        CONF_ATTR: [],
    },
    ENTITY_BATTERY_VOLTAGE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery voltage",
        CONF_ICON: "mdi:flash-triangle-outline",
        CONF_DEVICE_CLASS: DEVICE_CLASS_VOLTAGE,
        CONF_UNIT_OF_MEASUREMENT: "V",
        CONF_ATTR: [],
    },
    ENTITY_BATTERY_DISCHARGE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery discharge",
        CONF_ICON: "mdi:battery-arrow-down-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "Ah",
        CONF_ATTR: [],
    },
    ENTITY_BATTERY_TEMP: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery temp",
        CONF_ICON: "mdi:thermometer",
        CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        CONF_UNIT_OF_MEASUREMENT: "°C",
        CONF_ATTR: [],
    },
    ENTITY_BATTERY_AMBIENTE_TEMP: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery ambiente temperature",
        CONF_ICON: "mdi:thermometer",
        CONF_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        CONF_UNIT_OF_MEASUREMENT: "°C",
        CONF_ATTR: [],
    },
    ENTITY_BATTERY_CYCLES: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "battery cycles",
        CONF_ICON: "mdi:battery-sync-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_LAWN_MOWED: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "lawn mowed",
        CONF_ICON: "mdi:grass",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "%",
        CONF_ATTR: [],
    },
    ENTITY_LAST_COMPLETED: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "last completed",
        CONF_ICON: "mdi:calendar-check",
        CONF_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
        CONF_UNIT_OF_MEASUREMENT: "ISO8601",
        CONF_ATTR: [],
    },
    ENTITY_NEXT_MOW: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "next mow",
        CONF_ICON: "mdi:calendar-clock",
        CONF_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
        CONF_UNIT_OF_MEASUREMENT: "ISO8601",
        CONF_ATTR: [],
    },
    ENTITY_RUNTIME_TOTAL_OPERATION: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "runtime total operation",
        CONF_ICON: "mdi:timer-check-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "h",
        CONF_ATTR: [],
    },
    ENTITY_RUNTIME_TOTAL_MOWING: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "runtime total mowing",
        CONF_ICON: "mdi:timer-play-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "h",
        CONF_ATTR: [],
    },
    ENTITY_RUNTIME_TOTAL_CHARGING: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "runtime total charging",
        CONF_ICON: "mdi:timer-refresh-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "h",
        CONF_ATTR: [],
    },
    ENTITY_RUNTIME_LAST_OPERATION: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "runtime last operation",
        CONF_ICON: "mdi:timer-check-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "min",
        CONF_ATTR: [],
    },
    ENTITY_RUNTIME_LAST_MOWING: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "runtime last mowing",
        CONF_ICON: "mdi:timer-play-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "min",
        CONF_ATTR: [],
    },
    ENTITY_RUNTIME_LAST_CHARGING: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "runtime last charging",
        CONF_ICON: "mdi:timer-refresh-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "min",
        CONF_ATTR: [],
    },
    ENTITY_NEEDSSERVICE: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "needs service",
        CONF_ICON: "mdi:hammer-screwdriver",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_SERIAL: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "serial",
        CONF_ICON: "mdi:numeric",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_SERVICECOUNTER: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "service counter",
        CONF_ICON: "mdi:counter",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_NAME: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "name",
        CONF_ICON: "mdi:robot-mower-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_LONGITUDE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "longitude",
        CONF_ICON: "mdi:map-marker",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_LATITUDE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "latitude",
        CONF_ICON: "mdi:map-marker",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_TIMEZONE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "timezone",
        CONF_ICON: "mdi:map-clock",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_XPOS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "position x",
        CONF_ICON: "mdi:map-marker-radius-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_XSVGPOS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "position svg x",
        CONF_ICON: "mdi:image-marker",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_YPOS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "position y",
        CONF_ICON: "mdi:map-marker-radius-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_YSVGPOS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "position svg y",
        CONF_ICON: "mdi:image-marker",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_NETWORKCOUNT: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "networkcount",
        CONF_ICON: "mdi:numeric",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_STEEREDRSSI: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "steeredrssi",
        CONF_ICON: "mdi:signal",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "dBm",
        CONF_ATTR: [],
    },
    ENTITY_CONFIGMODE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "configmode",
        CONF_ICON: "mdi:script-text-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_CURRMODE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "currmode",
        CONF_ICON: "mdi:script-text-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_RSSI: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "rssi",
        CONF_ICON: "mdi:signal",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "dBm",
        CONF_ATTR: [],
    },
    ENTITY_MNC: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mobile network code",
        CONF_ICON: "mdi:numeric",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MCC: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mobile country code",
        CONF_ICON: "mdi:numeric",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_EMAIL: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "email",
        CONF_ICON: "mdi:at",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_LANGUAGE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "language",
        CONF_ICON: "mdi:translate",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_DISPLAYNAME: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "displayname",
        CONF_ICON: "mdi:rename-box",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_COUNTRY: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "country",
        CONF_ICON: "mdi:earth",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_OPTIN: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "optin",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_OPTINAPP: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "optinapp",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_INNERBOUNDS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "innerbounds",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_SIZE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "size",
        CONF_ICON: "mdi:ruler-square",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: "m²",
        CONF_ATTR: [],
    },
    ENTITY_SIGNALID: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "garden signal id",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_GARDEN_NAME: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "garden name",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_ID: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "garden id",
        CONF_ICON: "mdi:identifier",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MAPCELLSIZE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "map cell size",
        CONF_ICON: "mdi:map-legend",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_GARDEN_LASTMOW: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "garden last mow",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_STOPS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "stops",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_BUMPS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "bumps",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_HMIKEYSN: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "hmi key sn",
        CONF_ICON: "mdi:key-variant",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_STATE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "state",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_BUMP_SENSITIVITY: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "bump sensitivity",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_WIRE_ID: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "wire id",
        CONF_ICON: "mdi:identifier",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_BORDER_CUT: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "border cut",
        CONF_ICON: "mdi:content-cut",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_REGION: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "region",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_IS_PIN_SET: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "is pin set",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_ALARM_MODE: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "alarm mode",
        CONF_ICON: "mdi:shield-lock-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },    
    ENTITY_MODEL_DESCRIPTION: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "model description",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MODEL_VOLTAGE_MAX: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "model voltage max",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MODEL_VOLTAGE_MIN: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "model voltage min",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MOWING_MODE_DESCRIPTION: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mowing mode description",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITIY_MOW_TRIG: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mow tig",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MAPSVGCACHETS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "map svg cache ts",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_MAP_UPDATE_AVAILABLE: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "map update available",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    }, 
    ENTITY_MOWMODE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "mowmode",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },
    ENTITY_CONFIG_CHANGE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "config change",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   

    ENTITY_HAS_INTEGRITY_CHECK: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "has integrity check",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_HAS_AUTO_CAL: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "has auto calendar",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_HAS_MAP: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "has map",
        CONF_ICON: "mdi:map-search-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_HAS_PIN: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "has pin",
        CONF_ICON: "mdi:shield-account-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_HAS_OWNER: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "has owner",
        CONF_ICON: "mdi:account",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_ENABLED: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "enabled",
        CONF_ICON: "mdi:information-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_AUTOLOCK: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "autolock",
        CONF_ICON: "mdi:lock-clock",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
        ENTITY_ALERT_PUSH: {
        CONF_TYPE: BINARY_SENSOR_TYPE,
        CONF_NAME: "alert push",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_ATTR: [],
    },
    ENTITY_ALERT_COUNT: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert count",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },  
    ENTITY_ALERT_ID: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert id",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_ERROR_CODE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert errorcode",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_HEADLINE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert headline",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_DATE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert date",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_MESSAGE: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert message",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_READ_STATUS: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert read status",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_FLAG: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert flag",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },   
    ENTITY_ALERT_DESCRIPTION: {
        CONF_TYPE: SENSOR_TYPE,
        CONF_NAME: "alert description",
        CONF_ICON: "mdi:alert-octagon-outline",
        CONF_DEVICE_CLASS: None,
        CONF_UNIT_OF_MEASUREMENT: None,
        CONF_ATTR: [],
    },  
}


async def async_setup(hass, config: dict):
    """Set up the integration."""
    conf = config[DOMAIN]
    component = hass.data[DOMAIN] = IndegoHub(
        conf[CONF_NAME],
        conf[CONF_USERNAME],
        conf[CONF_PASSWORD],
        conf[CONF_ID],
        # conf[CONF_POLLING],
        hass,
    )

    async def load_platforms():
        await asyncio.gather(
            *[
                hass.async_create_task(
                    discovery.async_load_platform(hass, comp, DOMAIN, {}, config)
                )
                for comp in INDEGO_COMPONENTS
            ]
        )

    try:
        await component.login_and_schedule(load_platforms)
    except AttributeError as e:
        _LOGGER.warning("Login unsuccesfull: %s", e)
        return False

    async def async_send_command(call):
        """Handle the service call."""
        name = call.data.get(CONF_SEND_COMMAND, DEFAULT_NAME_COMMANDS)
        _LOGGER.debug("Indego.send_command service called, with command: %s", name)
        await hass.data[DOMAIN].indego.put_command(name)
        await hass.data[DOMAIN]._update_state()

    async def async_delete_alert(call):
        """Handle the service call."""
        alert_index = call.data.get(CONF_DELETE_ALERT, DEFAULT_NAME_COMMANDS)
        _LOGGER.debug("Indego.delete_alert service called, with command: %s", alert_index)
        await hass.data[DOMAIN]._update_alerts()
        await hass.data[DOMAIN].indego.delete_alert(alert_index)
        await hass.data[DOMAIN]._update_alerts()     

    async def async_delete_alert_all(call):
        """Handle the service call."""
        alert_index = call.data.get(CONF_DELETE_ALERT, DEFAULT_NAME_COMMANDS)
        _LOGGER.debug("Indego.delete_alert_all service called, with command: %s", "all")
        await hass.data[DOMAIN]._update_alerts()
        await hass.data[DOMAIN].indego.delete_all_alerts()
        await hass.data[DOMAIN]._update_alerts()   

    async def async_read_alert(call):
        """Handle the service call."""
        alert_index = call.data.get(CONF_READ_ALERT, DEFAULT_NAME_COMMANDS)
        _LOGGER.debug("Indego.read_alert service called, with command: %s", alert_index)
        await hass.data[DOMAIN]._update_alerts()
        await hass.data[DOMAIN].indego.put_alert_read(alert_index)
        await hass.data[DOMAIN]._update_alerts()

    async def async_read_alert_all(call):
        """Handle the service call."""
        alert_index = call.data.get(CONF_READ_ALERT, DEFAULT_NAME_COMMANDS)
        _LOGGER.debug("Indego.read_alert_all service called, with command: %s", "all")
        await hass.data[DOMAIN]._update_alerts()
        await hass.data[DOMAIN].indego.put_all_alerts_read()
        await hass.data[DOMAIN]._update_alerts()

    async def async_send_smartmowing(call):
        """Handle the service call."""
        name = call.data.get(CONF_SMARTMOWING, DEFAULT_NAME_COMMANDS)
        _LOGGER.debug("Indego.send_smartmowing service called, set to %s", name)
        await hass.data[DOMAIN].indego.put_mow_mode(name)
        await hass.data[DOMAIN]._update_generic_data()

    async def async_download_map(call):
        name = call.data.get(CONF_DOWNLAD_MAP, DEFAULT_MAP_NAME)
        filename = hass.config.path(f"www/{name}.svg")
        _LOGGER.debug("Indego.download_map service called")
        await hass.data[DOMAIN]._download_map(filename)

    hass.services.async_register(
        DOMAIN, SERVICE_NAME_COMMAND, async_send_command, schema=SERVICE_SCHEMA_COMMAND
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NAME_SMARTMOW,
        async_send_smartmowing,
        schema=SERVICE_SCHEMA_SMARTMOWING,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_NAME_DOWNLOAD_MAP,
        async_download_map,
        schema=SERVICE_SCHEMA_DOWNLOAD_MAP,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NAME_DELETE_ALERT, async_delete_alert, schema=SERVICE_SCHEMA_DELETE_ALERT
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NAME_READ_ALERT, async_read_alert, schema=SERVICE_SCHEMA_READ_ALERT
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NAME_DELETE_ALERT_ALL, async_delete_alert_all, schema=SERVICE_SCHEMA_DELETE_ALERT_ALL
    )
    hass.services.async_register(
        DOMAIN, SERVICE_NAME_READ_ALERT_ALL, async_read_alert_all, schema=SERVICE_SCHEMA_READ_ALERT_ALL
    )
    return True


class IndegoHub:
    """Class for the IndegoHub, which controls the sensors and binary sensors."""

    def __init__(self, name, username, password, serial, hass):
        # def __init__(self, name, username, password, serial, polling, hass):
        """Initialize the IndegoHub.

        Args:
            name (str): the name of the mower for entities
            username (str): username for indego service
            password (str): password for  indego service
            serial (str): serial of the mower, is used for uniqueness
            polling (bool): whether to keep polling the mower
            hass (HomeAssistant): HomeAssistant instance

        """
        self.mower_name = name
        self._username = username
        self._password = password
        self._serial = serial
        # self._polling = polling
        self._hass = hass

        self.indego = IndegoAsyncClient(self._username, self._password, self._serial)
        self.entities = {}
        self.refresh_state_task = None
        self.refresh_10m_remover = None
        self.refresh_24h_remover = None
        self._shutdown = False
        self._latest_alert = None

    def _create_entities(self):
        """Create sub-entities and add them to Hass."""
        for entity_key, entity in ENTITY_DEFINITIONS.items():
            if entity[CONF_TYPE] == SENSOR_TYPE:
                self.entities[entity_key] = IndegoSensor(
                    f"indego_{self._serial}_{entity_key}",
                    f"{self.mower_name} {entity[CONF_NAME]}",
                    entity[CONF_ICON],
                    entity[CONF_DEVICE_CLASS],
                    entity[CONF_UNIT_OF_MEASUREMENT],
                    entity[CONF_ATTR],
                )
            elif entity[CONF_TYPE] == BINARY_SENSOR_TYPE:
                self.entities[entity_key] = IndegoBinarySensor(
                    f"indego_{self._serial}_{entity_key}",
                    f"{self.mower_name} {entity[CONF_NAME]}",
                    entity[CONF_ICON],
                    entity[CONF_DEVICE_CLASS],
                    entity[CONF_ATTR],
                )

    async def login_and_schedule(self, load_platforms):
        """Login to the api."""
        login_success = await self.indego.login()
        if not login_success:
            raise AttributeError("Unable to login, please check your credentials")
        if not self._serial:
            self._serial = self.indego.serial
        self._create_entities()
        await load_platforms()
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED, self._initial_update
        )
        self._hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, self.async_shutdown)

    async def _initial_update(self, _):
        """Do the initial update of all entities."""
        _LOGGER.debug("Starting initial update.")
        self.refresh_state_task = self._hass.async_create_task(self.refresh_state())
        await asyncio.gather(*[self.refresh_10m(_), self.refresh_24h(_)])
        try:
            _LOGGER.debug("Refreshing initial operating data.")
            await self._update_operating_data()
        except Exception as e:
            _LOGGER.info("Update operating data got an exception: %s", e)

    async def async_shutdown(self, _):
        """Remove all future updates, cancel tasks and close the client."""
        self._shutdown = True
        if self.refresh_state_task:
            self.refresh_state_task.cancel()
            await self.refresh_state_task
        if self.refresh_10m_remover:
            self.refresh_10m_remover()
        if self.refresh_24h_remover:
            self.refresh_24h_remover()
        await self.indego.close()

    async def refresh_state(self):
        """Update the state, if necessary update operating data and recall itself."""
        _LOGGER.debug("Refreshing state.")
        try:
            await self._update_state()
        except Exception as e:
            _LOGGER.info("Update state got an exception: %s", e)
        try:
            await self._update_network()
        except Exception as e:
            _LOGGER.info("Update Network got an exception: %s", e)
        if self._shutdown:
            return
        if self.indego.state:
            state = self.indego.state.state
            if (500 <= state <= 799) or (state in (257, 260)):
                try:
                    _LOGGER.debug("Refreshing operating data.")
                    await self._update_operating_data()
                except Exception as e:
                    _LOGGER.info("Update operating data got an exception: %s", e)
            if self.indego.state.error != self._latest_alert:
                self._latest_alert = self.indego.state.error
                try:
                    _LOGGER.debug("Refreshing alerts, to get new alert.")
                    await self._update_alerts()
                except Exception as e:
                    _LOGGER.info("Update alert got an exception: %s", e)
        self.refresh_state_task = self._hass.async_create_task(self.refresh_state())

    async def refresh_10m(self, _):
        """Refresh Indego sensors every 10m."""
        _LOGGER.debug("Refreshing 10m.")
        results = await asyncio.gather(
            *[
                self._update_generic_data(),
                self._update_alerts(),
                self._update_last_completed_mow(),
                self._update_next_mow(),
                self._update_user(),
                self._update_setup(),
                self._update_security(),
            ],
            return_exceptions=True,
        )
        next_refresh = 600
        index = 0
        for res in results:
            if res:
                try:
                    raise res
                except Exception as e:
                    _LOGGER.warning("Uncaught error: %s on index: %s", e, index)
            index += 1
        self.refresh_10m_remover = async_call_later(
            self._hass, next_refresh, self.refresh_10m
        )

    async def refresh_24h(self, _):
        """Refresh Indego sensors every 24h."""
        _LOGGER.debug("Refreshing 24h.")
        try:
            await self._update_updates_available()
        except Exception as e:
            _LOGGER.info("Update updates available got an exception: %s", e)
        self.refresh_24h_remover = async_call_later(self._hass, 86400, self.refresh_24h)

    async def _update_operating_data(self):
        await self.indego.update_operating_data()
        # dependent state updates
        _LOGGER.info(f"Updating _update_operating_data")
        if self.indego.operating_data:
            self.entities[ENTITY_ONLINE].state = self.indego._online
            #operating data
            self.entities[ENTITY_HMIKEYSN].state = self.indego.operating_data.hmiKeys
            #battery
            self.entities[ENTITY_BATTERY_PRECENT].state = self.indego.operating_data.battery.percent
            self.entities[ENTITY_BATTERY_VOLTAGE].state = self.indego.operating_data.battery.voltage
            self.entities[ENTITY_BATTERY_CYCLES].state = self.indego.operating_data.battery.cycles
            self.entities[ENTITY_BATTERY_DISCHARGE].state = self.indego.operating_data.battery.discharge
            self.entities[ENTITY_BATTERY_AMBIENTE_TEMP].state = self.indego.operating_data.battery.battery_temp
            self.entities[ENTITY_BATTERY_TEMP].state = self.indego.operating_data.battery.ambient_temp
            self.entities[ENTITY_BATTERY_PERCENT_ADJUSTED].state = self.indego.operating_data.battery.percent_adjusted
            #garden
            self.entities[ENTITY_ID].state = self.indego.operating_data.garden.id
            self.entities[ENTITY_GARDEN_NAME].state = self.indego.operating_data.garden.name
            self.entities[ENTITY_SIGNALID].state = self.indego.operating_data.garden.signal_id
            self.entities[ENTITY_SIZE].state = self.indego.operating_data.garden.size
            self.entities[ENTITY_INNERBOUNDS].state = self.indego.operating_data.garden.inner_bounds
            self.entities[ENTITY_BUMPS].state = self.indego.operating_data.garden.bumps
            self.entities[ENTITY_STOPS].state = self.indego.operating_data.garden.stops
            self.entities[ENTITY_GARDEN_LASTMOW].state = self.indego.operating_data.garden.last_mow
            self.entities[ENTITY_MAPCELLSIZE].state = self.indego.operating_data.garden.map_cell_size
        else:
            self.entities[ENTITY_ONLINE].state = self.indego._online

    async def _update_state(self):
        await self.indego.update_state(longpoll=True, longpoll_timeout=300)
        # dependent state updates
        _LOGGER.info(f"Updating _update_state")
        if self._shutdown:
            return
        if self.indego.state:
            self.entities[ENTITY_LAWN_MOWED].state = self.indego.state.mowed
            #State
            self.entities[ENTITY_MOWER_STATE].state = self.indego.state_description
            self.entities[ENTITY_MOWER_STATE_DETAIL].state = self.indego.state_description_detail
            self.entities[ENTITY_STATE].state = self.indego.state.state
            self.entities[ENTITY_MAP_UPDATE_AVAILABLE].state = self.indego.state.map_update_available
            self.entities[ENTITY_MOWMODE].state = self.indego.state.mowmode
            self.entities[ENTITY_XPOS].state = self.indego.state.xPos
            self.entities[ENTITY_YPOS].state = self.indego.state.yPos
            self.entities[ENTITY_MAPSVGCACHETS].state = self.indego.state.mapsvgcache_ts
            self.entities[ENTITY_XSVGPOS].state = self.indego.state.svg_xPos
            self.entities[ENTITY_YSVGPOS].state = self.indego.state.svg_yPos
            self.entities[ENTITY_CONFIG_CHANGE].state = self.indego.state.config_change
            self.entities[ENTITIY_MOW_TRIG].state = self.indego.state.mow_trig
            #Runtime Total
            self.entities[ENTITY_RUNTIME_TOTAL_OPERATION].state = self.indego.state.runtime.total.operate
            self.entities[ENTITY_RUNTIME_TOTAL_MOWING].state = self.indego.state.runtime.total.cut
            self.entities[ENTITY_RUNTIME_TOTAL_CHARGING].state = self.indego.state.runtime.total.charge
            #Runttime Session
            self.entities[ENTITY_RUNTIME_LAST_OPERATION].state = self.indego.state.runtime.session.operate
            self.entities[ENTITY_RUNTIME_LAST_MOWING].state = self.indego.state.runtime.session.cut
            self.entities[ENTITY_RUNTIME_LAST_CHARGING].state = self.indego.state.runtime.session.charge

            self.entities[ENTITY_BATTERY_PERCENT_ADJUSTED].charging = (
                True if self.indego.state_description_detail == "Charging" else False
            )
            try:
                #await _update_position(self.indego.state.svg_xPos,self.indego.state.svg_yPos)
                svg = fromfile(f"www/mapWithoutIndego.svg")
                xpos = self.indego.state.svg_xPos
                ypos = self.indego.state.svg_yPos
                _LOGGER.info(f'Indego position (x,y): {xpos},{ypos}')
                circle = f'<circle cx="{xpos}" cy="{ypos}" r="15" fill="yellow" />'
                mower_circle = fromstring(circle)
                _LOGGER.info(f'Adding mower to map and save new svg...')
                svg.append(mower_circle)
                svg.save(f"www/mapWithIndego.svg")
            except Exception as e:
                _LOGGER.info("Update state got an exception: %s", e)


    async def _update_generic_data(self):
        await self.indego.update_generic_data()
        _LOGGER.info(f"Updating _update_generic_data")
        # dependent state updates
        if self.indego.generic_data:
            #generic data
            self.entities[ENTITY_NAME].state = self.indego.generic_data.alm_name
            self.entities[ENTITY_SERIAL].state = self.indego.generic_data.alm_sn
            self.entities[ENTITY_SERVICECOUNTER].state = self.indego.generic_data.service_counter
            self.entities[ENTITY_NEEDSSERVICE].state = self.indego.generic_data.needs_service
            self.entities[ENTITY_MODELNUMBER].state = self.indego.generic_data.bareToolnumber
            self.entities[ENTITY_FIRMWARE].state = self.indego.generic_data.alm_firmware_version
            self.entities[ENTITY_MODEL_DESCRIPTION].state = self.indego.generic_data.model_description
            self.entities[ENTITY_MOWING_MODE_DESCRIPTION].state = self.indego.generic_data.mowing_mode_description
            #model voltage
            self.entities[ENTITY_MODEL_VOLTAGE_MIN].state = self.indego.generic_data.model_voltage.min
            self.entities[ENTITY_MODEL_VOLTAGE_MAX].state = self.indego.generic_data.model_voltage.max


    async def _update_alerts(self):
        await self.indego.update_alerts()
        # dependent state updates
        if self.indego.alerts:
            self.entities[ENTITY_ALERT].state = self.indego.alerts_count > 0
            self.entities[ENTITY_ALERT_COUNT].state = self.indego.alerts_count
            self.entities[ENTITY_ALERT_ID].state = self.indego.alerts[0].alert_id
            self.entities[ENTITY_ALERT_ERROR_CODE].state = self.indego.alerts[0].error_code
            self.entities[ENTITY_ALERT_HEADLINE].state = self.indego.alerts[0].headline
            self.entities[ENTITY_ALERT_DATE].state = self.indego.alerts[0].date
            self.entities[ENTITY_ALERT_MESSAGE].state = self.indego.alerts[0].message
            self.entities[ENTITY_ALERT_READ_STATUS].state = self.indego.alerts[0].read_status
            self.entities[ENTITY_ALERT_PUSH].state = self.indego.alerts[0].push
            self.entities[ENTITY_ALERT_DESCRIPTION].state = self.indego.alerts[0].alert_description

        else:
            self.entities[ENTITY_ALERT].state = 0
            self.entities[ENTITY_ALERT_COUNT].state = 0
            self.entities[ENTITY_ALERT_ID].state = 0
            self.entities[ENTITY_ALERT_ERROR_CODE].state = 0
            self.entities[ENTITY_ALERT_HEADLINE].state = "Kein Problem"
            self.entities[ENTITY_ALERT_DATE].state = "Kein Problem"
            self.entities[ENTITY_ALERT_MESSAGE].state = "Kein Problem"
            self.entities[ENTITY_ALERT_READ_STATUS].state = False
            self.entities[ENTITY_ALERT_PUSH].state = False
            self.entities[ENTITY_ALERT_DESCRIPTION].state = "Kein Problem"

    async def _update_updates_available(self):
        await self.indego.update_updates_available()
        _LOGGER.info(f"Updating _update_updates_available")
        # dependent state updates
        self.entities[ENTITY_UPDATE_AVAILABLE].state = self.indego.update_available

    
    async def _update_security(self):
        await self.indego.update_security()
        _LOGGER.info(f"Updating _update_securitiy")
        # dependent state updates
        if self.indego.security:
            self.entities[ENTITY_ENABLED].state = self.indego.security.enabled
            self.entities[ENTITY_AUTOLOCK].state = self.indego.security.autolock


    async def _update_setup(self):
        await self.indego.update_setup()
        _LOGGER.info(f"Updating _update_setup")
        # dependent state updates
        if self.indego.setup:
            self.entities[ENTITY_HAS_OWNER].state = self.indego.setup.hasOwner
            self.entities[ENTITY_HAS_PIN].state = self.indego.setup.hasPin
            self.entities[ENTITY_HAS_MAP].state = self.indego.setup.hasMap
            self.entities[ENTITY_HAS_AUTO_CAL].state = self.indego.setup.hasAutoCal
            self.entities[ENTITY_HAS_INTEGRITY_CHECK].state = self.indego.setup.hasIntegrityCheckPassed

    async def _update_user(self):
        await self.indego.update_user()
        _LOGGER.info(f"Updating _update_user")
        # dependent state updates
        if self.indego.user:
            self.entities[ENTITY_EMAIL].state = self.indego.user.email
            self.entities[ENTITY_DISPLAYNAME].state = self.indego.user.display_name
            self.entities[ENTITY_LANGUAGE].state = self.indego.user.language
            self.entities[ENTITY_COUNTRY].state = self.indego.user.country
            self.entities[ENTITY_OPTINAPP].state = self.indego.user.optIn
            self.entities[ENTITY_OPTINAPP].state = self.indego.user.optInApp

    async def _update_network(self):
        await self.indego.update_network()
        _LOGGER.info(f"Updating _update_network")
        # dependent state updates
        if self.indego.network:
            self.entities[ENTITY_RSSI].state = self.indego.network.rssi
            self.entities[ENTITY_CURRMODE].state = self.indego.network.currMode
            self.entities[ENTITY_CONFIGMODE].state = self.indego.network.configMode
            self.entities[ENTITY_STEEREDRSSI].state = self.indego.network.steeredRssi
            self.entities[ENTITY_NETWORKCOUNT].state = self.indego.network.networkCount
            self.entities[ENTITY_NETWORKCOUNT].add_attribute(
                {"networks": self.indego.network.networks,}
            )
            if self.indego.network.mcc == 262:
                self.entities[ENTITY_MCC].state = "Deutschland" 
            if self.indego.network.mcc == 204:
                self.entities[ENTITY_MCC].state = "Niederlande" 
            if self.indego.network.mcc == 208:
                self.entities[ENTITY_MCC].state = "Frankreich" 
            if self.indego.network.mcc == 232:
                self.entities[ENTITY_MCC].state = "Österreich" 
            if self.indego.network.mcc == 238:
                self.entities[ENTITY_MCC].state = "Dänemark" 
            if self.indego.network.mcc == 240:
                self.entities[ENTITY_MCC].state = "Schweden" 
            if self.indego.network.mcc == 242:
                self.entities[ENTITY_MCC].state = "Norwegen" 
            if self.indego.network.mcc == 244:
                self.entities[ENTITY_MCC].state = "Finnland" 

            if self.indego.network.mnc == 1:
                self.entities[ENTITY_MNC].state = "Telekom Deutschland"
            if self.indego.network.mnc == 2:
                self.entities[ENTITY_MNC].state = "Vodafone"
            if self.indego.network.mnc == 3:
                self.entities[ENTITY_MNC].state = "Telefónica"
            if self.indego.network.mnc == 4:
                self.entities[ENTITY_MNC].state = "Vodafone"
            if self.indego.network.mnc == 5:
                self.entities[ENTITY_MNC].state = "Telefónica"
            if self.indego.network.mnc == 6:
                self.entities[ENTITY_MNC].state = "Telekom Deutschland"
            if self.indego.network.mnc == 9:
                self.entities[ENTITY_MNC].state = "Vodafone"

    async def _update_last_completed_mow(self):
        await self.indego.update_last_completed_mow()
        _LOGGER.info(f"Updating _update_last_completed_mow")
        if self.indego.last_completed_mow:
            self.entities[ENTITY_LAST_COMPLETED].state = self.indego.last_completed_mow.isoformat()

    async def _update_next_mow(self):
        await self.indego.update_next_mow()
        _LOGGER.info(f"Updating _update_next_mow")
        if self.indego.next_mow:
            self.entities[ENTITY_NEXT_MOW].state = self.indego.next_mow.isoformat()

    async def _download_map(self, filename: str):
        _LOGGER.debug(f"Downloading map to {filename}")
        await self.indego.download_map(filename)

    async def _update_position(xpos,ypos):
        svg = fromfile(f"www/mapWithoutIndego.svg")
        _LOGGER.info(f'Indego position (x,y): {xpos},{ypos}')
        circle = f'<circle cx="{xpos}" cy="{ypos}" r="15" fill="yellow" />'
        mower_circle = fromstring(circle)
        _LOGGER.info(f'Adding mower to map and save new svg...')
        svg.append(mower_circle)
        svg.save(f"www/mapWithIndego.svg")

        