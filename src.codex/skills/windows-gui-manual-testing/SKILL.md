---
name: windows-gui-manual-testing
description: Manual visual verification of Qt desktop and Windows GUI via screenshots, video frames, or live inspection. Use when Codex needs evidence-backed UI findings before or after a fix.
---

# Windows GUI Manual Testing

## Overview

Use this skill to inspect Windows desktop UI behavior visually and report concrete findings. Focus on reproducible evidence: screenshots, extracted video frames, exact control names, theme/state context, and before/after comparisons.

This is a narrow evidence-based verification specialist for Windows desktop UI, especially Qt desktop surfaces. Return one visual findings package with concrete observations, not codebase exploration or implementation ownership.

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
- DPI or display scaling if known
- window size and whether the panel is docked, floating, or maximally narrowed
- exact control path, for example `Analysis -> Data -> Resampling -> Mode`

When the issue is about interaction timing, note the pointer location and whether the bug happens on first open only or on every open.

### 2. Prefer the right evidence type

Use the lightest artifact that can prove the problem:

- single screenshot: static layout, wrong colors, clipped text, mismatched checkbox style
- two screenshots: before/after state, theme comparison, collapsed vs expanded panel
- short video: popup jerk, animation glitch, text reflow, control motion under the mouse
- exported frame sequence: detailed timing analysis when one bad intermediate frame matters

If the user gives a local image path, inspect it with `view_image`.

If the user gives a local video path, extract frames first, then inspect representative frames instead of guessing from the video description.

### 3. Obtain and analyze video evidence

When the bug is animation-, timing-, or sequence-dependent, video evidence is required. The video may come from one of two sources:

1. **The user records and shares the file themselves.** Skip directly to frame analysis via `$analyzing-video-bugs` using the provided path.
2. **The agent captures the video itself** when no recording exists. Use ffmpeg's `gdigrab` on Windows:

   ```powershell
   # Full desktop, 30 fps, 10 seconds, H.264 mp4
   ffmpeg -f gdigrab -framerate 30 -i desktop -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4

   # Specific window by title (window must be visible and named):
   ffmpeg -f gdigrab -framerate 30 -i title="ExactWindowTitle" -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4

   # Region of screen:
   ffmpeg -f gdigrab -framerate 30 -offset_x 100 -offset_y 100 -video_size 1280x720 -i desktop -t 10 -c:v libx264 -preset ultrafast -pix_fmt yuv420p .scratch/capture.mp4
   ```

   Notes:
   - Start the target app first, position and size it as needed, then start the capture command.
   - Most UI bugs reproduce in 5–15 seconds; do not record long sessions when a short repro is enough.
   - Store captures in `.scratch/` (gitignored). Frames extracted from captures live in `.scratch/video-frames/` per `$analyzing-video-bugs` conventions.
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

### 7. Report findings cleanly

Report findings as concrete UI observations, not guesses:

- what control was tested
- what frame/state is wrong
- what moved, clipped, duplicated, or repainted late
- whether the bug is theme-specific
- whether the issue is structural (`popup path`, `relayout`, `text wrap`, `stale style path`) or merely visual

Prefer short cause statements like:

- `Popup opens in two geometry stages.`
- `Summary label changes height when the combo opens, moving the next control.`
- `System theme is still using the custom combo popup path.`

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

## Guardrails

- Do not call a UI issue “fixed” from code inspection alone when visual evidence is available.
- Do not hide structural GUI problems with cosmetic text tweaks unless the user explicitly asks for a stopgap.
- Do not rely on a single screenshot for animation bugs when a short video or frame sequence exists.
- When a visual issue depends on an intermediate frame, say that explicitly and keep the frame numbers or timestamps in the notes.
