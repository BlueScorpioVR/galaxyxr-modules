# 0.1.2-experimental

- Make **100% curvature equal to v0.1.0's 75%**. Both the raw curvature ceiling
  and width-based arc limit are reduced, so the change also applies to wide
  windows. Slider percentages remain 0-100; the new ceiling is 3/m with a nominal
  112.5-degree arc limit.
- Publish the module source, reproducible builder, checks and disabled ZIP.
- Add the module to the KernelSU GXR Sources catalogue and provide an update feed.
- Own a separate handle to the same CPM scene node so flat rollback still works
  after Android closes its node wrapper. Release it only after successful rollback;
  failed live restores remain retryable.
- Isolate per-task cleanup failures, attempt all menu cleanups, and avoid repeating
  the same fatal error every heartbeat during shutdown.
- Archive old runtime diagnostics when explicitly acknowledging old-boot quarantine.
- Keep task-local Curve/Flatten controls, remembered strength while running,
  independent windows, firmware/hash gating and supervised flat restoration.
- Preserve disabled-by-default installation, including upgrades. Enable separately
  and restart with active root as documented; no automatic interface restart.

## Validation and limitations

The repaired 0.1.2 build passed a three-minute staged multi-window test including
curved-app close/reopen and automatic flat shutdown, with no cleanup errors and
unchanged SystemUI/SpaceFlinger PIDs. The owner reported flawless behavior and
subsequently confirmed the installed version runs fine. Host regression tests
cover reduced-range scaling, wrapper lifetime, retryable rollback and isolated
task/menu cleanup. A proposed ten-minute test was not run.

An earlier 0.1.0 session was followed by a native SystemUI crash. Its root cause
remains unresolved: fixing the confirmed cleanup bug is not proof that the native
crash is fixed. Crash quarantine and explicit recovery remain in place.

Galaxy XR SM-I610 / I610UEU2AZF3 only. Flat move/resize highlights, a corner that
can sit behind a curved edge, and possible head-motion rim flicker remain known
limitations. Immersive and system-control surfaces are not supported. This is
experimental, not certification of every app, keyboard or lifecycle transition.
