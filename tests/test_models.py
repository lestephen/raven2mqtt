from raven2mqtt.models import RavenState


def test_state_normalizes_scaled_values() -> None:
    state = RavenState()

    changed = state.update(
        "InstantaneousDemand",
        {
            "Demand": "0x000004D2",
            "Multiplier": "0x00000001",
            "Divisor": "0x000003E8",
            "MeterMacId": "0xABC",
        },
    )

    assert changed
    assert state.as_dict()["power_kw"] == 1.234
    assert state.as_dict()["meter_mac_id"] == "0xABC"


def test_state_decodes_signed_instantaneous_demand() -> None:
    state = RavenState()

    state.update(
        "InstantaneousDemand",
        {
            "Demand": "0xFFFFFF9C",
            "Multiplier": "0x00000001",
            "Divisor": "0x00000064",
        },
    )

    assert state.as_dict()["power_kw"] == -1.0


def test_update_returns_false_when_values_unchanged() -> None:
    state = RavenState()
    payload = {
        "Demand": "0x000004D2",
        "Multiplier": "0x00000001",
        "Divisor": "0x000003E8",
        "MeterMacId": "0xABC",
        "DeviceMacId": "0xDEF",
    }

    assert state.update("InstantaneousDemand", payload) is True
    assert state.update("InstantaneousDemand", payload) is False


def test_update_returns_true_when_only_mac_changes() -> None:
    state = RavenState()
    state.update("InstantaneousDemand", {"Demand": "0x1", "Multiplier": "0x1", "Divisor": "0x1"})

    changed = state.update(
        "InstantaneousDemand",
        {"Demand": "0x1", "Multiplier": "0x1", "Divisor": "0x1", "MeterMacId": "0xABC"},
    )

    assert changed is True
    assert state.meter_mac_id == "0xABC"
