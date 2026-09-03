# Overrides details

In Klipper, when two identical `[section]` are defined, it's the last one in the include order that will take over. Additionally, any missing values are filled in by the last entry. This mechanism is called an "override".

To keeps Klippain files read-only and compatible with Moonraker's update manager, you will need to use this mechansim extensively. There is default values included in every Klippain files, but if you want to change them, you can add some overrides without having to dig and modify all the files in Klippain folders.

Use overrides to tweak machine dimensions, invert motor directions, change axis limits, currents, sensors type, or anything you feel the need to change. You can even override a full macro to replace it completely by your own or add new features to Klippain on your side. This is a very powerful feature!

  > **Note**
  >
  > Klipper does not allow `[board_pins]` sections to contain pin modifiers such as `!`, `^`, and `~`. Furthermore, when configuring multiple MCUs simultaneously, all aliases used in hardware sections must be prefixed with the MCU name. This is a current limitation of Klipper and the reason why you'll also need to use the `overrides.cfg` file to add them.


## Common overrides

Since my defaults aim to be as generic as possible, you won't need many overrides. However, there are still some common elements to check.

For example, **pay special attention to axis limits** in the `[stepper_...]` sections, run current, etc. Verify thermistor types in `[extruder]` and `[heater_bed]` sections. If using a multi-MCU configuration, you'll need to override any section where pins are connected to the secondary or toolhead boards to specify it. Finally, use overrides if you want to change motor direction or add a pull-up/down (using `!`, `^`, and `~`).

Additionally, if you want to add a new macro to Klippain or even replace an existing one to adapt it to your use case, you can do it the same way!


## How to write an override

The following examples should help you add all the overrides you need to customize Klippain and make it work correctly with your printer!

If something in your hardware isn't working as expected, first inspect the relevant default configuration file for your hardware. For example if your v0 display encoder is rotating in the opposite direction:
`cd ~/printer_data/config` then `less config/hardware/displays/V0_display.cfg`, copy the relevant portion then edit to suit in your `overrides.cfg`:
```
[display]
# Set the direction of the encoder wheel
#   Standard: Right (clockwise) scrolls down or increases values. Left (counter-clockwise scrolls up or decreases values.
#encoder_pins: ^v0_display:PA3, ^v0_display:PA4
#   Reversed: Right (clockwise) scrolls up or decreases values. Left (counter-clockwise scrolls down or increases values.
encoder_pins: ^v0_display:PA4, ^v0_display:PA3
```

Or let's say you want to change the motor current for the X-axis. You'll need to override the `[tmc2209 stepper_x]` section because that's where the current is defined. To do this, simply add the following to your `overrides.cfg` file:
```
[tmc2209 stepper_x]
run_current: ...
```

Similarly, if you want to invert the Z2 motor direction, override the `[stepper_z2]` section and add a `!` before the pin name:
```
[stepper_z2]
dir_pin: !mcu:Z2_DIR
```

Changing a thermistor type (like for the bed), can be done this way:
```
[heater_bed]
sensor_type: ...
```

You can even redefine a full macro! For example if the default Klippain prime line is not adapted to your needs, just override the macro like that:
```
[gcode_macro _MODULE_PRIMELINE]
gcode:
  # Put your custom prime line G-code here...
```

## Custom START_PRINT and END_PRINT actions

`START_PRINT` and `END_PRINT` are built from ordered action lists in `_USER_VARIABLES`.
Override these lists in `overrides.cfg` to reorder actions, remove actions,
duplicate actions, or insert your own custom actions.

Built-in `START_PRINT` actions are `bed_soak`, `extruder_preheating`,
`chamber_soak`, `extruder_heating`, `tilt_calib`, `z_offset`,
`contact_z_home`, `contact_auto_calibrate`, `beacon_calib`, `bedmesh`, `purge`,
`clean`, and `primeline`.

Built-in `END_PRINT` actions are `retract_filament`, `turn_off_heaters`,
`turn_off_fans`, `turn_off_motors`, and `reset_limits`.

Example:
```
[gcode_macro _USER_VARIABLES]
variable_startprint_actions: "bed_soak", "extruder_preheating", "my_start_action", "bedmesh", "primeline"
variable_endprint_actions: "retract_filament", "my_end_action", "turn_off_heaters", "turn_off_fans"
gcode:
```

The preferred way to add a custom action is to add its name to the list and define
its matching macro in `overrides.cfg`. Use lowercase letters, numbers, and
underscores for custom action names. Klippain uppercases the action name and calls
`_START_PRINT_ACTION_<NAME>` or `_END_PRINT_ACTION_<NAME>`.

For a custom `START_PRINT` action named `my_start_action`:
```
[gcode_macro _START_PRINT_ACTION_MY_START_ACTION]
gcode:
  # Put your custom START_PRINT G-code here...
```

For a custom `END_PRINT` action named `my_end_action`:
```
[gcode_macro _END_PRINT_ACTION_MY_END_ACTION]
gcode:
  # Put your custom END_PRINT G-code here...
```

Custom action macros receive the original `START_PRINT` or `END_PRINT` parameters,
so values such as `BED_TEMP`, `EXTRUDER_TEMP`, `MATERIAL`, or `FILTER_TIME` are
available through `params` when they were passed to the parent macro.

If a custom action is listed but its matching macro does not exist, Klippain raises
an error instead of silently skipping it.

`START_PRINT` also keeps the older `custom1` through `custom9` action slots for
compatibility. If `variable_startprint_actions` contains `custom1`, Klippain calls
`_MODULE_CUSTOM1`; if it contains `custom9`, Klippain calls `_MODULE_CUSTOM9`, and
so on. These slots only exist for `START_PRINT`. For new custom actions, prefer the
named `_START_PRINT_ACTION_<NAME>` pattern because it is clearer and does not limit
you to nine custom actions.

### Actions before motion and parking

The main `START_PRINT` action list begins after homing. For actions that must happen
before homing or any other START_PRINT motion, set `variable_startprint_pre_actions`
and define matching `_START_PRINT_PRE_ACTION_<NAME>` macros.

`END_PRINT` and `CANCEL_PRINT` also provide action lists immediately before `PARK`:
`variable_endprint_pre_park_actions` and `variable_cancelprint_pre_park_actions`.
Their matching macro names are `_END_PRINT_PRE_PARK_ACTION_<NAME>` and
`_CANCEL_PRINT_PRE_PARK_ACTION_<NAME>`. All three lists are empty by default, and
the original macro parameters are forwarded to custom actions.

For example, define an early setup action in `overrides.cfg`:
```ini
[gcode_macro _USER_VARIABLES]
variable_startprint_pre_actions: ["prepare"]
gcode:

[gcode_macro _START_PRINT_PRE_ACTION_PREPARE]
gcode:
    # Your setup commands here; axes may not be homed yet.
```

Use a list (`["prepare"]`) or tuple (`"prepare",`) for a single action, and `()`
to disable a hook list. Entries are custom action names, not the built-in actions
from the main START/END lists. Actions execute in order and may be repeated.
An unknown action raises an error before any commands in the parent macro run.

Pre-start actions run after parameter/material validation and before setup,
homing, or MMU initialization. Parameters saved on `START_PRINT` are available
when the action macro executes. As with other Klipper macros, the parent template
is evaluated before its commands run; actions cannot change already evaluated
conditions in that parent invocation.

Cancel pre-park actions also run when axes are unhomed; cancellation still skips
`PARK` in that case. Keep these actions short and safe without homing. The existing
END sequence remains `PARK`, `M400`, optional `BED_MESH_CLEAR`, then the configured
cleanup actions. Preserve `reset_limits` when replacing `endprint_actions` if you
want its configured velocity, extrusion and speed resets.
