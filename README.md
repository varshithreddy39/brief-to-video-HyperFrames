<div align="center">

# brief-to-video — HyperFrames

**Plain-language brief → structured plan → verified MP4. No human in the loop.**

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI%20SDK-latest-412991?logo=openai&logoColor=white)
![HyperFrames](https://img.shields.io/badge/HyperFrames-0.8.27-black)
![GSAP](https://img.shields.io/badge/GSAP-3.12.5-88CE02?logo=greensock&logoColor=white)

</div>

---

An end-to-end generator that turns a plain-language creative brief into a validated MP4 motion-graphics advertisement. It plans first with `gpt-5.5`, generates only the imagery that materially improves the story with `gpt-image-2`, compiles a deterministic HyperFrames composition, runs the HyperFrames verification gate, repairs failures up to a fixed cap, renders an MP4, and verifies the rendered file before returning success.

The printable planning artifact for every run is `plan.json`. The wider engineering rationale is in [Planning and System Design](docs/PLANNING_AND_SYSTEM_DESIGN.md).

---

## 🎬 Output Videos

Both renders were produced end-to-end — planned by `gpt-5.5`, composed deterministically, passed the mandatory HyperFrames gate, and validated by `ffprobe` before being written to disk.

> **Run `41083e755fe13009`**
> *"Create a 26-second widescreen video about an AI productivity assistant that helps teams work smarter."*
> → [output.mp4](runs/41083e755fe13009/renders/output.mp4) · [plan.json](runs/41083e755fe13009/plan.json) · [gate result](runs/41083e755fe13009/checks/attempt_0.json)

> **Run `d4b95c79d1266dbb`**
> *"Create a cinematic 20-second widescreen advertisement for an AI meeting assistant that turns chaotic meetings into clear action plans."*
> → [output.mp4](runs/d4b95c79d1266dbb/renders/output.mp4) · [plan.json](runs/d4b95c79d1266dbb/plan.json) · [gate result](runs/d4b95c79d1266dbb/checks/attempt_0.json)

---

## How it works

1. Accepts a short natural-language brief
2. Uses `gpt-5.5` structured output to produce a typed `VideoPlan` before any code or assets are generated
3. Validates that plan semantically — timings, dimensions, assets, text, motion, and assertions
4. Uses `gpt-image-2` only where a generated image materially improves the visual story
5. Deterministically compiles supported scenes and GSAP motion into a HyperFrames composition
6. Runs `npx hyperframes check <composition> --json` on every generated composition
7. Sends gate failures to a capped `gpt-5.5` repair loop — recompiles and rechecks after each repair
8. Renders only after the gate reports `ok: true`, then validates the MP4 with `ffprobe`

---

## Architecture

```mermaid
flowchart TD
    B[Plain-language brief] --> P[Planning agent<br/>gpt-5.5]
    P --> PA[plan.json<br/>printable VideoPlan artifact]
    PA --> PV[Semantic plan validator]
    PV -->|invalid/unusable| PR[Planning retry<br/>bounded]
    PR --> P
    PV -->|valid| AP[Asset planner<br/>gpt-image-2]
    AP --> AR[Deterministic asset cache<br/>and registry]
    AR --> CC[Deterministic compiler<br/>HTML + CSS + GSAP]
    PA --> CC
    CC --> HC[HyperFrames gate<br/>check --json]
    HC -->|issues| RL[Repair agent<br/>gpt-5.5]
    RL -->|repaired plan| PV
    RL -->|repair cap reached| F[Fail loudly<br/>artifacts + findings]
    HC -->|ok: true| R[HyperFrames render<br/>MP4]
    R --> MV[MP4 verifier<br/>duration · FPS · size]
    MV -->|invalid| F
    MV -->|valid| S[✅ Success<br/>MP4 + complete artifacts]
```

The **compiler** owns implementation detail — typography, safe layout zones, responsive 16:9 / 9:16 / 1:1 treatments, motion easing, and image-safe camera drift. The **model** owns the creative plan — message, scene sequence, copy, imagery intent, timing, and motion intent. This boundary prevents the model from emitting arbitrary HTML/CSS/JS while still giving every brief a distinct visual story.

---

## Setup

### Prerequisites

- Python 3.11+ (tested with Python 3.12)
- Node.js 22+ (`hyperframes` requires Node 22 or newer)
- Docker Desktop running (the pipeline renders with `--docker`)
- An OpenAI-compatible API key with access to `gpt-5.5` and `gpt-image-2`

### Install

```bash
git clone https://github.com/varshithreddy39/brief-to-video-HyperFrames.git
cd brief-to-video-HyperFrames

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

npm ci

cp .env.example .env
# edit .env and add your OPENAI_API_KEY
```

---

## Run a brief

```bash
python -c "
from app.orchestrator.pipeline import run_pipeline
r = run_pipeline('Create a 12 second ad for a developer tool, dark theme, purple accent, three feature callouts, ends on a call to action.')
print('HyperFrames gate:', r.hyperframes_check.ok)
print('MP4 valid:', r.mp4_validation.ok)
print('Output:', r.output_path)
"
```

On success both gates print `True` and the MP4 path is returned. The full run is stored under `runs/<sha256-of-brief>/`.

---

## Verification and repair

The HyperFrames gate is mandatory. The pipeline **does not** render until it receives `{"ok": true}` from:

```bash
npx hyperframes check runs/<run_id>/composition --json
```

When the gate reports issues, the pipeline normalises and prioritises the findings, asks `gpt-5.5` for a repaired `VideoPlan`, revalidates, recompiles, and reruns the gate. `MAX_REPAIR_ATTEMPTS` defaults to `3`. Exceeding the cap raises `PipelineError` with the run directory and remaining diagnostics — a failed video is never returned as success.

---

## Determinism

The normalised brief is SHA-256 hashed to derive its run directory. Repeating the same brief reuses the saved `plan.json` and cached asset files, then recompiles the same deterministic composition. There is no randomness in layout, copy, or asset-cache keys.

---

<details>
<summary><strong>Artifacts produced by every run</strong></summary>

```text
runs/<run_id>/
├── brief.txt                   # normalised source brief
├── plan.json                   # printable GPT-5.5 structured plan
├── assets/
│   ├── registry.json           # asset ID → deterministic cached file
│   └── *.png                   # gpt-image-2 output where needed
├── composition/
│   ├── index.html
│   ├── styles.css
│   ├── timeline.js
│   └── index.motion.json
├── checks/
│   ├── attempt_0.json          # HyperFrames check result
│   ├── attempt_1.json          # present only after repair
│   └── mp4.json                # post-render verifier result
├── renders/
│   └── output.mp4
└── logs/
    ├── pipeline.log
    └── render.log
```

Two complete runs are committed to this repository:
- [`runs/41083e755fe13009/`](runs/41083e755fe13009/)
- [`runs/d4b95c79d1266dbb/`](runs/d4b95c79d1266dbb/)

All other run output is git-ignored.

</details>

<details>
<summary><strong>Scope deliberately cut</strong></summary>

This project focuses on the core: creative planning, deterministic composition, self-verification, bounded repair, and reproducible artifacts.

| Cut | Reason |
|-----|--------|
| Cloud deployment / queue workers | Local artifact-rich execution is sufficient to prove the core workflow |
| Browser UI | A CLI provides the clearest reproducible demonstration |
| Voiceover, music, TTS | Introduces timing, licensing, and mixing concerns unrelated to the visual planning problem |
| Arbitrary product screenshots | Adds account/secrets management and makes deterministic reruns less reliable |
| Unlimited self-repair | A bounded, artifact-rich failure is more honest and debuggable than infinite retries |

</details>

---

## License

MIT © Varshith Reddy Mettukuru
