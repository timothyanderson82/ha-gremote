"""Client for the G-Web cloud API used by Centurion G-ULTRA / G-SPEAK gate modules.

The phone apps address a module with a ``data`` query parameter made of
base64 parts joined by ``|``: the device ID, the account's G-Web token and an
IO number (an output to pulse, or ``1`` for a status read).
"""

from __future__ import annotations

import base64
import contextlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

import aiohttp
from yarl import URL

BASE_URL = "https://www.gweb.co.za"
USER_AGENT = "MyCentsysRemote/1.1.0.98 CFNetwork/1496.0.7 Darwin/23.5.0"
TIMEOUT = aiohttp.ClientTimeout(total=20)

# G-Web runs on South African time and reports naive timestamps.
GWEB_TZ = ZoneInfo("Africa/Johannesburg")

EP_IO_STATES = "/api/AppIOStatesEN"  # live IO states, addressed by device ID only
EP_STATUS = "/api/MCRStatus"  # last-known diagnostics and IO names
EP_TRIGGER = "/api/MCRActEn"  # pulse an output

# State codes reported by a status-feedback input. Unused IOs also report 48,
# so it only means "opening" on the IO that carries the gate status.
GATE_STATES = {48: "opening", 49: "open", 50: "closing", 51: "closed", 52: "running"}
# Outputs report 88-99: even is on, odd is off.
OUTPUT_STATES = range(88, 100)

TRIGGER_OK = "Activation Queued Successfully"
OFFLINE = "Device is Offline"


class GRemoteError(Exception):
    """The G-Web API could not be reached or returned something unexpected."""


class DeviceOfflineError(GRemoteError):
    """The module is not connected to G-Web."""


class InvalidCredentialsError(GRemoteError):
    """G-Web did not accept the device ID and token."""


@dataclass(frozen=True)
class IO:
    """One of the module's IOs, numbered from 1 as in the app."""

    number: int
    name: str
    direction: str  # "Output", "Input" or "NA"

    @property
    def is_output(self) -> bool:
        return self.direction.lower() == "output"

    @property
    def is_input(self) -> bool:
        return self.direction.lower() == "input"


@dataclass
class Status:
    """Diagnostics from MCRStatus; G-Web caches these, see ``last_synced``."""

    online: bool
    ios: list[IO] = field(default_factory=list)
    voltage: float | None = None
    signal: int | None = None
    firmware: str | None = None
    connection_type: str | None = None
    calls_remaining: int | None = None
    sms_remaining: int | None = None
    last_synced: datetime | None = None

    @property
    def gate_io(self) -> IO | None:
        """The output that runs the gate: the one named "Open", else the first."""
        outputs = [io for io in self.ios if io.is_output]
        named = [io for io in outputs if io.name.lower() == "open"]
        return (named or outputs or [None])[0]

    @property
    def feedback_io(self) -> IO | None:
        """The input wired to the gate's status feedback, if there is one."""
        inputs = [io for io in self.ios if io.is_input]
        named = [io for io in inputs if "status" in io.name.lower()]
        return (named or inputs or [None])[0]


def encode_data(*values: object) -> str:
    """Build a ``data`` parameter the way the apps do."""
    return "%7C".join(base64.b64encode(str(v).encode()).decode() for v in values)


def parse_url(url: str) -> tuple[int, str]:
    """Return (device ID, token) from any G-Web app URL, e.g. an MCRStatus one."""
    query = urlsplit(url.strip()).query
    # Not parse_qs: it would turn the base64 "+" into a space
    raw = next((unquote(p[5:]) for p in query.split("&") if p.startswith("data=")), "")
    if not raw:
        raise ValueError("no data parameter")
    parts = raw.split("|")
    if len(parts) != 3:
        raise ValueError("data parameter does not have three parts")
    try:
        device_id, token = (base64.b64decode(p, validate=True).decode() for p in parts[:2])
    except ValueError as err:
        raise ValueError("data parameter is not base64") from err
    if not device_id.isdigit() or not token:
        raise ValueError("data parameter does not hold a device ID and token")
    return int(device_id), token


def _unwrap(text: str) -> Any:
    """Decode a body that is JSON, or JSON encoded again as a JSON string."""
    try:
        value = json.loads(text)
        if isinstance(value, str):
            try:
                return json.loads(value)
            except ValueError:
                return value
        return value
    except ValueError:
        return text.strip().strip('"')


def _number(value: Any, kind: type[int] | type[float]) -> int | float | None:
    try:
        return kind(str(value).replace(",", ".").strip())
    except (TypeError, ValueError):
        return None


def parse_status(body: Any) -> Status:
    """Turn an MCRStatus body into a Status."""
    if body == OFFLINE:
        return Status(online=False)
    if not isinstance(body, dict):
        raise InvalidCredentialsError(f"unexpected status reply: {str(body)[:80]!r}")

    # "Open:Off,Pedestrian:Off,Keep Open:Off,Gate Status:Closed,NA:NA,NA:NA"
    names = [s.rpartition(":")[0].strip() for s in str(body.get("IOstates", "")).split(",")]
    # "Output, Output, Output, Input, NA,NA"
    directions = [s.strip() for s in str(body.get("IODirections", "")).split(",")]
    ios = [
        IO(number, name, direction)
        for number, (name, direction) in enumerate(zip(names, directions, strict=False), 1)
        if name and name != "NA" and direction != "NA"
    ]

    # "Tokens Remaining Call: 40 SMS: 0"
    airtime = str(body.get("Airtime", ""))
    calls = re.search(r"Call:\s*(\d+)", airtime)
    sms = re.search(r"SMS:\s*(\d+)", airtime)

    synced = None
    if body.get("LastSynced"):
        with contextlib.suppress(ValueError):
            synced = datetime.strptime(body["LastSynced"], "%Y/%m/%d %H:%M:%S").replace(
                tzinfo=GWEB_TZ
            )

    return Status(
        online=str(body.get("OnlineStatus", "")).lower() == "active",
        ios=ios,
        voltage=_number(body.get("Voltage"), float),
        signal=_number(body.get("Signal"), int),
        firmware=body.get("Firmware") or None,
        connection_type=body.get("ConnectionType") or None,
        calls_remaining=int(calls[1]) if calls else None,
        sms_remaining=int(sms[1]) if sms else None,
        last_synced=synced,
    )


def gate_state(states: list[int], feedback: IO | None) -> str | None:
    """The gate position reported by the feedback input, or None if unknown."""
    if feedback is None or feedback.number > len(states):
        return None
    return GATE_STATES.get(states[feedback.number - 1])


def output_is_on(states: list[int], io: IO) -> bool | None:
    """Whether an output is on, or None if it does not report on/off."""
    if io.number > len(states) or states[io.number - 1] not in OUTPUT_STATES:
        return None
    return states[io.number - 1] % 2 == 0


class GRemoteClient:
    """Talks to G-Web for one module."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        device_id: int,
        token: str,
        base_url: str = BASE_URL,
    ) -> None:
        self._session = session
        self.device_id = device_id
        self._token = token
        self._base_url = base_url

    async def _get(self, endpoint: str, data: str) -> Any:
        # encoded=True keeps the base64 "+", "/" and "=" exactly as the apps send them
        url = URL(f"{self._base_url}{endpoint}?data={data}", encoded=True)
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
                timeout=TIMEOUT,
            ) as response:
                text = await response.text()
                if response.status >= 400:
                    raise GRemoteError(f"{endpoint} returned HTTP {response.status}")
        except (aiohttp.ClientError, TimeoutError) as err:
            raise GRemoteError(f"{endpoint} failed: {err!r}") from err
        return _unwrap(text)

    async def io_states(self) -> list[int]:
        """Live state code of every IO, in IO order."""
        body = await self._get(EP_IO_STATES, encode_data(self.device_id))
        if body == OFFLINE:
            raise DeviceOfflineError(OFFLINE)
        if not isinstance(body, dict) or not isinstance(body.get("IOList"), list):
            raise GRemoteError(f"unexpected IO states reply: {str(body)[:80]!r}")
        return [_number(io.get("IOStateID"), int) or 0 for io in body["IOList"]]

    async def status(self) -> Status:
        """Diagnostics and IO names. These are cached by G-Web, not live."""
        return parse_status(await self._get(EP_STATUS, encode_data(self.device_id, self._token, 1)))

    async def trigger(self, io_number: int) -> None:
        """Pulse an output, as pressing its button in the app does."""
        result = await self._get(EP_TRIGGER, encode_data(self.device_id, self._token, io_number))
        if result == TRIGGER_OK:
            return
        if result == OFFLINE:
            raise DeviceOfflineError(OFFLINE)
        raise GRemoteError(f"G-Web refused the trigger: {str(result)[:80]!r}")
