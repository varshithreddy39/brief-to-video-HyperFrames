<div align="center">

# brief-to-video · HyperFrames

*Type a brief. Get a verified MP4. No human in the loop.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev)
[![OpenAI SDK](https://img.shields.io/badge/OpenAI%20SDK-latest-412991?logo=openai&logoColor=white)](https://github.com/openai/openai-python)
[![HyperFrames](https://img.shields.io/badge/HyperFrames-0.8.27-000000)](https://www.npmjs.com/package/hyperframes)
[![GSAP](https://img.shields.io/badge/GSAP-3.12.5-88CE02?logo=greensock&logoColor=white)](https://gsap.com)

</div>

---

An end-to-end pipeline that turns a plain-language creative brief into a validated MP4 motion-graphics advertisement — `gpt-5.5` plans the composition, `gpt-image-2` generates imagery, HyperFrames compiles and renders it, and the system verifies its own output before declaring success.

→ Full engineering rationale: [Planning and System Design](docs/PLANNING_AND_SYSTEM_DESIGN.md)

---

## Output Videos

Two complete runs — each passed the HyperFrames gate and `ffprobe` validation end-to-end.

<table>
<tr>
<td width="50%" valign="top">

**Run 1 · `41083e755fe13009`**

*26-second widescreen — AI productivity assistant*

[▶ output.mp4](runs/41083e755fe13009/renders/output.mp4)

[plan.json](runs/41083e755fe13009/plan.json) · [gate check](runs/41083e755fe13009/checks/attempt_0.json) · [mp4 check](runs/41083e755fe13009/checks/mp4.json)

</td>
<td width="50%" valign="top">

**Run 2 · `d4b95c79d1266dbb`**

*20-second widescreen — AI meeting assistant*

[▶ output.mp4](runs/d4b95c79d1266dbb/renders/output.mp4)

[plan.json](runs/d4b95c79d1266dbb/plan.json) · [gate check](runs/d4b95c79d1266dbb/checks/attempt_0.json) · [mp4 check](runs/d4b95c79d1266dbb/checks/mp4.json)

</td>
</tr>
</table>

---

## How It Works

| Step | What happens |
|------|-------------|
| **1. Plan** | `gpt-5.5` turns the brief into a typed `VideoPlan` — scenes, timings, copy, motion intent, asset specs |
| **2. Validate** | Semantic validator checks timings, dimensions, assets, and motion before anything is generated |
| **3. Generate assets** | `gpt-image-2` produces imagery only where it materially improves the visual story |
| **4. Compile** | Deterministic compiler turns the plan into HTML + CSS + GSAP — no model-authored code |
| **5. Gate check** | `npx hyperframes check --json` — blocks rendering if `ok` is not `true` |
| **6. Repair** | Gate failures go back to `gpt-5.5`, which repairs the plan; capped at `MAX_REPAIR_ATTEMPTS` |
| **7. Render** | HyperFrames renders the checked composition to MP4 |
| **8. Verify** | `ffprobe` confirms duration, dimensions, and FPS match the plan |

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

---

## Setup

**Prerequisites**
- Python 3.11+ (tested with 3.12)
- Node.js 22+
- Docker Desktop running
- An OpenAI-compatible API key for `gpt-5.5` and `gpt-image-2`

```bash
git clone https://github.com/varshithreddy39/brief-to-video-HyperFrames.git
cd brief-to-video-HyperFrames

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
npm ci

cp .env.example .env
# → add your OPENAI_API_KEY to .env
```

---

## Run

```bash
python -c "
from app.orchestrator.pipeline import run_pipeline
r = run_pipeline('Your brief here.')
print('Gate:', r.hyperframes_check.ok)
print('MP4: ', r.mp4_validation.ok)
print('File:', r.output_path)
"
```

Both gates print `True` on success. The full run is saved under `runs/<sha256-of-brief>/`.

---

## Verification & Repair

The gate is mandatory — the pipeline never renders without `{"ok": true}` from:

```bash
npx hyperframes check runs/<run_id>/composition --json
```

When issues are found, `gpt-5.5` repairs the plan, it revalidates, recompiles, and the gate runs again. Exceeding `MAX_REPAIR_ATTEMPTS` raises `PipelineError` with the run directory and unresolved findings — a broken video is never returned as success.

---

## Determinism

The normalised brief is SHA-256 hashed to produce the run directory. Repeating the same brief reuses the saved plan and cached assets, then recompiles the same deterministic composition. No randomness anywhere in the pipeline.

---

<details>
<summary>Run artifact structure</summary>

```
runs/<run_id>/
├── brief.txt
├── plan.json
├── assets/
│   ├── registry.json
│   └── *.png
├── composition/
│   ├── index.html
│   ├── styles.css
│   ├── timeline.js
│   └── index.motion.json
├── checks/
│   ├── attempt_0.json
│   └── mp4.json
├── renders/
│   └── output.mp4
└── logs/
    ├── pipeline.log
    └── render.log
```

</details>

<details>
<summary>Scope deliberately cut</summary>

| Cut | Reason |
|-----|--------|
| Cloud deployment | Local execution is sufficient to demonstrate the pipeline |
| Browser UI | CLI keeps the demo reproducible and focused |
| Voiceover / TTS | Adds timing and licensing complexity unrelated to the core problem |
| Unlimited repair | Bounded failure is more honest and debuggable than infinite retries |

</details>

---

<div align="center">

MIT © Varshith Reddy Mettukuru

</div>
