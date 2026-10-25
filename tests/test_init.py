"""Setup, the gate cover, buttons and sensors."""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.button import SERVICE_PRESS
from homeassistant.components.cover import (
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    CoverState,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.gremote.api import (
    DeviceOfflineError,
    GRemoteError,
    InvalidCredentialsError,
)

from .conftest import KEEP_OPEN, OPEN, OPENING

GATE = "cover.gate"


async def _states(hass: HomeAssistant, client: AsyncMock, states: list[int]) -> None:
    client.io_states.return_value = list(states)
    await hass.config_entries.async_entries("gremote")[0].runtime_data.async_refresh()
    await hass.async_block_till_done()


async def _cover(hass: HomeAssistant, service: str) -> None:
    await hass.services.async_call(COVER_DOMAIN, service, {ATTR_ENTITY_ID: GATE}, blocking=True)


async def test_entities(hass: HomeAssistant, setup_integration: MockConfigEntry) -> None:
    assert setup_integration.state is ConfigEntryState.LOADED
    assert hass.states.get(GATE).state == CoverState.CLOSED
    assert hass.states.get(GATE).attributes["device_class"] == "gate"
    assert hass.states.get("button.gate_pedestrian")
    assert hass.states.get("button.gate_keep_open")
    assert not hass.states.get("button.gate_open")  # the cover runs output 1
    assert hass.states.get("binary_sensor.gate_keep_open_output").state == STATE_OFF
    assert hass.states.get("binary_sensor.gate_connectivity").state == STATE_ON
    assert hass.states.get("sensor.gate_voltage").state == "27.4"
    assert hass.states.get("sensor.gate_call_tokens_remaining").state == "40"


@pytest.mark.parametrize(
    ("states", "service", "pulsed"),
    [
        (None, SERVICE_OPEN_COVER, True),
        (None, SERVICE_CLOSE_COVER, False),
        (OPEN, SERVICE_CLOSE_COVER, True),
        (OPEN, SERVICE_OPEN_COVER, False),
    ],
)
async def test_cover_only_pulses_when_needed(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    client: AsyncMock,
    states: list[int] | None,
    service: str,
    pulsed: bool,
) -> None:
    if states:
        await _states(hass, client, states)
    await _cover(hass, service)
    if pulsed:
        client.trigger.assert_awaited_once_with(1)
    else:
        client.trigger.assert_not_awaited()


async def test_cover_refuses_while_moving(
    hass: HomeAssistant, setup_integration: MockConfigEntry, client: AsyncMock
) -> None:
    await _states(hass, client, OPENING)
    assert hass.states.get(GATE).state == CoverState.OPENING
    with pytest.raises(HomeAssistantError, match="moving"):
        await _cover(hass, SERVICE_CLOSE_COVER)
    await _cover(hass, SERVICE_OPEN_COVER)  # already on its way
    client.trigger.assert_not_awaited()


async def test_trigger_polls_fast_then_settles(
    hass: HomeAssistant,
    setup_integration: MockConfigEntry,
    client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    coordinator = setup_integration.runtime_data
    await _cover(hass, SERVICE_OPEN_COVER)
    assert coordinator.update_interval == timedelta(seconds=3)
    client.io_states.return_value = list(OPEN)
    freezer.tick(timedelta(seconds=4))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(GATE).state == CoverState.OPEN
    freezer.tick(timedelta(seconds=90))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_button_and_output_state(
    hass: HomeAssistant, setup_integration: MockConfigEntry, client: AsyncMock
) -> None:
    await hass.services.async_call(
        "button", SERVICE_PRESS, {ATTR_ENTITY_ID: "button.gate_pedestrian"}, blocking=True
    )
    client.trigger.assert_awaited_once_with(2)
    await _states(hass, client, KEEP_OPEN)
    assert hass.states.get("binary_sensor.gate_keep_open_output").state == STATE_ON


async def test_trigger_failure_is_reported(
    hass: HomeAssistant, setup_integration: MockConfigEntry, client: AsyncMock
) -> None:
    client.trigger.side_effect = GRemoteError("boom")
    with pytest.raises(HomeAssistantError, match="Could not reach the gate"):
        await _cover(hass, SERVICE_OPEN_COVER)


async def test_offline(
    hass: HomeAssistant, setup_integration: MockConfigEntry, client: AsyncMock
) -> None:
    client.io_states.side_effect = DeviceOfflineError("Device is Offline")
    await setup_integration.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(GATE).state == STATE_UNAVAILABLE
    assert hass.states.get("button.gate_pedestrian").state == STATE_UNAVAILABLE
    assert hass.states.get("binary_sensor.gate_connectivity").state == STATE_OFF


async def test_cannot_connect_retries(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: AsyncMock
) -> None:
    client.io_states.side_effect = GRemoteError("down")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_bad_token_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: AsyncMock
) -> None:
    client.status.side_effect = InvalidCredentialsError("nope")
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [f["context"]["source"] for f in flows] == ["reauth"]
