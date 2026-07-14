---
name: windows-gui-manual-testing
description: "Windows GUI testing: verify desktop UI with visual evidence."
---

# Windows GUI Manual Testing

## Overview

Use this skill to inspect Windows desktop UI behavior visually and report concrete findings. Focus on reproducible evidence: screenshots, extracted video frames, exact control names, theme/state context, and before/after comparisons.

This is a narrow evidence-based verification specialist for Windows desktop UI, including Qt, Avalonia, WinUI/WPF, WebView/native-child, and other native or hosted Windows surfaces. Return one visual findings package with concrete observations, not codebase exploration or implementation ownership.

Hard crop gate: before using any cropped screenshot, video, or extracted frame as full-window evidence, inspect a verification frame and prove it contains the entire target window. For normal overlapped windows, the top-right close button must be visible. If any edge is clipped or the close-button anchor is missing, discard the crop and use full-desktop evidence or recalculate the rectangle before proceeding.

## Scope

- Use when visual/manual evidence is needed before a fix, after a fix, or when the bug is only visible through screenshots, video, or frame-by-frame inspection.
- Keep the work grounded in running UI behavior, control state, theme context, and reproducible visual evidence.
- Do not treat this skill as a codebase explorer, a generic implementation owner, a global UX reviewer, or a lead.

## Related skills

- `$analyzing-video-bugs` — frame extraction, scene-change detection, and dense sampling for any video file (user-provided or captured here in step 3). Always route video evidence through that skill rather than reading raw video.
- `$bug-hunting` — broader diagnostic-logging methodology for runtime bugs whose cause is not obvious from visual evidence alone. Use when visual inspection narrowed the symptom but the underlying gate/state needs runtime confirmation.

## Workflow

### 1. Prepare the context

Record the environment before drawing conclusions:

- app/build being tested
- theme or style mode (`system`, custom, CAD, dark/light)
- actual per-monitor scale from `GetDpiForWindow`, plus the target process's DPI-awareness mode from `GetProcessDpiAwareness` or `DPI_AWARENESS_CONTEXT`
- window size and whether the panel is docked, floating, or maximally narrowed
- exact control path, for example `Analysis -> Data -> Resampling -> Mode`

When the issue is about interaction timing, note the pointer location and whether the bug happens on first open only or on every open.

### 2. Prefer the right evidence type

Use the lightest artifact that can prove the problem:

- single screenshot: static layout, wrong colors, clipped text, mismatched checkbox style
- two screenshots: before/after state, theme comparison, collapsed vs expanded panel
- short video: popup jerk, animation glitch, text reflow, control motion under the mouse
- exported frame sequence: detailed timing analysis when one bad intermediate frame matters

If the user gives a local image path, Read the frame image (Read tool on Claude Code; view_image on Codex).

If the user gives a local video path, extract frames first, then inspect representative frames instead of guessing from the video description.

### 3. Obtain and analyze video evidence

When the bug is animation-, timing-, or sequence-dependent, video evidence is required. The video may come from one of two sources:

1. **The user records and shares the file themselves.** Skip directly to frame analysis via `$analyzing-video-bugs` using the provided path.
2. **The agent captures the video itself** when no recording exists. Probe the installed ffmpeg build first with `ffmpeg -hide_banner -filters | Select-String ddagrab` (or `grep ddagrab`). Prefer the Desktop Duplication / Direct3D 11 `ddagrab` filter when present for hardware-composited Direct3D, OpenGL, WebView2, and Qt Rendering Hardware Interface surfaces; use the installed build's documented `ddagrab` input syntax. Keep `gdigrab` as the fallback and for window-title or region convenience.

   ```powershell
   # Full desktop, 30 fps, 10 seconds, H.264 mp4
   ffmpeg -f gdigrab -draw_mouse 1 -framerate 30 -i desktop -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4

   # One-frame artifacts: use 60 fps and keep the clip short
   ffmpeg -f gdigrab -draw_mouse 1 -framerate 60 -i desktop -t 9 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4

   # Specific window by title (window must be visible and named):
   ffmpeg -f gdigrab -draw_mouse 0 -framerate 30 -i title="ExactWindowTitle" -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4

   # Region of screen:
   ffmpeg -f gdigrab -draw_mouse 0 -framerate 30 -offset_x 100 -offset_y 100 -video_size 1280x720 -i desktop -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4
   ```

   Correct full-window capture recipe:

   1. Find the target top-level HWND, then call `GetWindowRect` and the virtual-screen metrics (`SM_XVIRTUALSCREEN`, `SM_YVIRTUALSCREEN`, `SM_CXVIRTUALSCREEN`, `SM_CYVIRTUALSCREEN`). On Windows with DPI scaling or extended glass/shadow bounds, also call `DwmGetWindowAttribute(..., DWMWA_EXTENDED_FRAME_BOUNDS, ...)` and prefer the DWM extended-frame rectangle when `GetWindowRect` clips the right or bottom edge.
   2. If any side of the window rect is outside the visible virtual screen, restore/move/resize the window into a known visible rectangle before recording.
   3. Normalize capture width and height to even values for H.264.
   4. Capture one still frame with the exact intended `-offset_x`, `-offset_y`, and `-video_size`.
   5. Read the frame image (Read tool on Claude Code; view_image on Codex). Confirm the entire app surface is present from left edge to right edge and from title bar to bottom edge. For normal overlapped windows, the top-right close button must be visible; if the close button is missing, the crop is wrong and cannot be used as full-window evidence.
   6. Only after the check frame passes, drive the repro and record the video. If the check frame is clipped, discard the setup and correct the rectangle first.

   UI Automation preflight:
   - When UI Automation is available, use it to identify the exact top-level app window and record its `BoundingRectangle`, title, process id, and title-bar button controls before choosing a crop.
   - Treat the UIA close button as a hard crop anchor for normal windows: if UIA reports a close button but the verification still does not show it, the crop is wrong.
   - If Win32 or DWM bounds disagree with UIA bounds on a high-DPI desktop, prefer the rectangle whose verification frame shows the full title bar and close button; stale or DPI-logical `GetWindowRect` values can crop the right side.
   - Re-run UIA discovery after any window move, resize, maximize, restore, detach, or user adjustment. Do not reuse stale coordinates.
   - For scripted repro clicks, prefer UIA element centers for tabs/buttons, then save an action log with target name, role, and absolute coordinates. After recording, verify the video or app log proves those clicks landed; a clip with wrong-click actions is not evidence.
   - Do not blame a console/log window that is behind or below the app unless the verification frame actually shows it covering the target window. Crop the app window, not the nearby tooling.

   Notes:
   - Choose `-draw_mouse 0` or `1` deliberately and record the choice. Hover-state evidence may need the cursor position, but the cursor can also occlude the control under test.
   - Start the target app first, position and size it as needed, then start the capture command.
   - Before any cropped window or region capture, prove that the requested capture rectangle contains the whole visual surface under test. If `GetWindowRect` extends off the visible desktop, or if the right/bottom side of the app is outside the monitor, first move/resize/maximize the window fully into the visible desktop or capture the full desktop instead. Do not treat a partial crop as evidence for full-window behavior.
   - Most UI bugs reproduce in 5–15 seconds; do not record long sessions when a short repro is enough.
   - Store captures in `.scratch/` (gitignored). Frames extracted from captures live in `.scratch/video-frames/` per `$analyzing-video-bugs` conventions.
   - For native-child, WebView, popup, tooltip, menu, overlay, or airspace bugs, prefer full-desktop capture first. Window-title capture can miss or mis-layer separate native/top-level windows; crop the target window after capture.
   - If process APIs do not reveal the visible app window reliably, enumerate HWNDs with Win32 `EnumWindows` + `GetWindowText` + `GetWindowRect`; do not trust `Get-Process.MainWindowTitle` as the only locator. In PowerShell use a variable like `$procId`, not `$pid`, because `$PID` is read-only.
   - On multi-monitor or high-DPI desktops, treat `GetWindowRect` as virtual-screen coordinates. Compare the crop rectangle against the virtual-screen bounds, not just the primary monitor. If any side is clipped or ambiguous, move the window into a known visible rectangle before recording.
   - After starting a new capture setup, extract or capture one verification frame before driving the repro. Inspect it directly and confirm the full left-to-right and top-to-bottom app surface is present, including side panels, previews, popups, overlays, and native child controls that matter to the bug. If the check frame is clipped, discard that capture setup and correct the rectangle before recording evidence.
   - For intermittent one-frame bugs, drive several repeated transitions in one clip. Bring the exact HWND foreground before each scripted hotkey or click, leave a short stable pause between transitions, and verify the video file exists with a non-trivial byte size.
   - If the user must trigger the repro manually, coordinate timing: say "starting capture, please trigger the bug now" and wait for confirmation in chat that the trigger fired.
   - If `ffmpeg gdigrab` is unavailable (non-Windows host, restricted environment, no ffmpeg in PATH), ask the user to record with the OS's built-in tool (Game Bar via Win+G on Windows, QuickTime on macOS, GNOME Screencast on Linux) and provide the file path.

Once a video file exists on disk, hand it off to `$analyzing-video-bugs` for the systematic ffprobe → coarse extraction → scene-change detection → dense sampling → native-resolution verification pipeline. Do not read raw video files; do not extract frames ad hoc here when the specialized skill already owns that workflow.

### 4. Inspect dropdowns and popup animation

For combo boxes and popup lists, check these phases explicitly:

1. closed resting state
2. first visible popup frame
3. mid-open frame
4. “almost open” frame
5. fully open frame
6. selected state after close

Look for:

- popup geometry changing after it is already visible
- selected text duplicating, disappearing, or repainting late
- popup chrome and content moving in separate stages
- shadow/background arriving after the list content
- popup width snapping after open
- theme mismatch between closed combo and opened popup

If menus behave correctly but combo boxes do not, treat them as separate popup paths and do not assume a style-only bug.

### 5. Inspect layout shifts and text reflow

When a control “moves under the mouse”, inspect neighboring labels and summaries, not just the clicked widget.

Specifically check for:

- word-wrap adding/removing lines
- conditional help text appearing/disappearing
- summary labels changing height
- scrollbars appearing and shrinking the viewport
- combo open/close changing available width and forcing relayout

When stabilizing text, prefer preserving readable content over blindly truncating it. If a compact one-line summary is needed, keep the full text in a tooltip or a dedicated detail surface.

### 6. Compare themes intentionally

For theme-dependent bugs, check at least:

1. `system`
2. the project’s custom/styled mode

If the project has an additional theme family such as CAD, check that too. A fix that only improves one theme but leaves another on a different popup path is incomplete.

For before/after or cross-theme no-change claims, use the pixel-diff method in step 8; side-by-side inspection alone cannot support a no-visual-regression `PASS`.

### 7. Report findings cleanly

Return one findings package with the tested control path; environment (app/build, theme, actual DPI and DPI-awareness mode, window state); evidence type; concrete observations; structural-vs-cosmetic classification; theme-specificity; residual risk; and a final gate decision of `PASS`, `REVISE`, or `BLOCKED`. Report findings as concrete UI observations, not guesses:

- what control was tested
- what frame/state is wrong
- what moved, clipped, duplicated, or repainted late
- whether the bug is theme-specific
- whether the issue is structural (`popup path`, `relayout`, `text wrap`, `stale style path`) or merely visual
- the evidence file path plus frame number or timestamp for every observation, not only intermediate-frame findings
- whether blur or fractional-scale behavior comes from Desktop Window Manager bitmap stretching of a DPI-unaware/system-aware process (an app-manifest finding) or from the paint path

Prefer short cause statements like:

- `Popup opens in two geometry stages.`
- `Summary label changes height when the combo opens, moving the next control.`
- `System theme is still using the custom combo popup path.`

#### 7.1 Persist non-passing findings

On `REVISE` or `BLOCKED`, file each finding in `work-items/bugs/<date>-<slug>.md` using the qa-engineer-owned format with `found-by: windows-gui-manual-testing` before returning the verdict. Cite volatile machine-local evidence by `.scratch/` path and frame timestamp, but make the bug's repro steps, control path, theme, actual DPI, DPI-awareness mode, and window state sufficient to re-derive that evidence.

### 8. Re-test after a fix

After a GUI fix, re-check the exact failure path first, then verify nearby regressions:

- same control
- same theme
- same window width
- same first-open interaction
- neighboring controls that used to shift

For dropdown fixes, always verify both:

- first open after window creation/theme switch
- reopen after one successful interaction

For still-image before/after, theme, or no-change claims, produce a machine diff such as `magick compare -metric AE before.png after.png diff.png` or an ffmpeg difference blend. Mask only named legitimately volatile regions such as clocks, carets, or cursors, and report the changed-pixel count and affected regions. An eyeball-only comparison cannot establish a no-visual-regression `PASS`.

## Guardrails

- Do not call a UI issue “fixed” from code inspection alone when visual evidence is available.
- Do not hide structural GUI problems with cosmetic text tweaks unless the user explicitly asks for a stopgap.
- Do not rely on a single screenshot for animation bugs when a short video or frame sequence exists.
- When a visual issue depends on an intermediate frame, say that explicitly and keep the evidence path plus frame numbers or timestamps in the notes.
