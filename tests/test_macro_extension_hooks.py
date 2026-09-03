from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

import jinja2


REPO_ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT = jinja2.Environment(
    block_start_string="{%", block_end_string="%}",
    variable_start_string="{", variable_end_string="}",
)


def macro_text(name: str) -> str:
    return (REPO_ROOT / "macros" / "base" / f"{name.lower()}.cfg").read_text(encoding="utf-8")


def macro_gcode(name: str) -> str:
    section = macro_text(name).split(f"[gcode_macro {name}]", 1)[1]
    section = re.split(r"^\[", section, maxsplit=1, flags=re.M)[0]
    return section.split("gcode:\n", 1)[1]


def raise_error(message: str) -> None:
    raise ValueError(message)


def render(name: str, *, variables=None, homed="xyz", commands=(), rawparams="") -> list[str]:
    user = dict.fromkeys([
        "verbose", "light_enabled", "status_leds_control_enabled",
        "force_homing_in_start_print", "klippain_mmu_enabled",
        "firmware_retraction_enabled", "filter_enabled", "filament_sensor_enabled",
        "part_fan_tach_enabled", "hotend_fan_tach_enabled", "mmu_unload_on_cancel_print",
        "turn_off_heaters_in_end_print",
    ], False)
    user.update({
        "klippain_startup_succeeded": True,
        "bed_mesh_enabled": True,
        "print_default_bed_temp": 60,
        "print_default_extruder_temp": 200,
        "print_default_soak": 0,
        "print_default_chamber_temp": 0,
        "print_default_chamber_max_heating_time": 0,
        "print_default_material": "PLA",
        "safe_extruder_temp": 150,
        "material_parameters": {"PLA": {"pressure_advance": 0, "additional_z_offset": 0}},
        "startprint_actions": ("primeline",),
    })
    # Read actual defaults rather than duplicating them in the fixture.
    for text in (macro_text("START_PRINT"), macro_text("END_PRINT"), macro_text("CANCEL_PRINT")):
        for key, value in re.findall(r"^variable_(\w*actions):\s*(.+)$", text, re.M):
            user[key] = ast.literal_eval(value)
    user.update(variables or {})
    printer = {
        "gcode_macro _USER_VARIABLES": user,
        "gcode": {"commands": commands},
        "toolhead": {"homed_axes": homed},
        "extruder": {"can_extrude": False},
    }
    rendered = ENVIRONMENT.from_string(macro_gcode(name)).render(
        printer=printer, params={}, rawparams=rawparams, action_raise_error=raise_error,
    )
    return [line.strip() for line in rendered.splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


class MacroExtensionHookTest(unittest.TestCase):
    def test_default_end_sequence_is_unchanged(self) -> None:
        self.assertEqual(render("END_PRINT"), [
            "PARK", "M400", "BED_MESH_CLEAR", "_MODULE_RETRACT_FILAMENT",
            "_MODULE_TURN_OFF_HEATERS", "_MODULE_TURN_OFF_FANS",
            "_MODULE_TURN_OFF_MOTORS", "_MODULE_RESET_LIMITS",
            "SET_PAUSE_NEXT_LAYER ENABLE=0", "SET_PAUSE_AT_LAYER ENABLE=0 LAYER=0",
        ])

    def test_end_actions_can_place_custom_behavior_before_park(self) -> None:
        command = "_END_PRINT_ACTION_CLEAR_SKEW"
        result = render("END_PRINT", variables={"endprint_actions": (
            "clear_skew", "park", "wait_moves", "clear_bed_mesh", "reset_limits", "finalize",
        )}, commands=(command,), rawparams="FILTER_TIME=20")
        self.assertEqual(result, [
            command + " FILTER_TIME=20", "PARK", "M400", "BED_MESH_CLEAR",
            "_MODULE_RESET_LIMITS", "SET_PAUSE_NEXT_LAYER ENABLE=0",
            "SET_PAUSE_AT_LAYER ENABLE=0 LAYER=0",
        ])

    def test_start_hook_precedes_core_setup_and_both_homing_paths(self) -> None:
        command = "_START_PRINT_PRE_ACTION_PREPARE"
        for force_homing, home in ((False, "_CG28"), (True, "G28")):
            with self.subTest(force_homing=force_homing):
                result = render("START_PRINT", commands=(command,), rawparams="BED_TEMP=60",
                                variables={"startprint_pre_actions": ["prepare"],
                                           "force_homing_in_start_print": force_homing})
                self.assertLess(result.index(command + " BED_TEMP=60"), result.index("CLEAR_PAUSE"))
                self.assertLess(result.index(command + " BED_TEMP=60"), result.index(home))
                self.assertLess(result.index(home), result.index("_MODULE_PRIMELINE"))

    def test_default_cancel_sequence_is_unchanged(self) -> None:
        self.assertEqual(render("CANCEL_PRINT"), [
            "PARK", "SET_HEATER_TEMPERATURE HEATER=extruder TARGET=150.0", "M107",
            "M400", "CLEAR_PAUSE", "BED_MESH_CLEAR", "SDCARD_RESET_FILE",
            "SET_PAUSE_NEXT_LAYER ENABLE=0", "SET_PAUSE_AT_LAYER ENABLE=0 LAYER=0",
            "BASE_CANCEL_PRINT",
        ])

    def test_cancel_actions_can_place_custom_behavior_before_conditional_park(self) -> None:
        command = "_CANCEL_PRINT_ACTION_CLEAR_SKEW"
        for homed in ("xyz", "xy", ""):
            with self.subTest(homed=homed):
                result = render("CANCEL_PRINT", homed=homed, commands=(command,),
                                rawparams="FILTER_TIME=20",
                                variables={"cancelprint_actions": (
                                    "clear_skew", "park", "finalize", "base_cancel",
                                )})
                self.assertEqual(result[0], command + " FILTER_TIME=20")
                self.assertEqual("PARK" in result, homed == "xyz")
                self.assertEqual(result[-1], "BASE_CANCEL_PRINT")

    def test_unknown_actions_fail_before_rendering_commands(self) -> None:
        for name, variable in (
            ("START_PRINT", "startprint_pre_actions"),
            ("END_PRINT", "endprint_actions"),
            ("CANCEL_PRINT", "cancelprint_actions"),
        ):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "Unknown"):
                render(name, variables={variable: ["missing"]})

    def test_missing_or_empty_start_pre_actions_preserve_default_output(self) -> None:
        default = render("START_PRINT")
        for value in ([], (), jinja2.Undefined()):
            with self.subTest(value=value):
                self.assertEqual(default, render("START_PRINT", variables={"startprint_pre_actions": value}))


if __name__ == "__main__":
    unittest.main()
