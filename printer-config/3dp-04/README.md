# 3dp-04 overlay and update handoff

This directory exists only on the personal `codex/3dp-04` branch. The generic
`codex/configurable-print-actions` branch contains no printer-specific values. Nothing here
is installed automatically by Klippain's installer or workflow.

## Repository inspection

Inspected upstream `main` at `295cf77549d17474198ef5af10335a11abf014db`.
There is no CONTRIBUTING file or active validation workflow at that revision.
The only workflow is a commented-out stale-issue workflow. Existing validation is
`scripts/validate_probe_framework.py`, Python unittest tests and
`tests/install_mcu_templates_test.sh`. The added workflow runs those same entry
points. The new lifecycle tests use Jinja2 to render the actual macros.

`START_PRINT` homes before its existing action list, so it has an empty-by-default
pre-start action list. `END_PRINT` and `CANCEL_PRINT` now expose their complete
ordered sequences as action lists; their defaults preserve the prior command
order. `reset_limits` remains in the default END list. `PARK` already supports
a configurable lift and clamps it to the remaining Z travel; it is unchanged.

## Proposed user configuration

`klippain-overrides.cfg` is an overlay for a Voron 2.4 300mm with Tap. It clears
skew before START core setup/homing and places `clear_skew` before `park` in the
ordered END/CANCEL action lists, then loads
`calilantern_skew_profile` after purge, cleaning and primeline. Its START list is
based on the current upstream Tap profile; merge any existing custom actions
from the live printer before installing it. Keep the existing `[skew_correction]`
section and saved profile. No calibration data is supplied or changed here.

Live inspection on 2026-09-03 confirmed that 3dp-04 already uses the listed
`purge_blob`, `qgl_fine` and `load_skew` actions, includes `reset_limits`, and has
the requested parking values. Its existing `qgl_fine.cfg` already has the same
coarse pass followed by a deferred, state-checked fine pass. The deployment diff
therefore adds the pre-start action, ordered END/CANCEL actions and updater override;
it preserves those existing definitions rather than replacing them.
`lifecycle-hooks.cfg` is the exact small file intended for the live user-config
directory; include it once at the end of `overrides.cfg`.

`thermal-management.cfg` is the exact thermal policy intended to be installed as
`~/printer_data/config/klippain-thermal-management.cfg`. Replace the existing
`[include electronics_enclosure_fan.cfg]` line in `printer.cfg` with an include
of that file; do not include both because they drive the same controller-fan pin.
The old file should remain in the rollback backup.

The smart soak uses the installed Voron Klipper Extensions `temp_tracker` over
the prior ten minutes of chamber readings. PLA, PETG and TPU always wait only for
bed temperature. ABS and ASA request an eight-minute soak unless the recent
chamber average is within 5C of the slicer's requested `CHAMBER` target. With a
50C target, an average of 45C or higher skips the timed soak. `SOAK=<minutes>`
overrides the material duration, and `FORCE_SOAK=1` prevents a warm-printer skip.
The tracker starts with no history after a Klipper restart, which safely produces
a cold result until readings accumulate.

The custom electronics-fan macro is replaced by Klipper's native
`controller_fan`: active speed 0.8, then speed 0.3 for 300 seconds after the
watched heaters and drivers become inactive. The RPi fan defaults to an idle
target of 55C with 3C hysteresis and a 0.60 speed cap. START_PRINT lowers its
target to 47C; END_PRINT and CANCEL_PRINT restore the 55C idle target.

`QGL_FINE` calls the existing Klippain QGL wrapper twice. The coarse call uses
`HORIZONTAL_MOVE_Z=30 SAMPLES=1 RETRIES=0`; the fine call changes only
`HORIZONTAL_MOVE_Z=3`. Sampling, sample tolerance, sample retries, QGL tolerance
and QGL retries therefore come from the printer's normal configuration on the
fine call. No global QGL override is added. The START action retains the normal
already-leveled/force-homing condition, and the following `z_offset` action still
rehomes Z. A direct manual `QGL_FINE` always requests both passes.

These command overrides are supported by
[Klipper's QGL command](https://www.klipper3d.org/G-Codes.html#quad_gantry_level).
The final 3mm traverse needs a supervised physical check after the coarse pass;
software tests cannot establish Tap clearance or the actual gantry condition.
Parking uses a 50mm lift and XY 150,10.

## Safe sync and promotion

- Keep fork `main` as an unmodified upstream mirror. It was 95 commits behind,
  with no unique commits, at inspection time.
- Keep the generic lifecycle commit on `codex/configurable-print-actions`, suitable for upstream
  review. The fork-only workflow lives on `codex/validated-hooks`. Rebase
  unpublished review work onto new upstream revisions;
  avoid rewriting any branch used by a printer.
- Use `codex/3dp-04` for integration candidates. Merge upstream updates into a
  new candidate branch, resolve conflicts, review release/config changes, run
  all validation, and compare the live user configuration before promotion.
- Point the printer only at `codex/3dp-04-stable`, advanced manually by a
  fast-forward to an explicitly reviewed candidate SHA after successful CI.
  Do not enable automatic merging or deployment from upstream. A scheduled
  upstream comparison/PR can be added later; it should never advance stable.

The stable branch is deliberately not created by this overlay. Create it at the
reviewed candidate SHA after checking the live printer configuration. For future
promotions, ensure the previous stable SHA is an ancestor of the candidate:

```sh
git merge-base --is-ancestor origin/codex/3dp-04-stable CANDIDATE_SHA
git push origin CANDIDATE_SHA:refs/heads/codex/3dp-04-stable
```

Do not force-push stable. Preserve the previous deployed SHA and user-config
backup for rollback. Revert problematic changes on the branch for routine remote
rollback; an emergency local checkout of the saved SHA is a separate manual
recovery step while the printer is idle.

## Repointing Moonraker after validation

First read the live `moonraker.conf`, all its included updater definitions, the
Klippain checkout path/branch/remotes/status and the user `printer.cfg`,
`variables.cfg` and `overrides.cfg`. Check whether the live version predates the
95 upstream commits now in the candidate. Do not assume this is only a remote-URL
change. Preserve any existing modifications, includes, saved calibration and
symlinks before proceeding.

The upstream installer defaults to `~/klippain_config`, hardcodes Frix-x for a
fresh clone and installs managed directories as symlinks. For an existing clone
it skips the download; do not rerun a fresh installer to switch forks. Its
post-install stage also installs ShakeTune, so changing sources alone should not
invoke the installer unnecessarily.

After confirming the exact diff, idle printer state and rollback backup:

1. Create the stable branch at the exact validated/reviewed candidate SHA.
2. Keep the existing checkout path and add `upstream` pointing to
   `https://github.com/Frix-x/klippain.git` if absent. Set `origin` to
   `https://github.com/agreen/klippain.git` and fetch it.
3. Switch the clean checkout to a local `codex/3dp-04-stable` branch tracking
   `origin/codex/3dp-04-stable`. Stop if uncommitted printer changes would be lost.
4. Copy/merge the reviewed overlay into user-owned configuration, outside the
   Klippain checkout. Include it last from `overrides.cfg` if using a separate
   file. This keeps future fork updates from silently changing printer values.
5. Apply `moonraker-overrides.conf` in the user-owned `moonraker.conf` after the
   base include. Preserve the actual checkout path and existing updater options.
   Do not edit the managed `moonraker/base.conf` symlink target.
6. With explicit approval for the live restart, restart Moonraker and Klipper,
   inspect startup errors, and verify the updater points to the stable branch.
7. Supervise START, two-pass QGL, END and CANCEL, including parking near maximum
   Z, before relying on this for unattended prints.

The printer was inspected read-only; no files, services, or Git refs were changed.
Before deployment, preserve these five untracked files in `~/klippain_config`:
the local Mellow SB2040 Pro v3 board definition and its swap file,
`macros/base/park.cfg.orig`, plus local Moonraker timelapse and Voron-extension
snippets. Moonraker reported the tracked checkout pristine at `ac565f2`, one
upstream commit behind, with Klipper and Moonraker active.
