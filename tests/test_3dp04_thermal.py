from __future__ import annotations

import re
import unittest
from pathlib import Path

import jinja2


REPO_ROOT = Path(__file__).resolve().parents[1]
THERMAL = (REPO_ROOT / "printer-config" / "3dp-04" / "thermal-management.cfg").read_text(encoding="utf-8")
HOOKS = (REPO_ROOT / "printer-config" / "3dp-04" / "lifecycle-hooks.cfg").read_text(encoding="utf-8")
ENVIRONMENT = jinja2.Environment(
    block_start_string="{%", block_end_string="%}",
    variable_start_string="{", variable_end_string="}",
)


def section(name: str) -> str:
    body = THERMAL.split(f"[{name}]", 1)[1]
    return re.split(r"^\[", body, maxsplit=1, flags=re.M)[0]


def macro_gcode(name: str) -> str:
    return section(f"gcode_macro {name}").split("gcode:\n", 1)[1]


def render_soak(material: str, chamber: float, average: float, **params: object) -> list[str]:
    printer = {
        "gcode_macro START_PRINT": {
            "material": material, "bed_temp": 105, "chamber_temp": chamber,
        },
        "gcode_macro _USER_VARIABLES": {
            "material_soak_minutes": {"PLA": 0, "PETG": 0, "ABS": 8, "ASA": 8, "TPU": 0},
            "smart_soak_chamber_margin": 5,
            "status_leds_control_enabled": False,
            "filter_enabled": True,
            "travel_speed": 350,
        },
        "temp_tracker chamber_soak": {"average": average},
        "toolhead": {"axis_maximum": {"x": 300, "y": 300}},
    }
    rendered = ENVIRONMENT.from_string(macro_gcode("_START_PRINT_ACTION_SMART_BED_SOAK")).render(
        printer=printer, params=params,
    )
    return [line.strip() for line in rendered.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


class ThermalManagementTest(unittest.TestCase):
    def test_material_policy_skips_timed_soak_for_open_materials(self) -> None:
        for material in ("PLA", "PETG", "TPU"):
            with self.subTest(material=material):
                output = render_soak(material, chamber=0, average=25)
                self.assertIn(f"RESPOND MSG=\"Smart soak: {material} does not require a timed soak\"", output)
                self.assertEqual("HEATSOAK_BED TEMP=105.0 SOAKTIME=0", output[-1])
                self.assertFalse(any(line.startswith("G0 ") for line in output))

    def test_cold_abs_and_asa_get_configured_soak(self) -> None:
        for material in ("ABS", "ASA"):
            with self.subTest(material=material):
                output = render_soak(material, chamber=50, average=35)
                self.assertIn("START_FILTER SPEED=1", output)
                self.assertIn("G0 X150.0 Y100.0 Z50 F21000.0", output)
                self.assertEqual("HEATSOAK_BED TEMP=105.0 SOAKTIME=8", output[-1])

    def test_recent_average_tracks_requested_chamber_target(self) -> None:
        for chamber, average in ((50, 45), (40, 35)):
            with self.subTest(chamber=chamber):
                output = render_soak("ABS", chamber=chamber, average=average)
                self.assertIn("timed soak skipped", output[0])
                self.assertEqual("HEATSOAK_BED TEMP=105.0 SOAKTIME=0", output[-1])

    def test_explicit_soak_and_force_controls_take_precedence(self) -> None:
        self.assertEqual(
            "HEATSOAK_BED TEMP=105.0 SOAKTIME=0",
            render_soak("ABS", chamber=50, average=20, SOAK=0)[-1],
        )
        self.assertEqual(
            "HEATSOAK_BED TEMP=105.0 SOAKTIME=12",
            render_soak("ABS", chamber=50, average=50, SOAK=12, FORCE_SOAK=1)[-1],
        )

    def test_native_controller_fan_has_five_minute_cooldown(self) -> None:
        fan = section("controller_fan electronics_fan")
        self.assertRegex(fan, r"(?m)^idle_timeout: 300$")
        self.assertRegex(fan, r"(?m)^idle_speed: 0\.3$")
        self.assertIn("heater: heater_bed, extruder", fan)
        for stepper in ("stepper_x", "stepper_y", "stepper_z3", "extruder"):
            self.assertIn(stepper, fan)

    def test_rpi_policy_uses_quiet_idle_and_active_targets(self) -> None:
        rpi = section("temperature_fan rpi_fan")
        self.assertRegex(rpi, r"(?m)^max_speed: 0\.60$")
        self.assertRegex(rpi, r"(?m)^target_temp: 55$")
        self.assertRegex(rpi, r"(?m)^max_delta: 3$")
        self.assertIn("TARGET=47 MAX_SPEED=0.60", macro_gcode("_START_PRINT_PRE_ACTION_SET_ACTIVE_THERMALS"))
        self.assertEqual(2, THERMAL.count("TARGET=55 MAX_SPEED=0.60"))

    def test_lifecycle_references_each_thermal_action(self) -> None:
        for action in ("smart_bed_soak", "set_active_thermals", "set_idle_thermals"):
            self.assertIn(action, HOOKS)


if __name__ == "__main__":
    unittest.main()
