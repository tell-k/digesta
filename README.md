# digesta

English | [日本語](README.ja.md)

An [Agent Skill](https://agentskills.io/) that turns a meeting or study-session recording and its transcript into minutes, a graphic recording, and a digest video. The name is Latin for "things arranged and summarized".

- **Minutes**: decisions, action items, and the key points of each talk or agenda item
  - Markdown, optionally docx (`<name>_summary.md`)
- **Graphic recording**: a one-page visual summary
  - PNG (`<name>_graphic_4k.png`, `_1920.png`)
- **Digest video**: a few minutes of clips in the speakers' own voices, with subtitles, narrated title/recap cards, and background music
  - mp4 (`<name>_digest.mp4`, 1920x1080)

> **Note:** digesta is built for Japanese meetings. The skill instructions, the generated minutes, subtitles, narration, and the script messages are in Japanese.

Styles (switch with the `style` setting; the same content can be re-rendered in another style):

- `doodle`: hand-drawn, with characters (for study sessions)
- `business`: white background, sans-serif, straight lines, no characters (for meetings and reports)
- `pop`: colorful minutes-style layout; character illustrations are generated with Gemini
- `mono`: yellow, black and gray only

Rebuilding:

- Everything is kept as editable text (minutes, narration script, cut list, rules)
- Edit the text and run the same command again; only the affected parts are rebuilt

## Installation

- digesta is a standard Agent Skill (`skills/digesta/SKILL.md`), so it works with Claude Code, Codex, and other agents that support skills
- Install it only one way per agent; with both, Claude Code shows two copies of the skill

### Any agent: `npx skills`

With the [skills CLI](https://github.com/vercel-labs/skills):

```
npx skills add tell-k/digesta                 # into the current project (choose agents interactively)
npx skills add tell-k/digesta -g -a codex     # globally for Codex (~/.agents/skills/)
npx skills add tell-k/digesta -g -a claude-code
```

### Claude Code: plugin

Add the marketplace [tell-k/agent-skills](https://github.com/tell-k/agent-skills), then install the plugin.

```
/plugin marketplace add tell-k/agent-skills
/plugin install digesta@tell-k
```

- Update: `/plugin marketplace update tell-k`, then update from `/plugin`
- Load a local clone directly: `claude --plugin-dir /path/to/digesta`

## Usage

Open the project folder that contains your meeting folders (e.g. `tech-lunch/`) in your agent and invoke the skill.

- Claude Code: `/digesta` (installed with `npx skills`) or `/digesta:digesta` (installed as a plugin)
- Codex and others: mention the skill (e.g. `$digesta`)
- Plain language works too, e.g. "make the minutes for 012" or "I edited the narration, update the video"

```
/digesta <meeting-dir> [minutes|image|video|all] [--fresh] [what to change]
```

Examples:

- `/digesta tech-lunch/012`
  - Builds minutes, image, and video
- `/digesta tech-lunch/012 minutes`
  - Minutes only
- `/digesta tech-lunch/012 minutes,image`
  - Minutes and image
- `/digesta tech-lunch/012 image split by chapter too`
  - Also outputs a 16:9 image per chapter (`<name>_graphic_chN.png`), for posting one chapter per Slack thread reply
- `/digesta tech-lunch/012 video`
  - Video only; also used to rebuild after editing the text
- `/digesta tech-lunch/012 minutes also as docx`
  - Also exports the minutes as docx
- `/digesta tech-lunch/012 video make the BGM quieter`
  - Describe the change in plain words
- `/digesta tech-lunch/012 --fresh`
  - Discards the existing text and rewrites it from the source material

Rough timings:

- Minutes: a few minutes
- Image: 10–20 minutes
- Video, first build: 40–60 minutes, including reading the material and choosing cuts (the build alone is 20–30 minutes)
- Video, rebuild after a text edit: 2–10 minutes
- **Without a transcript**: the recording is transcribed from scratch first, which adds at least the length of the recording
  - A 50-minute meeting took over an hour on an Intel Mac; Apple silicon is faster
  - Bring the transcript or captions from Zoom / Teams / Google Meet whenever you can

Keeping token usage low:

- Start a new session for each meeting; continuing a long session re-reads the whole conversation on every turn
- The skill delegates writing the cut list, writing the graphic recording, and checking the result to subagents when the agent supports them (`references/agents.md`)
- Transcripts and frames are read from saved files, only the parts needed

## Requirements

### Required

- **An agent that supports Agent Skills**
  - Tested with [Claude Code](https://code.claude.com/); Codex and others should work (they need to run shell commands and read images)
- **macOS**
  - The only tested OS (Intel and Apple silicon). Linux may work but is untested
  - Narration with `say` is macOS-only
- **[uv](https://docs.astral.sh/uv/)** (`brew install uv`)
  - Runs the Python scripts; their dependencies (PyYAML, Playwright, Pillow, faster-whisper) are installed automatically
- **[ffmpeg](https://ffmpeg.org/) with libass** (`brew install ffmpeg`)
  - Audio/video processing and burned-in subtitles
- **Internet access on first run**
  - Downloads fonts (Google Fonts, OFL) to `~/.cache/digesta/fonts/`, a headless Chromium for rendering, and the local transcription model

### Required for the default video settings

- **Gemini API key**
  - Narration (Gemini TTS) and background music (Lyria). Lyria needs a key with billing enabled
  - Without it: set `external_api: deny` (narration with macOS `say`, no BGM), or `narration: voicevox` / `bgm: none`
  - Not needed for minutes or the graphic recording

### Optional

- **[pandoc](https://pandoc.org/)** (`brew install pandoc`)
  - Importing docx transcripts (e.g. Gemini notes, Teams transcripts) and exporting minutes as docx
- **Docker + [VOICEVOX engine](https://voicevox.hiroshiba.jp/)**
  - Local Japanese narration (`narration: voicevox`; a credit line is required)
  - Install: `docker run -d --name voicevox_digesta -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest`

### Gemini API key

Put it in `.env` in the project folder (e.g. `tech-lunch/`):

```
GEMINI_API_KEY=your-key
```

Lookup order (the first one found wins):

1. `.env` in the meeting folder (e.g. `tech-lunch/012/.env`)
2. `.env` in the project folder (e.g. `tech-lunch/.env`)
3. `.env` in the current working directory
4. The `GEMINI_API_KEY` environment variable
5. `~/.config/digesta/gemini.env` (either the bare key or `GEMINI_API_KEY=...`)

Notes:

- `GOOGLE_API_KEY` is also accepted in `.env`
- `digest.py status <meeting>` shows where the key was loaded from (never the key itself)
- Do not paste the key into the chat. To write it from the clipboard, run `printf 'GEMINI_API_KEY=%s\n' "$(pbpaste)" >> .env` in a terminal outside the agent
- If the folder is under git, add `.env` to `.gitignore`
- `.env` is never copied into `output/`. Remove it before sharing the whole folder

## Input

Put the following in the folder for one meeting:

- **Recording** (optional): mp4 / mov / m4v / mkv / webm, or audio only (m4a / mp3 / wav)
- **Transcript or notes**: docx (e.g. Gemini notes from Google Meet), vtt / srt (Zoom or Teams captions), txt, md
  - Without one, the whole recording is transcribed on your machine first (faster-whisper). Slow, and speakers are not distinguished

Without a video recording:

- All three deliverables can be made from a transcript or notes alone
- The digest video uses a slide per topic with narration and subtitles instead of clips of the speakers (`references/video-guide.md`, "2b. 録画がないとき")

## Folder layout

```
<project>/                     e.g. tech-lunch/
├── digesta.md                 Settings, rules and glossary shared by the project   ← edited by people
└── <meeting>/                 e.g. 012/
    ├── recording & transcript Source material. Never modified
    ├── digesta.md             Settings, rules and glossary for this meeting      ← edited by people
    ├── digest/
    │   ├── minutes.md         The minutes (source of truth)                      ← edited by people
    │   ├── grareco.html       The graphic recording                              ← edited by people
    │   ├── icons.js           Extra illustrations for this meeting               ← edited by people
    │   ├── episode.yaml       Text on the video cards                            ← edited by people
    │   ├── cuts.yaml          Video cut list and subtitles                       ← edited by people
    │   ├── narration.md       Narration script                                   ← edited by people
    │   ├── lib/               Rendering library (generated; do not edit)
    │   └── work/              Intermediate files and caches (safe to delete)
    └── output/                Deliverables
```

- `digest/` and the project/meeting `digesta.md` files are created on the first run

## Making changes

Edit the source text and run the same command again (or ask the agent in plain language).

- **Wording of the minutes**
  - Edit `digest/minutes.md`, run `minutes`
- **Wording or layout of the graphic recording**
  - Edit `digest/grareco.html`, run `image`
- **Narration wording or pronunciation**
  - Edit `digest/narration.md`, run `video`
- **Subtitles, which scenes are cut, clipped words**
  - Edit `digest/cuts.yaml`, run `video`
- **Card text (title, recap, closing notice)**
  - Edit `digest/episode.yaml`, run `video`
- **Voice, BGM on/off or volume, minutes format**
  - Edit the settings in the meeting or project `digesta.md`, run `video` / `minutes`
- **Style (hand-drawn ↔ business)**
  - Change the `style` setting and rewrite the graphic recording for that style (`grareco.<style>.html`), run `image` → `video`

Notes:

- The video rebuilds only what changed. Editing one narration sentence redoes only that card's audio and frames
- When editing YAML by hand, quote values that contain ` #` (space + hash) or `: `. Otherwise the rest of the value is lost

## Rules and settings

Rules are free-form Markdown in three layers; later layers take precedence.

| Layer | File | What goes there |
|---|---|---|
| Skill | `references/rules.md` | Rules for every meeting: handling of facts, wording, confidential information |
| Project | `<project>/digesta.md` | Meeting type, minutes format, video length, closing notice, material not to use. A final `## 用語集` (glossary) section with spellings, readings, and common mis-transcriptions of names and terms |
| Meeting | `<meeting>/digesta.md` | Same format, for conditions specific to one meeting, e.g. "don't use 12:30–14:00, a customer's screen is shown" |

Each file starts with a settings block between `---` lines. Meeting settings override project settings.

| Key | Values | Default | Description |
|---|---|---|---|
| `style` | `doodle` / `business` / `pop` / `mono`, or a style found in `styles_path` | `doodle` | Visual style |
| `styles_path` | Folder paths (`:`-separated or a list) | empty | Extra folders to search for styles. See "Custom styles" below |
| `image_model` | Model ID | `gemini-3.1-flash-image` | Used to generate `pop` characters |
| `external_api` | `ask` / `allow` / `deny` | `ask` | Whether narration scripts etc. may be sent to Gemini. See "External services" |
| `minutes_format` | `md` / `docx` / `both` | `md` | Output format of the minutes |
| `narration` | `gemini` / `voicevox` / `say` / `none` | `gemini` | How the narration is made |
| `voice` | Voice name | `Leda` | Gemini voice |
| `voice_style` | English text | A bright young narrator | Speaking-style instruction for Gemini |
| `bgm` | `lyria` / `none` / file path | `lyria` | Background music. Paths are relative to the meeting folder |
| `bgm_gain` | Number | `0.166` | Base BGM level; it ducks automatically under speech |
| `bgm_prompt` | English text | Style default | Music prompt for Lyria (doodle: cheerful ukulele, business: calm piano) |
| `clean_audio` | `true` / `false` | `true` | Light cleanup of the source audio (low-cut, mild denoise, mild compression) |
| `credit` | String | empty | Credit line at the bottom of the closing card |
| `output_dir` | Path | `output` | Where deliverables go |
| `video` | File name | auto | Which recording to use when there are several |
| `asr_prompt` | String | empty | Proper-noun hints for transcription |

## External services

- **Minutes and images**: nothing is sent out
  - The material is read by your agent session itself; what that session sends to its model provider depends on the agent
- **Video**: by default the narration script (about ten sentences summarizing the meeting) goes to Gemini TTS and the music prompt to Lyria
- **`pop` characters**: only the English appearance/pose descriptions in `digest/chars.yaml` go to Gemini image generation (no names or meeting content)
- **Consent**: asked once, the first time a project builds a video; the answer is stored as `external_api` in `digesta.md`
- **With `deny`**: narration uses macOS speech and there is no BGM. For a natural local voice, use `narration: voicevox`

## Terms and credits

- **VOICEVOX**: requires a credit (e.g. `VOICEVOX:四国めたん`) in the video or the post
  - Even for private internal use
  - The build stops if `credit` is empty
- **Gemini TTS / Lyria**: no attribution requirement was found (as of 2026-10)
  - Generated audio carries an inaudible SynthID watermark
- **Fonts** (Yusei Magic, Zen Kurenaido, Klee One, Zen Maru Gothic, Mochiy Pop One): SIL Open Font License
- **rough.js** (hand-drawn lines): MIT License, bundled as `assets/styles/*/rough.js`

## Caveats

- Automatic transcription often gets names wrong. Names that rest only on the transcript are reported as "to be confirmed" (要確認); check them
- The agent cannot hear
  - Narration pronunciation is verified by re-transcribing
  - Intonation, BGM level, and audio cleanup need a human ear
- Gemini TTS varies slightly between runs; rebuilding gives a different take of the same script
- To keep a BGM you like, copy it out of `work/` and pin it with `bgm: <path>`; setting or skill updates then won't regenerate it
- Deleting `digest/work/` clears the caches; the next video build starts from scratch (narration and BGM are regenerated)

## Custom styles

- Keep private styles (e.g. company branding) in a separate folder or repository
  - Same layout as the bundled styles (`<style>/style.yaml`, …)
- Add it to the search path in the project's `digesta.md`:

```yaml
---
styles_path: ~/src/my-digesta-themes/styles
style: mybrand
---
```

- The `DIGESTA_STYLES_PATH` environment variable works too
- Search order: `styles_path` → `DIGESTA_STYLES_PATH` → bundled styles
- How to build a style: "新しいスタイルを追加する" in `skills/digesta/references/styles.md`

## Contents

```
digesta/
├── .claude-plugin/plugin.json   Plugin manifest
├── README.md                    This file (README.ja.md: Japanese)
└── skills/digesta/
    ├── SKILL.md                 Instructions the agent follows
    ├── scripts/
    │   ├── digest.py            Build tool (init / status / minutes / image / video / narration / bgm / voices / sheet / grid / crop / frames / plan)
    │   ├── asr.py               Transcription (finding cut points, verifying audio)
    │   └── usage.py             Token usage report for a session (Claude Code only)
    ├── references/
    │   ├── rules.md             Common rules
    │   ├── agents.md            Work delegated to subagents
    │   ├── minutes-guide.md     How to write minutes
    │   ├── grareco-guide.md     How to make the graphic recording (doodle)
    │   ├── styles.md            Choosing, switching and adding styles; business-style graphic recordings
    │   └── video-guide.md       How to make the digest video
    └── assets/
        ├── styles/
        │   ├── doodle/          Hand-drawn style (illustrations, cards, video frame, graphic-recording template)
        │   ├── business/        Business style (same parts; single-color line pictograms)
        │   ├── pop/             Colorful minutes style (characters generated with Gemini)
        │   └── mono/            Yellow / black / gray style
        ├── templates/           Templates (rules, minutes, the three video texts)
        ├── examples/            A fictional study session (study/)
        └── reference.docx       Style reference for docx minutes
```

The scripts also work standalone (`<digesta>` is where this repository lives):

```bash
uv run <digesta>/skills/digesta/scripts/digest.py --help
uv run <digesta>/skills/digesta/scripts/digest.py status tech-lunch/012
uv run <digesta>/skills/digesta/scripts/digest.py minutes tech-lunch/012 --format both
uv run <digesta>/skills/digesta/scripts/digest.py video tech-lunch/012
```

- A `digesta.md` is created in the project on the first run; add your meeting type and naming conventions there

## Troubleshooting

- **Stops with "外部 API に内容を送る。…まだ確認が取れていない"** (not yet confirmed to send to an external API)
  - Set `external_api` in `digesta.md` to `allow` or `deny`
- **"Gemini の API キーがない"** (no Gemini API key)
  - Put `GEMINI_API_KEY=...` in the project's `.env`; check the source with `digest.py status`
- **Lyria returns HTTP 429 or a billing error**
  - Use a key with billing enabled, or set `bgm: none`
- **"Chromium がない"** (Chromium not found)
  - `uv run --with playwright playwright install chromium-headless-shell`
- **"VOICEVOX エンジンに繋がらない"** (cannot reach VOICEVOX)
  - Start Docker and run `docker run -d --name voicevox_digesta -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest`
- **"録画ファイルが 2 個ある"** (two recordings found)
  - Add `video: <file name>` to the meeting's `digesta.md` settings
- **Card text is cut off**
  - A YAML value contains ` #` or `: `; quote it
- **The start or end of a word is clipped**
  - In `digest/cuts.yaml`, move `start` earlier / `end` later by 0.2–0.4 s
- **Transcription is slow**
  - Slower than real time on Intel Macs. The skill transcribes only candidate ranges; use full transcription (`asr.py full`) only when needed
  - If it is interrupted, running it again resumes where it stopped (`--force` starts over)

## License

- MIT License (see `LICENSE`)
- Bundled rough.js: MIT License
- Fonts downloaded on first run: SIL Open Font License
