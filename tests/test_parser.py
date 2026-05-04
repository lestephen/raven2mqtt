from raven2mqtt.parser import RAVEnXmlStreamParser


def test_parser_ignores_mid_stanza_prefix_and_parses_top_level_frame() -> None:
    parser = RAVEnXmlStreamParser()

    frames = parser.feed(
        "MeterMacId>0xABC</MeterMacId>"
        "<InstantaneousDemand>"
        "<DeviceMacId>0xD</DeviceMacId>"
        "<MeterMacId>0xM</MeterMacId>"
        "<Demand>0x000004D2</Demand>"
        "<Multiplier>0x00000001</Multiplier>"
        "<Divisor>0x000003E8</Divisor>"
        "</InstantaneousDemand>"
    )

    assert [frame.tag for frame in frames] == ["InstantaneousDemand"]
    assert frames[0].payload["Demand"] == "0x000004D2"


def test_parser_handles_split_and_concatenated_frames() -> None:
    parser = RAVEnXmlStreamParser()

    assert parser.feed("<CurrentSummationDelivered><SummationDelivered>0x0") == []
    frames = parser.feed(
        "00000A</SummationDelivered><SummationReceived>0x00000002</SummationReceived>"
        "<Multiplier>0x00000001</Multiplier><Divisor>0x00000002</Divisor>"
        "</CurrentSummationDelivered>"
        "<NetworkInfo><Status>Connected</Status><LinkStrength>0x64</LinkStrength></NetworkInfo>"
    )

    assert [frame.tag for frame in frames] == [
        "CurrentSummationDelivered",
        "NetworkInfo",
    ]


def test_parser_recovers_after_malformed_top_level_frame() -> None:
    parser = RAVEnXmlStreamParser()

    frames = parser.feed(
        "<InstantaneousDemand><Demand>0x1</InstantaneousDemand>"
        "<NetworkInfo><Status>Connected</Status></NetworkInfo>"
    )

    assert [frame.tag for frame in frames] == ["NetworkInfo"]
