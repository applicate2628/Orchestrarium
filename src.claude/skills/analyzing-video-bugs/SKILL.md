---
name: analyzing-video-bugs
description: Extract frames from a UI/animation/layout bug video with ffmpeg, locate transitions, and read selected frames. Use for any video file; for static screenshots use Read directly.
---

# Analyzing video bugs

This skill processes an existing video file showing a UI bug, animation glitch, layout jump, or visual artifact, and turns it into a small set of frames an agent can actually read. It applies to **any video bug regardless of origin** — whether the user recorded the repro themselves and shared a path, or the agent captured the recording via the screen-capture workflow in `$windows-gui-manual-testing`. The skill begins after a video file exists on disk; it does not own video capture.

The Read tool reads images (PNG/JPG/GIF) and PDFs, but not video files. To analyze a video bug you must first extract frames with ffmpeg, then Read the resulting images.

## Related skills

- `$windows-gui-manual-testing` — parent visual-verification workflow; owns environment/theme context, evidence-type choice (screenshot vs short video vs frame sequence), screen capture when no recording exists, and structural-vs-cosmetic classification of UI issues.
- `$bug-hunting` — general diagnostic-logging methodology for runtime bugs whose cause is not obvious from inspection alone; Rule 4 there points back here for visual evidence.

## Tooling preflight (do this first, exactly once)

```bash
# Both should print a path. If either is empty, fall back to:
# winget install Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
where.exe ffmpeg
where.exe ffprobe
```

On Windows the winget install puts ffmpeg under `C:\Users\<user>\AppData\Local\Microsoft\WinGet\Links\ffmpeg.exe` — this path may not be in the current shell's PATH even when winget reports "installed". Always check `where.exe ffmpeg` and fall back to the full path when needed.

Use a scratch folder inside the repo (`.scratch/video-frames/`) so the output never accidentally gets committed — the repo's `/.scratch/` rule in `.gitignore` already covers this. Do not put frames in the system temp folder — Read needs absolute paths and the workflow gets much easier when frames live next to the repo.

## Pipeline

### Step 1 — Probe the video

```bash
ffprobe -v error -show_entries format=duration,size:stream=width,height,r_frame_rate \
  -of default=noprint_wrappers=1 "<video-path>"
```

Decide a coarse sampling rate based on duration:
- ≤ 10 s → 2 fps (~20 frames)
- 10–60 s → 1 fps
- > 60 s → 0.5 fps or sample only flagged ranges
- One-frame UI artifacts captured at 60 fps often need 4 fps coarse extraction first, then 60 fps dense extraction around the transition. Do not downsample away the only bad frame.

### Step 2 — Coarse extraction

```bash
ffmpeg -v error -i "<video>" -vf "fps=2,scale=1158:-1" -q:v 4 frame_%02d.jpg
```

- `scale=1158:-1` shrinks 1080p+ video so each frame is ~50–70 KB JPEG. 1158 px wide is enough to read UI text in most apps; go wider only if you cannot tell what a button says.
- `-q:v 4` is a good middle for JPEG (lower = better quality).
- `%02d` zero-pads filenames so they sort correctly in Glob output.
- If the capture is full desktop or multi-monitor, make a target-window crop before judging the UI. Start from the HWND `GetWindowRect` if available, but verify it against one full-desktop frame because virtual-screen coordinates and DPI can make the first crop wrong.

Read all coarse frames in parallel (one Read tool call per frame, batched in a single message). Identify the stable states (which frames look identical) and where the transitions are.

For many frames, build contact sheets before opening individual images:

```bash
ffmpeg -v error -framerate 4 -i "frame_%02d.jpg" \
  -vf "scale=550:-1,tile=4x9:margin=8:padding=4:color=white" \
  -frames:v 1 sheet.jpg
```

On Windows ffmpeg builds, `-pattern_type glob` may be unsupported; prefer numbered patterns such as `frame_%02d.jpg`.

### Step 3 — Find exact transition timestamps

Coarse sampling almost always straddles the moment of change. Use ffmpeg's scene detector to get precise timestamps:

```bash
ffmpeg -i "<video>" -vf "select='gt(scene,0.03)',showinfo" -an -f null - > scene.log 2>&1
grep -E "pts_time" scene.log
```

`scene` is the normalized frame-difference score: `0.03` catches most UI transitions, `0.1` is more selective. The `pts_time` values are your transition timestamps. Sometimes transitions come in pairs ~100–200 ms apart — the second timestamp is usually the "after" state and the first is mid-transition. This is the signal worth investigating.

For low-contrast layout shifts, try thresholds in the `0.015` to `0.03` range and cross-check against coarse frames. Scene detection is a locator, not a verdict.

### Step 4 — Dense sampling around transitions

Re-extract at higher rate over a narrow window:

```bash
ffmpeg -v error -ss <start> -t <duration> -i "<video>" \
  -vf "fps=15,scale=1158:-1" -q:v 3 dense_%02d.jpg
```

Then read dense frames around each suspicious timestamp.

For one-frame bugs, use the source frame rate (often 60 fps) and sample several repeated transitions, not just the first clean one:

```bash
ffmpeg -v error -ss <start> -t 0.55 -i "<video>" \
  -vf "crop=<w>:<h>:<x>:<y>,fps=60,scale=1200:-1" -q:v 3 dense_%03d.jpg

ffmpeg -v error -framerate 60 -i "dense_%03d.jpg" \
  -vf "scale=400:-1,tile=6x6:margin=8:padding=4:color=white" \
  -frames:v 1 dense_sheet.jpg
```

If the bug is intermittent or reported "between frames", inspect dense sheets from at least 3-5 transitions and cover both directions of the UI state change when both directions exist.

### Step 5 — Verify duplicates by file size

When two adjacent extracted frames have identical file sizes (bytes), they are usually the same source frame decoded twice — useful for confirming a stable state vs a real transition:

```bash
ls -la dense_*.jpg | awk '{print $5, $9}'
```

If `dense_05.jpg` and `dense_06.jpg` are both `54231 bytes` and `dense_07.jpg` is `57864 bytes`, the change happened between frame 6 and 7.

### Step 6 — Native-resolution verification

Coarse JPEGs can blur subtle UI details (cursor highlight, selected-state shading, 1 px borders). For the final root-cause check, pull individual frames at native resolution as PNG:

```bash
ffmpeg -v error -ss <ts> -i "<video>" -frames:v 1 probe_<ts>.png
```

These are large (700 KB+) but lossless, and the Read tool handles them fine.

## Interpretation heuristics

- **Cursor position drift across frames** = mouse trajectory. The cursor is the most reliable timestamp anchor for "when did the user click".
- **Highlighted button (different background colour)** = hover or pressed state. Distinguish hover (mouse over) from selected (toggle state) by checking adjacent frames — selected persists, hover follows cursor.
- **Identical file sizes across N frames** = the source content did not change, only the encoder happened to emit a new I-frame.
- **Scene-change pairs ~100–200 ms apart** = a two-step transition: the first event triggers a layout/style change, the second commits the final state. Bugs often live in the gap between them.
- **A whole-app size change between two states** (e.g. text appears 2× larger) is usually a DPI / scaling mismatch between two renderers, not a frame-rendering bug.

## Do not do these

- Do not read all dense frames in series — they are independent, batch them into a single message with parallel Read calls.
- Do not draw a conclusion from your own frame interpretation without confirming with the user what they actually see as the bug — the user's description of "the bug" almost always names a specific symptom, not the whole visual delta. Verify before coding fixes.
- Do not `git add .scratch/video-frames/` — that folder must stay local.
- Do not assume you must capture the video yourself; if the user has already provided one, skip capture and start at Step 1 on their file.
- Do not assume the user will record one; if the bug is animation/timing-dependent and no video exists, fall through to `$windows-gui-manual-testing` step 3 (Obtain and analyze video evidence) to record one, then return here for analysis.

## When the user shares only a description, not a video

If the bug is described verbally without any video or screenshot, decide which path applies:
- Animation, timing, layout-jump, or transition bug → request or capture a video, then return here.
- Static layout, color, text, or alignment issue → use `$windows-gui-manual-testing` directly (single screenshot is usually enough).
- Cause is not obvious from any visual at all → fall through to `$bug-hunting` and start with diagnostic logging.

## Terms and abbreviations

- `coarse extraction`: low-fps frame dump used to find candidate transition windows.
- `dense sampling`: high-fps frame dump over a narrow window around a known transition.
- `native-resolution PNG`: lossless single-frame snapshot used when subtle pixel-level detail matters.
- `pts_time`: presentation timestamp from ffmpeg's `showinfo` output; the time at which a frame is meant to be displayed.
- `scene-change pair`: two `pts_time` values close together; first usually marks the start of a transition, second the commit.
