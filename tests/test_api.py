"""The G-Web client and parsers, without Home Assistant."""

import base64
from urllib.parse import quote

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker
from yarl import URL

from custom_components.gremote import api

from .conftest import CLOSED, DEVICE_ID, PULSING, RUNNING, STATUS_BODY, TOKEN, URL as STATUS_URL


def test_parse_url_round_trip() -> None:
    assert api.parse_url(STATUS_URL) == (DEVICE_ID, TOKEN)


def test_parse_url_keeps_plus_and_accepts_raw_pipes() -> None:
    raw = "|".join(base64.b64encode(str(v).encode()).decode() for v in (DEVICE_ID, TOKEN, 1))
    assert "+" in raw
    assert api.parse_url(f" https://www.gweb.co.za/api/MCRActEn?data={raw} ") == (
        DEVICE_ID,
        TOKEN,
    )
    assert api.parse_url(f"https://x/api/MCRStatus?data={quote(raw, safe='')}") == (
        DEVICE_ID,
        TOKEN,
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.gweb.co.za/api/MCRStatus",
        "https://www.gweb.co.za/api/MCRStatus?data=bm90IGEgbnVtYmVy%7CdA==%7CMQ==",
        "https://www.gweb.co.za/api/MCRStatus?data=MTIzNDU=",
        "https://www.gweb.co.za/api/MCRStatus?data=!!!%7C!!!%7C!!!",
    ],
)
def test_parse_url_rejects(url: str) -> None:
    with pytest.raises(ValueError):
        api.parse_url(url)


def test_parse_status() -> None:
    status = api.parse_status(STATUS_BODY)
    assert status.online
    assert [(io.number, io.name, io.direction) for io in status.ios] == [
        (1, "Open", "Output"),
        (2, "Pedestrian", "Output"),
        (3, "Keep Open", "Output"),
        (4, "Gate Status", "Input"),
    ]
    assert status.gate_io.number == 1
    assert status.feedback_io.number == 4
    assert status.voltage == 27.4
    assert status.signal == 2
    assert (status.calls_remaining, status.sms_remaining) == (40, 0)
    assert status.last_synced.isoformat() == "2026-10-23T06:32:03+02:00"


def test_parse_status_offline_and_garbage() -> None:
    assert not api.parse_status(api.OFFLINE).online
    with pytest.raises(api.InvalidCredentialsError):
        api.parse_status("Invalid Request")


def test_states() -> None:
    feedback = api.parse_status(STATUS_BODY).feedback_io
    assert api.gate_state(CLOSED, feedback) == "closed"
    assert api.gate_state(RUNNING, feedback) == "running"
    assert api.gate_state(CLOSED, None) is None
    open_io, pedestrian = api.parse_status(STATUS_BODY).ios[:2]
    assert api.output_is_on(PULSING, open_io) is True
    assert api.output_is_on(PULSING, pedestrian) is False
    assert api.output_is_on([48], open_io) is None


async def test_client_requests(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    base = "https://gweb.test"
    io_url = URL(f"{base}/api/AppIOStatesEN?data={api.encode_data(DEVICE_ID)}", encoded=True)
    aioclient_mock.get(
        io_url,
        text='"{\\"DeviceId\\":12345,\\"IOList\\":[{\\"IOStateID\\":89},{\\"IOStateID\\":51}]}"',
    )
    aioclient_mock.get(
        URL(f"{base}/api/MCRActEn?data={api.encode_data(DEVICE_ID, TOKEN, 2)}", encoded=True),
        text='"Activation Queued Successfully"',
    )
    aioclient_mock.get(
        URL(f"{base}/api/MCRActEn?data={api.encode_data(DEVICE_ID, TOKEN, 1)}", encoded=True),
        text='"Device is Offline"',
    )
    client = api.GRemoteClient(async_get_clientsession(hass), DEVICE_ID, TOKEN, base)
    assert await client.io_states() == [89, 51]
    await client.trigger(2)
    with pytest.raises(api.DeviceOfflineError):
        await client.trigger(1)
    # The base64 must reach G-Web as the apps send it: "+" and "=" unescaped
    sent = str(aioclient_mock.mock_calls[1][1])
    assert "+" in sent and "=%7C" in sent

    aioclient_mock.clear_requests()
    aioclient_mock.get(io_url, status=500)
    with pytest.raises(api.GRemoteError):
        await client.io_states()
