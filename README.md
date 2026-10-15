# SnakeNet

Original desktop multiplayer snake arena built on **raw UDP sockets** (Python `socket` + pygame).
Trabalho de *Fundamentos de Redes de Computadores* — "Desenvolvimento de Aplicação em Rede utilizando Sockets" (entrega: 28/10/2026).

## Team / Integrantes
| Name | Role |
|---|---|
| _[TODO: nome 1]_ | _[TODO]_ |
| _[TODO: nome 2]_ | _[TODO]_ |
| _[TODO: nome 3]_ | _[TODO]_ |

## 1. The problem and the solution
**Problem:** several people on different machines want to play in the *same* real-time world, which needs low-latency communication between processes and one consistent view of the game.
**Solution:** a **server** process owns the world (authoritative) and simulates 12 steps/s; each **client** process sends only keyboard *inputs* and renders the *snapshots* it receives. Eating food grows the snake and raises the score; hitting a wall or a snake body kills; a leaderboard ranks players.
(*PT:* o servidor decide tudo; o cliente só envia teclas e desenha o estado recebido.)

## 2. Architecture
Diagram and sequence: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (Mermaid, renders on GitHub/VS Code).

```
 client A ──UDP──┐                         ┌── server/app.py  (socket bind, recv → validate → dispatch)
 client B ──UDP──┼──►  <SERVER_IP>:5000 ───┤── server/sessions.py (token + address, rate limit)
 client C ──UDP──┘   ◄── STATE @ 12 Hz ────└── game/world.py   (authoritative simulation)
```
* **Processes:** `snakenet.server` (1 per match) and `snakenet.client` / `snakenet.client.bot` (N).
* **Server:** binds UDP, validates every datagram, keeps sessions, simulates, broadcasts `STATE`, expires idle sessions.
* **Client:** own UDP socket + network thread (never blocks rendering), JOIN with retries, sends inputs, drops stale snapshots, shows connection status.
* **Layout:** `snakenet/protocol/` (wire contract) · `game/` (pure rules) · `server/` · `client/` · `tests/` mirrors it · `docs/` · `tools/` · `evidence/`.

## 3. Transport: UDP — and why
Chosen: **UDP** (`SOCK_DGRAM`). Real-time state is *replaceable*: the next snapshot (≈83 ms later) makes a lost one irrelevant, so TCP's retransmission and in-order delivery would only add **head-of-line blocking** and latency. UDP also needs no handshake and preserves message boundaries (one datagram = one message). We add only the reliability that matters (sequence numbers, bounded JOIN retries, idempotent control messages, timeouts) — see [PROTOCOL.md §6](docs/PROTOCOL.md).
**If TCP were used instead:** we would need explicit message framing (length prefix) on a byte stream, one connection per player with a 3-way handshake, the kernel would retransmit stale positions and stall newer ones behind a lost segment, and Nagle/`TCP_NODELAY` tuning would be needed. TCP would be the right choice for login, chat or file transfer. Details in [docs/PRESENTATION.md](docs/PRESENTATION.md).
UDP is **not** reliable or ordered; limitations are listed in §10.

## 4. IP address and port (configurable)
| Setting | Server | Client |
|---|---|---|
| Address | `--host` (default `127.0.0.1`; `0.0.0.0` = all interfaces) or env `SNAKENET_HOST` | `--host` (server's IP or name) or `SNAKENET_HOST` |
| Port | `--port` (default **UDP 5000**) or env `SNAKENET_PORT` | `--port` |
Other server options: `--tick-rate` (12), `--snapshot-rate` (12), `--session-timeout` (5 s, ≥ 0.5), `--max-players` (8), `--seed`. Limits live in `snakenet/config.py` and `snakenet/protocol/limits.py`.

## 5. Application protocol and messages
Full specification (fields, validation, errors, examples): **[docs/PROTOCOL.md](docs/PROTOCOL.md)**. One UTF-8 JSON object per datagram: `{"v":1,"t":"<TYPE>",...}`.

| Type | Dir | Purpose |
|---|---|---|
| `JOIN` | C→S | request to enter the match |
| `WELCOME` | S→C | admission: `pid`, session `tok`, arena size |
| `INPUT` | C→S | direction `U/D/L/R` + sequence number |
| `STATE` | S→C | authoritative snapshot (snakes, food, scores), `seq` for staleness |
| `PING` / `PONG` | C→S / S→C | keep-alive and RTT |
| `LEAVE` | C→S | leave (idempotent) |
| `ERROR` | S→C | structured error `code` + `msg` |

Examples:
```json
{"v":1,"t":"JOIN","name":"ana"}
{"v":1,"t":"WELCOME","pid":1,"tok":"9f2c4a1b7e0d5c33","w":60,"h":40,"tick_rate":12.0,"timeout":5.0}
{"v":1,"t":"INPUT","tok":"9f2c4a1b7e0d5c33","seq":17,"dir":"U"}
{"v":1,"t":"ERROR","code":"BAD_FIELD","msg":"INPUT.dir: expected one of ('U', 'D', 'L', 'R')","ref":"INPUT"}
```

## 6. Error handling (what can go wrong → what happens)
| Situation | Handling |
|---|---|
| Server not running / unreachable | Client retries JOIN 5× (0.5 s) then shows **FAILED: server unavailable** (no crash); `R` retries |
| Hostname can't be resolved | Immediate FAILED with message |
| Port in use / bad bind | Server prints `cannot bind UDP host:port: …`, exit code 2 |
| Invalid JSON, wrong version, unknown type, missing/invalid fields, oversize datagram | Rejected before touching game state; `ERROR` reply (≤ 5/s per address); throttled log line |
| Inputs: reversal, bad direction, flood | Reversal/invalid ignored; flood limited by a token bucket → `RATE_LIMITED` |
| Duplicate / reordered `INPUT`, retried `JOIN`, repeated `LEAVE` | Idempotent: ignored or same `WELCOME` re-sent; never executes twice |
| Stale / duplicate `STATE` | Client drops it (`seq` ≤ last applied) |
| Lost datagrams | Next `STATE` supersedes; inputs sent twice |
| Wrong/forged token or token from another address | `BAD_SESSION`, no state change |
| Client vanishes | Server expires the session after the timeout and frees the snake |
| Server vanishes / restarts | Client: no data for 2 s → **LOST**, auto re-JOIN; on `SERVER_SHUTDOWN` → FAILED |
| Server full | `SERVER_FULL` shown to the player |
| Unexpected exceptions | Caught per datagram / per tick; server keeps running |

## 7. Prerequisites and setup
Python 3.10+ (developed on 3.14).
```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt        # Windows: .venv\Scripts\pip ...
```
Dependency note: `pygame-ce` (same `import pygame` API) is used because the plain `pygame 2.6.1` wheel for Python 3.14 shipped **without its font module**. The server, protocol, game and network client use only the standard library.

## 8. Running
```bash
# Terminal 1 – server
.venv/bin/python -m snakenet.server --host 127.0.0.1 --port 5000

# Terminals 2, 3, … – clients (arrow keys / WASD, R = reconnect, Esc = quit)
.venv/bin/python -m snakenet.client --host 127.0.0.1 --port 5000 --name ana
.venv/bin/python -m snakenet.client --host 127.0.0.1 --port 5000 --name bob

# Optional – headless bots for demos/captures
.venv/bin/python -m snakenet.client.bot --port 5000 --name bot1 --duration 60
tools/demo_local.sh            # server + 2 bots
```
**Several clients on one computer:** run the client command in several terminals; each gets its own ephemeral source port.
**Over a local network:** on the server machine run `--host 0.0.0.0 --port 5000`, find its LAN IP (`ip addr` / `ipconfig`), allow inbound **UDP 5000** in the firewall, and on other machines run `python -m snakenet.client --host <SERVER_LAN_IP> --port 5000`. *LAN play across two real machines has not been tested yet; internet play is not supported/tested.*

## 9. Tests and Wireshark
```bash
.venv/bin/python -m pytest          # protocol, game rules, server (real UDP on localhost), client, headless UI
```
Wireshark capture and analysis: **[docs/WIRESHARK.md](docs/WIRESHARK.md)** (filter `udp.port == 5000`). Assignment traceability: **[docs/COMPLIANCE.md](docs/COMPLIANCE.md)**; presentation: **[docs/PRESENTATION.md](docs/PRESENTATION.md)**; schedule: **[docs/PLAN.md](docs/PLAN.md)**.

## 10. Known limitations
* UDP: no delivery guarantee; a fully lost key press is simply lost. No encryption; tokens are readable on the wire. IPv4 only; one match per server; no persistence.
* Simultaneous moves: two heads swapping adjacent cells do not collide. Max 8 players, snake length ≤ 40 (keeps `STATE` ≤ 1472 B, tested at the worst case).
* Client accepts server datagrams only from the exact IP:port it sent to (a multi-homed server replying from another IP would be ignored).
* Network-condition behaviour (loss/latency) is covered by logic tests, not yet measured with `tc netem`.

## 11. Verification status (honest summary)
| Item | Status |
|---|---|
| Automated tests | **59 passed** (last run: `pytest`, 5 s). See COMPLIANCE.md for the mapping |
| Real run: server + 2 bots + headless UI client on localhost, graceful SIGTERM stop | Observed OK (screenshot: `evidence/screenshot-headless.png`) |
| Interactive play with a human on a real window | **Not yet done** (needs a desktop session) |
| LAN test between two machines | **Not yet done** |
| Wireshark capture / screenshots | **Not yet done** — blocked in the dev sandbox; procedure in docs/WIRESHARK.md |
| Packet-loss experiment (`tc netem`) | Not run |
