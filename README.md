# G-Remote for Home Assistant

Control a Centurion gate motor fitted with a **G-ULTRA** or **G-SPEAK** GSM module
from Home Assistant, through the same G-Web cloud API (`www.gweb.co.za`) that the
G-Remote and MyCentsys Remote apps use.

Unofficial; not affiliated with Centurion Systems. The CENTURION name and logo are
trademarks of Centurion Systems, used here only to identify the hardware.

## What you get

| Entity | What it does |
| --- | --- |
| `cover.gate` | Open and close the gate, with its live position (open, opening, closing, closed) when the module has a gate-status input wired. |
| A button per other output | e.g. **Pedestrian** and **Keep Open**, named as in the app. |
| A binary sensor per output | Whether that output is on, e.g. Keep Open holding the gate. |
| Connectivity | Whether the module is connected to G-Web. |
| Diagnostics | Supply voltage, signal, call/SMS tokens remaining, connection type, last sync. |

### How the gate cover behaves

The module runs the gate with one output that pulses the motor, like a remote's
button: each pulse sends the gate the other way, or stops it mid-travel. So the
cover only pulses when that gets the gate where you asked:

- **Open** does nothing if the gate is open or opening; **Close** does nothing if
  it is closed or closing.
- While the gate is moving the other way, the cover refuses rather than pulse,
  because a pulse would stop the gate instead of reversing it.
- Without a gate-status input the position is unknown, so both buttons always pulse.

After any press the integration polls every 3 seconds for 90 seconds so the
position follows the gate; otherwise it polls every 30 seconds. Diagnostics are
read every 15 minutes; G-Web caches those, so check *Last synced*.

## Installation

HACS → ⋮ → **Custom repositories** → add `https://github.com/timothyanderson82/ha-gremote`
as an **Integration**, install **G-Remote** and restart Home Assistant. Or copy
`custom_components/gremote` into your configuration's `custom_components` folder.

## Setup

**Settings → Devices & services → Add integration → G-Remote**, then paste a
G-Web URL for your module, for example

```
https://www.gweb.co.za/api/MCRStatus?data=<base64>%7C<base64>%7C<base64>
```

Any `MCRStatus` or `MCRActEn` URL the app calls works; its `data` parameter
holds the device ID and your account's G-Web token. If you already drive the
gate from Node-RED, copy the URL from your status request node. The URL is a
credential: anyone with it can open your gate, so don't share it.

If G-Web stops accepting the token, Home Assistant asks you to paste a new URL.

## Development

```
uv venv .venv --python 3.14
uv pip install --python .venv "homeassistant==2026.10.4" pytest-homeassistant-custom-component ruff
.venv/bin/pytest -q
```

Tests never contact G-Web.
