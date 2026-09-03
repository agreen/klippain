from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (REPO_ROOT / "printer-config" / "3dp-04" / "klippain-overrides.cfg").read_text(encoding="utf-8")
HOOKS = (REPO_ROOT / "printer-config" / "3dp-04" / "lifecycle-hooks.cfg").read_text(encoding="utf-8")
UPDATER = (REPO_ROOT / "printer-config" / "3dp-04" / "moonraker-overrides.conf").read_text(encoding="utf-8")


def value(name: str):
    match = re.search(rf"^variable_{re.escape(name)}:\s*(.+)$", OVERLAY, re.M)
    assert match is not None, f"missing variable_{name}"
    return ast.literal_eval(match.group(1))


def macro(name: str) -> str:
    section = OVERLAY.split(f"[gcode_macro {name}]", 1)[1]
    return re.split(r"^\[", section, maxsplit=1, flags=re.M)[0]


class PrinterOverlayTest(unittest.TestCase):
    def test_lifecycle_places_clear_skew_before_park(self) -> None:
        self.assertEqual(("clear_skew", "set_active_thermals"), value("startprint_pre_actions"))
        for actions in (value("endprint_actions"), value("cancelprint_actions")):
            self.assertLess(actions.index("clear_skew"), actions.index("park"))
        for prefix in ("START_PRINT_PRE_ACTION", "END_PRINT_ACTION", "CANCEL_PRINT_ACTION"):
            self.assertIn("SET_SKEW CLEAR=1", macro(f"_{prefix}_CLEAR_SKEW"))
        self.assertRegex(HOOKS, r'(?m)^variable_startprint_pre_actions: "clear_skew", "set_active_thermals"$')
        for variable in ("endprint_actions", "cancelprint_actions"):
            match = re.search(rf"^variable_{variable}:\s*(.+)$", HOOKS, re.M)
            self.assertIsNotNone(match)
            actions = ast.literal_eval(match.group(1))
            self.assertLess(actions.index("clear_skew"), actions.index("park"))
        self.assertEqual(3, HOOKS.count("SET_SKEW CLEAR=1"))

    def test_start_actions_use_two_pass_qgl_and_load_skew_last(self) -> None:
        actions = value("startprint_actions")
        self.assertNotIn("bed_soak", actions)
        self.assertEqual("smart_bed_soak", actions[0])
        self.assertNotIn("tilt_calib", actions)
        self.assertIn("qgl_fine", actions)
        self.assertIn("purge_blob", actions)
        self.assertGreater(actions.index("load_skew"), actions.index("purge_blob"))
        self.assertGreater(actions.index("load_skew"), actions.index("clean"))
        self.assertGreater(actions.index("load_skew"), actions.index("primeline"))
        self.assertIn("SKEW_PROFILE LOAD=calilantern_skew_profile", macro("_START_PRINT_ACTION_LOAD_SKEW"))

        qgl = [line.strip() for line in (macro("QGL_FINE") + macro("_QGL_FINE_FINISH")).splitlines()
               if line.strip().startswith("QUAD_GANTRY_LEVEL")]
        self.assertEqual(qgl, [
            "QUAD_GANTRY_LEVEL HORIZONTAL_MOVE_Z=30 SAMPLES=1 RETRIES=0",
            "QUAD_GANTRY_LEVEL HORIZONTAL_MOVE_Z=3",
        ])

    def test_end_defaults_and_parking_values(self) -> None:
        self.assertIn("reset_limits", value("endprint_actions"))
        self.assertEqual(50, value("park_lift_z"))
        self.assertEqual((150, 10), value("park_position_xy"))

    def test_updater_targets_stable_without_changing_live_path(self) -> None:
        self.assertIn("path: ~/klippain_config", UPDATER)
        self.assertIn("origin: https://github.com/agreen/klippain.git", UPDATER)
        self.assertIn("primary_branch: codex/3dp-04-stable", UPDATER)
        self.assertIn("managed_services: moonraker klipper", UPDATER)
        self.assertIn("install_script: install.sh", UPDATER)


if __name__ == "__main__":
    unittest.main()
