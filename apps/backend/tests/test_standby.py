"""6.4: the standby killer: chosen plugs off overnight or when away, and only those back on."""

from __future__ import annotations

from app.standby import service


def test_suggests_the_plug_behind_an_always_on_sensor():
    found = service.suggestions([{"entity_id": "sensor.tv_plug_power", "name": "TV plug power", "watts": 22},
                                 {"entity_id": "sensor.rack_power", "name": "Rack", "watts": 120}], ["switch.tv_plug", "switch.lamp"])
    assert found == [{"sensor": "sensor.tv_plug_power", "name": "TV plug power", "watts": 22, "switch": "switch.tv_plug"}]
    assert service.switch_for("sensor.desk_current_consumption") == "switch.desk"


def test_off_at_night_back_on_in_the_morning_and_only_what_it_turned_off():
    doc = {"switches": ["switch.tv_plug", "switch.printer"], "off_by_us": [], "period": "day"}
    off, on, period = service.plan(doc, {"switch.tv_plug": "on", "switch.printer": "off"}, night=True, away=None)
    assert (off, on, period) == (["switch.tv_plug"], [], "night")  # the printer was already off: not ours
    doc.update(off_by_us=["switch.tv_plug"], period="night")
    # Switched back on by hand in the night: not fought.
    assert service.plan(doc, {"switch.tv_plug": "on"}, night=True, away=None)[0] == []
    off, on, period = service.plan(doc, {"switch.tv_plug": "off", "switch.printer": "off"}, night=False, away=False)
    assert (off, on, period) == ([], ["switch.tv_plug"], "day")
    # Nobody home in the day counts like the night.
    assert service.plan({**doc, "period": "day"}, {"switch.tv_plug": "on"}, night=False, away=True)[2] == "away"


def test_hours_wrap_past_midnight():
    assert service.in_hours(23, (22, 6)) and service.in_hours(3, (22, 6)) and not service.in_hours(12, (22, 6))
    assert service.in_hours(2, (1, 6)) and not service.in_hours(6, (1, 6))
