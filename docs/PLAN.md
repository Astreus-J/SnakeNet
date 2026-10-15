# SnakeNet — Plan: cycles and tasks

Deadline: **2026-10-28**. Last updated 2026-10-15. Source of truth for sync: [`project-management/plane/plan.json`](../project-management/plane/plan.json) (same IDs `SN-n`).

> **Plane sync: NOT done.** No `PLANE_API_KEY`/`PLANE_BASE_URL`/project identifier values exist in this environment (the JuriSense repo only names the variables; `~/.config/Plane` is the desktop app's browser cache, which was deliberately not mined for session tokens). Once you export the four variables: `python tools/plane_sync.py` (dry run) then `python tools/plane_sync.py --apply`. Use a project dedicated to SnakeNet.

"done" means written **and** covered by the observed `pytest` run (59 passed) or an observed real run, unless the row says otherwise.


## Cycle 1 - Networking core (2026-10-15 → 2026-10-17)

| ID | Task | Status |
|---|---|---|
| SN-1 | Inspect repository and assignment PDF | ✅ done |
| SN-2 | Protocol package: schemas, validators, codec, limits | ✅ done |
| SN-3 | Game simulation (pure domain) | ✅ done |
| SN-4 | UDP server: sessions, validation, tick loop, expiry | ✅ done |
| SN-5 | Client network layer (thread, join retry, stale drop, lost detection) | ✅ done |
| SN-6 | Repository configuration (git, .gitignore, deps, pytest) | ✅ done |

## Cycle 2 - Playable game and tests (2026-10-18 → 2026-10-21)

| ID | Task | Status |
|---|---|---|
| SN-7 | pygame UI: arena, snakes, food, leaderboard, status banner | ✅ done |
| SN-8 | Bot client for demos and captures | ✅ done |
| SN-9 | Automated tests for the 14 required scenarios | ✅ done |
| SN-10 | Headless UI smoke test + screenshot | ✅ done |
| SN-11 | Multi-client localhost run observed | ✅ done |

## Cycle 3 - Evidence and docs (2026-10-22 → 2026-10-25)

| ID | Task | Status |
|---|---|---|
| SN-12 | README with all PDF-required items | ✅ done |
| SN-13 | Protocol specification | ✅ done |
| SN-14 | Architecture diagram | ✅ done |
| SN-15 | Wireshark guide and capture helper | ✅ done |
| SN-16 | Real Wireshark capture and screenshots into evidence/ | 🧍 todo (needs team) |
| SN-17 | LAN test with a second machine (record real IPs/ports) | 🧍 todo (needs team) |
| SN-18 | Compliance traceability table | ✅ done |

## Cycle 4 - Presentation and buffer (2026-10-26 → 2026-10-28)

| ID | Task | Status |
|---|---|---|
| SN-19 | Presentation plan and Q&A | ✅ done |
| SN-20 | Rehearse 10-minute demo; every member explains the code | 🧍 todo (needs team) |
| SN-21 | Final check of documented commands on a clean venv | ⬜ todo |
| SN-22 | Fill team member names in README | 🧍 todo (needs team) |
| SN-23 | Optional: boost, sound, menu (only if everything else is done) | ⬜ todo |

## Remaining work (all need the team)
1. **SN-16 Wireshark capture** — the only missing mandatory deliverable; follow [WIRESHARK.md](WIRESHARK.md).
2. SN-17 LAN test on two machines, SN-20 rehearsal, SN-22 team names, SN-21 clean-venv check.

## Risks
| Risk | Mitigation |
|---|---|
| No capture rights in dev sandbox | Capture on a team machine; procedure and filters ready; evidence must be genuine |
| Firewall blocks inbound UDP 5000 on LAN demo | Test early (SN-17); fall back to localhost demo |
| Loopback interface choice in Wireshark | Documented (`lo` / Npcap Loopback Adapter) |
| Snapshot size growth | Caps (8 players, length 40, food ≤ target+10) + worst-case size test |
| pygame wheel without fonts on Python 3.14 | Switched to `pygame-ce` (documented in README) |
