from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (REPO_ROOT / "printer-config" / "3dp-04" / "klippain-overrides.cfg").read_text(encoding="utf-8")


def value(name: str):
    match = re.search(rf"^variable_{re.escape(name)}:\s*(.+)$", OVERLAY, re.M)
    assert match is not None, f"missing variable_{name}"
    return ast.literal_eval(match.group(1))


def macro(name: str) -> str:
    section = OVERLAY.split(f"[gcode_macro {name}]", 1)[1]
    return re.split(r"^\[", section, maxsplit=1, flags=re.M)[0]


class PrinterOverlayTest(unittest.TestCase):
    def test_lifecycle_uses_clear_skew_hooks(self) -> None:
        self.assertEqual(["clear_skew"], value("startprint_pre_actions"))
        self.assertEqual(["clear_skew"], value("endprint_pre_park_actions"))
        self.assertEqual(["clear_skew"], value("cancelprint_pre_park_actions"))
        for prefix in ("START_PRINT_PRE_ACTION", "END_PRINT_PRE_PARK_ACTION",
                       "CANCEL_PRINT_PRE_PARK_ACTION"):
            self.assertIn("SET_SKEW CLEAR=1", macro(f"_{prefix}_CLEAR_SKEW"))

    def test_start_actions_use_two_pass_qgl_and_load_skew_last(self) -> None:
        actions = value("startprint_actions")
        self.assertNotIn("tilt_calib", actions)
        self.assertIn("qgl_fine", actions)
        self.assertGreater(actions.index("load_skew"), actions.index("purge"))
        self.assertGreater(actions.index("load_skew"), actions.index("clean"))
        self.assertGreater(actions.index("load_skew"), actions.index("primeline"))
        self.assertIn("SKEW_PROFILE LOAD=calilantern_skew_profile", macro("_START_PRINT_ACTION_LOAD_SKEW"))

        qgl = [line.strip() for line in macro("QGL_FINE").splitlines()
               if line.strip().startswith("QUAD_GANTRY_LEVEL")]
        self.assertEqual(qgl, [
            "QUAD_GANTRY_LEVEL HORIZONTAL_MOVE_Z=30 SAMPLES=1 RETRIES=0",
            "QUAD_GANTRY_LEVEL HORIZONTAL_MOVE_Z=3",
        ])

    def test_end_defaults_and_parking_values(self) -> None:
        self.assertIn("reset_limits", value("endprint_actions"))
        self.assertEqual(50, value("park_lift_z"))
        self.assertEqual((150, 10), value("park_position_xy"))


if __name__ == "__main__":
    unittest.main()
