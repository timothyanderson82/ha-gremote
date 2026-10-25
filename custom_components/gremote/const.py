"""Constants for the G-Remote integration."""

from datetime import timedelta

DOMAIN = "gremote"

CONF_DEVICE_ID = "device_id"
CONF_TOKEN = "token"
CONF_URL = "url"

# Live IO states are cheap to read; diagnostics are cached by G-Web anyway.
POLL_INTERVAL = timedelta(seconds=30)
STATUS_INTERVAL = timedelta(minutes=15)
# Poll quickly while the gate moves after a trigger.
FAST_POLL_INTERVAL = timedelta(seconds=3)
FAST_POLL_DURATION = timedelta(seconds=90)

MANUFACTURER = "Centurion Systems"
