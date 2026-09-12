# vk-scribe

Download a VK Video playlist and turn every lecture into text. For each
video the tool produces, side by side with the file:

- a `.txt` report with timecodes: speech transcript (faster-whisper) +
  slide text via OCR (RapidOCR with a Cyrillic-capable model) + VK
  subtitles, when the platform provides them;
- a `.pdf` — the slide deck rebuilt from the detected unique slides, one
  page per slide in order of appearance, without quality loss (img2pdf);
- a `<name>_slides/` folder with the slide frames as JPEG.

## Quick start (Windows)

No manual prerequisites — `run.ps1` bootstraps everything. Run it
without arguments for a step-by-step interactive menu that asks for the
playlist, the output folder, the recognition quality, and what to
extract, then shows live progress for every stage:

```powershell
.\run.ps1
```

Prefer a single command? That works too:

```powershell
.\run.ps1 run "https://vkvideo.ru/playlist/-169062866_5/season_0" -o vk_course
```

The launcher:

1. installs **uv** via winget when missing (official installer script as
   a fallback);
2. before `run`/`download`, checks **ffmpeg** — the only external tool
   yt-dlp needs to mux VK streams into mp4. When it is missing, the
   launcher warns and offers to install it via winget (Enter = install,
   `n` = skip). `extract` reads local files without ffmpeg, so the check
   is skipped for it;
3. runs `uv sync` — creates `.venv`, installs every dependency from
   `uv.lock`, and downloads a managed Python 3.13 if none is present.
   When an **NVIDIA GPU** is detected (`nvidia-smi` found), it also
   installs the CUDA runtime wheels (cuBLAS + cuDNN, `--extra cuda`) so
   Whisper runs on the GPU; otherwise Whisper uses the CPU;
4. launches the `vk-scribe` CLI with all passed-through arguments.

On first use the tool also downloads:

- the Cyrillic OCR recognition model (~8 MB) → `~/.cache/vk_scribe/ocr/`
- the Whisper model (`small` ≈ 460 MB) → the standard HuggingFace cache

## Commands

| Command | What it does |
|---|---|
| *(no command)* | Interactive menu — prompts for everything, then runs |
| `menu` | Same interactive menu, explicitly |
| `run <URL>` | Download the playlist, then extract text for every video |
| `download <URL>` | Only download the playlist |
| `extract <DIR>` | Extract text from videos already in a local folder |

Every command shows two live progress bars: an overall one
("3 of 12 videos") and a per-video one — percent downloaded while
fetching, then the current stage (speech recognition, slide detection,
slide OCR) while extracting.

Full cycle:

```powershell
.\run.ps1 run "https://vkvideo.ru/playlist/-169062866_5/season_0" -o vk_course
```

Download only, then extract later:

```powershell
.\run.ps1 download "https://vkvideo.ru/playlist/-169062866_5/season_0" -o vk_course
.\run.ps1 extract .\vk_course
```

Without the launcher (uv already installed):

```powershell
uv sync
uv run vk-scribe --help
```

## Output layout

```
vk_course/
├── 001 - Lecture title [123456].mp4
├── 001 - Lecture title [123456].txt   <-- speech + slides with timecodes
├── 001 - Lecture title [123456].pdf   <-- rebuilt slide deck
├── 001 - Lecture title [123456]_slides/   <-- slide frames (JPEG)
│   ├── slide_001.jpg
│   └── ...
├── 002 - ...
├── _playlist_manifest.json             <-- filename -> URL mapping
└── .download_archive.txt               <-- yt-dlp archive for incremental runs
```

Re-running `extract` leaves videos that already have a `.txt` untouched
(`--overwrite` forces reprocessing). Re-running `run` downloads only the
new playlist entries (yt-dlp download archive).

## Useful options

| Option | Effect |
|---|---|
| `-m tiny/base/small/medium/large-v3` | Whisper size (default `small`). `medium` is more accurate but slower |
| `--device auto/cuda/cpu` | Whisper backend; `auto` tries CUDA and falls back to CPU |
| `-l ru` | Hint the spoken language (auto-detected by default) |
| `--skip-whisper` | Slide OCR only, no speech recognition |
| `--skip-ocr` | Speech only, no slide OCR |
| `--skip-pdf` | Do not rebuild the slide deck and frame images |
| `--limit 1` | Process only the first video — handy for tuning |
| `--change-ratio 0.015` | Slide-change sensitivity: fraction of strongly changed pixels (lower = more sensitive; default 0.02) |
| `--sample-interval 1.5` | Frame sampling step in seconds (default 2) |
| `--cookies cookies.txt` | Browser cookies for private playlists |

## How it works inside

1. **Download** — yt-dlp; files are named `NNN - Title [id].mp4` so
   alphabetical order matches playlist order.
2. **Slide detection** — one frame every 2 s; a slide change is declared
   when the fraction of strongly changed pixels between downscaled
   thumbnails exceeds a threshold; short segments (fades, animations
   under 3 s) are discarded.
3. **Deduplication** — visually identical slides (a lecturer returning to
   an earlier slide) merge, keeping all occurrence timecodes.
4. **OCR** — RapidOCR with the PP-OCRv5 East-Slavic recognition model
   (Russian/English). Progressive slides (bullets appearing one by one)
   collapse into the richest variant.
5. **Speech** — faster-whisper with a VAD filter; audio is decoded
   straight from the mp4 via PyAV, no separate extraction step.

## Tuning for a specific playlist

- OCR misses slide changes → lower `--change-ratio` to 0.01–0.015 and/or
  `--sample-interval` to 1.5.
- Too many "slides" (every animation counts) → raise `--change-ratio` to
  0.03–0.05.
- Hallucinated speech in silence → already mitigated by VAD; `-m medium`
  helps further.

## Troubleshooting

- **Whisper model download fails (huggingface.co unreachable)** — point
  at a mirror first: `$env:HF_ENDPOINT="https://hf-mirror.com"`.
- **CUDA errors from faster-whisper (cublas/cudnn)** — run the launcher
  once with an NVIDIA GPU present: it installs the CUDA wheels
  automatically (`uv sync --extra cuda` does the same by hand). Without
  them the tool logs one line and runs on the CPU.
- **yt-dlp format errors / HTTP 403** — update it: `uv add yt-dlp -U`
  (VK changes its delivery periodically).
- **Private playlist** — export cookies from the browser (the
  "Get cookies.txt LOCALLY" extension) and pass `--cookies cookies.txt`.

## Development

```powershell
uv sync                 # runtime + dev dependencies
uv run pytest           # unit tests
uv run ruff check .     # lint
uv run ruff format .    # format
uv run mypy src         # type check
uv run python scripts/bump-version.py --bump patch   # after edits
```

pre-commit hooks (ruff + mypy): `uv run pre-commit install` after
`uv add --pre-commit` or `pip install pre-commit`.
