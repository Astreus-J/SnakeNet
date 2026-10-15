# Academic compliance traceability

Legend: ✅ yes · 🟡 partly · ⬜ no. **Implemented** = code exists; **Tested** = automated test or observed run; **Documented**; **Demonstrated** = shown live/with real evidence (still pending for everything that needs the team).
Nothing is marked fully satisfied just because a file exists. Test results: `pytest` → 59 passed (observed).

| Criterion (pts) | Implementation | Tests | Docs | Impl. | Tested | Docs | Demo | Gap |
|---|---|---|---|---|---|---|---|---|
| Client-server functionality (2.0) | `server/app.py`, `game/world.py`, `client/network.py`, `client/ui.py` | `tests/server/test_server.py`, `tests/client/test_network.py`, `tests/game/test_world.py`, `tests/client/test_ui_smoke.py`; observed localhost run with 2 bots + UI | README §8 | ✅ | ✅ | ✅ | 🟡 | Human-played session and LAN run not done |
| Socket implementation (1.5) | `server/app.py` (`socket`, `bind`, `recvfrom`, `sendto`, timeout loop), `client/network.py` (socket + thread) | port-in-use, shutdown-releases-socket, client close, many-clients-not-blocking tests | README §3–4, ARCHITECTURE | ✅ | ✅ | ✅ | ⬜ | Show code live |
| Application protocol (1.5) | `snakenet/protocol/` (schemas, validators, codec, limits, errors) | `tests/protocol/test_codec.py` (18 malformed cases, size cap) + server tests | `docs/PROTOCOL.md`, README §5 | ✅ | ✅ | ✅ | ⬜ | — |
| TCP/UDP justification (1.5) | design choice (UDP) + reliability layer: seq numbers, retries, idempotent JOIN/LEAVE | duplicate JOIN, duplicate/reordered INPUT, stale STATE tests | README §3, PROTOCOL §6, PRESENTATION | ✅ | ✅ | ✅ | ⬜ | Team must be able to defend it orally |
| Error handling (1.0) | validation in `protocol/`, `server/app.py`, `throttle.py`, `sessions.py`, client state machine | malformed traffic, rate limits, expiry, full server, unavailable server, unresolvable host, lost→recover | README §6, PROTOCOL §4–5 | ✅ | ✅ | ✅ | ⬜ | Loss/latency not measured on a real impaired link |
| Code organization (0.5) | layered packages, tests mirror packages | — | ARCHITECTURE (layering table) | ✅ | n/a | ✅ | n/a | — |
| Documentation (0.5) | README, PROTOCOL, ARCHITECTURE, WIRESHARK, PRESENTATION, PLAN, this file | — | — | ✅ | n/a | 🟡 | n/a | Team names are placeholders |
| Presentation (0.5) | plan in `docs/PRESENTATION.md` | — | ✅ | 🟡 | n/a | ✅ | ⬜ | Rehearsal pending |
| Conceptual understanding (1.0) | Q&A prepared in PRESENTATION.md | — | ✅ | n/a | n/a | ✅ | ⬜ | Every member must study it |

## Mandatory deliverables
| Deliverable | State |
|---|---|
| 1. Source code (client + server) | ✅ present, tested |
| 2. README with all required items (description, members, architecture, TCP/UDP, justification, IP/port, protocol, messages, run instructions) | ✅ present; **members are placeholders** |
| 3. Architecture diagram | ✅ [ARCHITECTURE.md](ARCHITECTURE.md) (Mermaid) |
| 4. Wireshark capture and analysis | ⬜ **not delivered yet** — procedure and filters ready in [WIRESHARK.md](WIRESHARK.md); must be captured on a machine with capture rights |

## The 10 questions from the assignment → where answered
1 problem → README §1 · 2 processes → README §2 · 3 how they communicate → ARCHITECTURE sequence + PROTOCOL · 4 transport → README §3 · 5 why suitable → README §3 / PRESENTATION · 6 application protocol → PROTOCOL.md · 7 messages → README §5 / PROTOCOL §4 · 8 what if the other protocol → README §3 / PRESENTATION · 9–10 errors and handling → README §6.
