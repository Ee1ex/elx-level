# ELX Level

<p align="right"><a href="README.md">🌐 简体中文</a></p>

<div align="center">

<img src="assets/readme/hero.svg" alt="ELX Level: choose the right workflow depth and keep the full project memory. Four responsibility levels L1–L4 with AUTO / CONFIRM / MANUAL_ONLY execution modes" width="100%">

![Version](https://img.shields.io/badge/version-2.2-5CE8CF?labelColor=0A101C&style=flat-square)
![LEVEL](https://img.shields.io/badge/LEVEL-1--4-23405F?labelColor=0A101C&style=flat-square)
![Python](https://img.shields.io/badge/Python-3.10%2B-23405F?labelColor=0A101C&style=flat-square)
![Platform](https://img.shields.io/badge/Platform-Codex%20%7C%20Claude%20Code%20%7C%20Cursor-23405F?labelColor=0A101C&style=flat-square)
![License](https://img.shields.io/badge/License-MIT-23405F?labelColor=0A101C&style=flat-square)

**A four-level project workflow Skill built for individual developers.**
It puts LEVEL 1 / LEVEL 2 first, keeps routine progress in `AUTO`, and pauses only for decisions that truly matter in `CONFIRM` or `MANUAL_ONLY`.

[✨ Why it exists](#-what-problem-it-solves) · [⚡ Quick start](#-quick-start-in-3-minutes) · [🎚️ Four levels](#-the-four-level-model-intensity-by-responsibility) · [🧠 Project memory](#-two-layer-project-memory) · [🛡️ Safety](#-safety-boundaries-and-the-github-delivery-gate) · [📖 LEVEL.md](LEVEL.md)

</div>

## 🆕 2.2 update: lighter tasks, more reliable records

- **Scale records to task impact**: use one record for small changes; add requirements, decisions and progress for multi-stage work to reduce duplicate documentation.
- **Clearer handoff entry**: the main Skill file shrinks from 136 to 60 lines; follow the map to the current task, implementation and verification, loading detailed rules when needed.
- **Current verification evidence**: bind results to the task and file content so stale results cannot stand in for checks on new changes.
- **Safer versioning and installation**: protect staged work and version fields, validate installed files, and improve legacy-state migration and entry paths after moving a project.

The four-level model and legacy templates remain. There are 26 additional regression tests, 144 in total. A shorter entry file is not a measured reduction in tokens or elapsed time. See the [CHANGELOG](CHANGELOG.md#22---2026-09-06) for details.

## ✨ What Problem It Solves

The three most common frustrations in AI pair development:

- 🫥 **Context vanishes when the session ends** — a new session has to guess the project state from chat logs.
- 🎚️ **Workflow depth is hard to pick** — too light leaves no memory worth handing over, too heavy turns every step into an approval.
- 🚦 **Public delivery lacks a gatekeeper** — Push, PR, Merge, and releases lack a single confirmation and verification gate.

ELX Level's answer: let the **responsibility mode** set the workflow intensity — first establish who owns the project and what responsibility it carries, then decide where AI runs autonomously and where it stops for confirmation; use **two-layer project memory** so every new session continues from facts; and give all public deliveries one shared **GitHub Gate**.

## ⚡ Quick Start in 3 Minutes

This example uses Windows, Codex, a project-scoped installation, and LEVEL 1. Review the Dry Run first; confirm the LEVEL before initializing the project.

```powershell
# ① Clone this repository
git clone https://github.com/Ee1ex/elx-level.git
Set-Location elx-level

# ② Review the Dry Run first, then install for real
$ProjectPath = 'D:\path\to\your-project'
./scripts/install.ps1 -Platform codex -Scope project -ProjectPath $ProjectPath -DryRun
./scripts/install.ps1 -Platform codex -Scope project -ProjectPath $ProjectPath

# ③ Initialize LEVEL 1 and check the status
python "$ProjectPath\.codex\skills\elx-level\scripts\workflow.py" init --project $ProjectPath --level 1
python "$ProjectPath\.codex\skills\elx-level\scripts\workflow.py" status --project $ProjectPath
```

Initialization creates `.elx-level/state.json` and `docs/elx-level/STATUS.md`. Other platforms and installation scopes are covered in [📦 Install on Your Platform](#-install-on-your-platform); the complete rules for all four LEVELs live in [`LEVEL.md`](LEVEL.md) as the single authoritative source.

## 🎚️ The Four-Level Model: Intensity by Responsibility

| LEVEL | 🧭 Responsibility mode | 🎯 Best suited to | ⚙️ Default approach |
| :---: | --- | --- | --- |
| **1** 🚀 | Fast development with complete project memory | Offline tools, scripts, Skills, plugins, mods, prototypes, static pages, and versioned downloads | Implement → run → observe → adjust; small changes leave lightweight records |
| **2** 🛰️ | Complete PVS for continuous operations | Products where you own accounts, permissions, cloud data, services, deployment, backup, rollback, monitoring, or support | Full embedded PVS; `Phase 0 → Phase N`, scope freeze, and DoD, with routine phases continuing automatically |
| **3** 🤝 | Existing, team, and open-source project improvement | Other people's, team, company, or open-source repositories | Reuse Issues, PRs, CHANGELOG, and ADRs; add only a project map, Change Record, baseline, regression evidence, and handoff |
| **4** 🎛️ | Complex automation reference and routing | Large products, multi-system orchestration, complex automation, and multi-person collaboration | Analyze first, implement after owner confirmation; ten nodes as reference, external Skills routed but never embedded |

**Decision order**: contributing to a repository governed by others selects LEVEL 3 → large multi-system orchestration selects LEVEL 4 → your own ongoing operational responsibility selects LEVEL 2 → other deliverables default to LEVEL 1. Publishing your own project as open source does not alone make it LEVEL 3.

> 💡 **"Updated often" ≠ "continuously operated."** Repackaging a download or updating a static page usually remains LEVEL 1; only long-term responsibility for availability, users, permissions, data, releases, and support moves the project into LEVEL 2.

## ⚙️ How It Works

<img src="assets/readme/workflow.svg" alt="Four steps: responsibility decides depth, risk decides pause points, evidence becomes memory, and public delivery is confirmed separately" width="100%">

1. **Responsibility sets the depth.** First decide whether you are building quickly, operating continuously, improving an existing repository, or orchestrating complex automation.
2. **Risk sets the pause point.** LEVEL 1–3 expose only `AUTO`, `CONFIRM`, and `MANUAL_ONLY`; routine implementation, tests, and local commits are not gates.
3. **Evidence becomes memory.** Goals, architecture, and current facts stay stable while decisions, changes, and verification accumulate, so the next session continues from facts.
4. **Public delivery is confirmed separately.** Requested remote actions receive consolidated confirmation and remote read-back. Codex prefers its GitHub plugin; other platforms may declare an available approved connector or CLI. Tag and Release are optional, subject to repository rules.

## 🧠 Two-Layer Project Memory

<img src="assets/readme/memory.svg" alt="Two-layer project memory: the stable cognition layer answers what the project is now, the evolution record layer answers why it became this way, together supporting cross-session handoff" width="100%">

Project memory is not a document count. It means two kinds of information stay ready for handoff:

- 🏛️ The **stable cognition layer** answers "What is the project now?": goals, scope, critical paths, architecture, modules, calls, data, dependencies, build, tests, and delivery.
- 📈 The **evolution record layer** answers "Why did it become this?": Requirements, Decisions, Progress, Bugs, CHANGELOG, Release Records, and verification evidence.

LEVEL 1 establishes both layers while a small feature or edit needs only Progress/Changelog or a lightweight Change Record. LEVEL 2 adopts the full embedded PVS across product, requirements, decisions, business flow, UI, architecture, API, data, permissions, deployment, monitoring, backup, rollback, operations, Bugs, pending verification, and version history. LEVEL 3 reuses existing repository facts instead of creating a parallel documentation tree.

The complete governance rules and starter templates are embedded in [`core/project-vibe-spec/PVS.md`](core/project-vibe-spec/PVS.md), with responsibilities mapped in [`templates/template-map.json`](templates/template-map.json); installing this package does not require downloading a second PVS Skill.

## 🛡️ Safety Boundaries and the GitHub Delivery Gate

⛔ **These actions always require confirmation**: bulk deletion, production data, secrets, payments, account permissions, irreversible migration, security reduction, production deployment, public publishing, outbound messages, Merge, and Release.

🚫 **Permanently forbidden**: Force Push and rewriting public history.

🔁 **Every LEVEL uses the same GitHub delivery contract**: the declared GitHub tool first reads the remote state read-only and presents the branch and commits, file scope, test evidence, PR, Merge, Tag/Release, rollback, and unverified items before requesting one remote-operation confirmation. **A success message is not completion** — the result must be read back through the declared tool.

## 📦 Install on Your Platform

Codex, Claude Code, and Cursor are supported:

```powershell
./scripts/install.ps1 -Platform codex -Scope user -DryRun
./scripts/install.ps1 -Platform cursor -Scope project -ProjectPath 'D:\path\to\project' -DryRun
```

```sh
./scripts/install.sh --platform claude-code --scope user --dry-run
./scripts/install.sh --platform claude-code --scope user
```

Adapters reference only the current LEVEL, state, and layering strategy instead of copying the complete workflow. The updater runs Doctor first, explicitly migrates project state, and creates a timestamped backup before replacing the installation. The uninstaller removes only `elx-level` and preserves `.elx-level/`, `docs/elx-level/`, the legacy `.project-workflow/`, and the legacy Skill installation by default.

## 🔄 Migrating from Older Versions

- 📦 `migrate` copies the complete legacy `.project-workflow` directory to `.elx-level` and leaves the source unchanged; when both directories exist, only a recorded matching migration-source digest permits reuse; otherwise it stops without overwriting either.
- 🔢 LEVEL 1–4 from `0.4.0` keep their numeric meaning, while the old LEVEL 4 remains at its analysis boundary awaiting execution confirmation; older states migrate by protocol: old LEVEL 1 → new LEVEL 1, old LEVEL 2 → new LEVEL 3, and old LEVEL 3 → new LEVEL 4.
- 💾 Before migrating, a `state.backup.json` is written and `STATUS.md` records the old/new level, schema, and reason.

The current version is `2.2`. This repository does not create GitHub Releases or automatically change tags. Updates are recorded in CHANGELOG.

## 🗂️ Repository Layout

```text
elx-level/
├── 📄 SKILL.md                 # Skill entry and trigger rules
├── 📄 LEVEL.md                 # Single authoritative four-level model
├── 📁 adapters/                # Codex · Claude Code · Cursor adapters
├── 📁 core/project-vibe-spec/  # Embedded PVS governance core
├── 📁 references/              # State protocol · risk permissions · routing contracts
├── 📁 templates/               # level1–4 + common templates
├── 📁 schemas/                 # workflow-state.schema.json
├── 📁 scripts/                 # workflow.py · install/update/uninstall
├── 📁 evals/ · tests/          # Chinese scenario evals and unit tests
└── 📁 assets/readme/           # README visual assets
```

## 🧪 Development and Verification

Development verification depends only on the Python 3.10+ standard library:

```sh
python -m unittest discover -s tests -v
python scripts/workflow.py doctor --package-root .
python scripts/workflow.py validate-package --package-root .
```

## 📄 License

This project is released under the [MIT License](LICENSE).

<div align="center">
<sub><b>ELX Level</b> — choose the right workflow intensity and keep the full project memory · <a href="#-elx-level">⬆ Back to top</a></sub>
</div>
