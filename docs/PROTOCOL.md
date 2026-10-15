# SnakeNet Application Protocol — version 1

Transport: **UDP** (IPv4). Default server port: **UDP 5000** (configurable).
Encoding: one **UTF-8 JSON object per datagram**. Source of truth: [`snakenet/protocol/`](../snakenet/protocol/).

> UDP is **not** reliable or ordered. Every rule below that sounds like reliability (sequence numbers,
> retries, idempotency) is implemented by the *application* on top of best-effort datagrams.

## 1. Framing

UDP keeps message boundaries: one `sendto` produces exactly one `recvfrom`. Therefore each datagram holds
exactly one message, and **no length prefix or delimiter is needed** (TCP, a byte stream, would need one).

## 2. Envelope

```json
{"v": 1, "t": "INPUT", "...": "type-specific fields"}
```

| Field | Type | Rule |
|---|---|---|
| `v` | int | Must equal `1`. Missing → `BAD_FIELD`; other value → `BAD_VERSION`. |
| `t` | string | One of the types below **and** valid for the direction it was sent in, else `BAD_TYPE`. |

Unknown extra fields are ignored and dropped. Booleans are never accepted as integers.

## 3. Limits

| Limit | Value | Reason |
|---|---|---|
| Client → server datagram | ≤ 1024 bytes | Real messages are < 150 B; bounds parse cost. Larger → `TOO_LARGE`. |
| Server → client datagram | ≤ 1472 bytes | 1500 (Ethernet MTU) − 20 (IPv4) − 8 (UDP): never IP-fragmented. |
| Player name | 1–12 printable chars | |
| Session timeout | 5 s of silence (`--session-timeout`) | |
| INPUT rate | 30/s sustained, burst 30 (per session) | Token bucket. |
| ERROR replies | ≤ 5/s per source address | Limits reflection and log spam. |

## 4. Messages

Direction: **C→S** client to server, **S→C** server to client. `tok` is the 16-hex-char session token.

### JOIN (C→S)
`{"v":1,"t":"JOIN","name":"ana"}` — request to enter the match. Retried by the client every 0.5 s, up to 5 times.
Server: creates a session (new `pid`, random `tok`) and replies `WELCOME`; if that address already has a
session the same `WELCOME` is re-sent (**idempotent**, no duplicate player). Full match → `ERROR SERVER_FULL`.

### WELCOME (S→C)
`{"v":1,"t":"WELCOME","pid":3,"tok":"9f2c4a1b7e0d5c33","w":60,"h":40,"tick_rate":12,"timeout":5}`
`pid` is the player id, `tok` must accompany every later client message, `w`/`h` arena size in cells,
`timeout` tells the client how fast it must send keep-alives (it pings every `timeout/3`).

### INPUT (C→S)
`{"v":1,"t":"INPUT","tok":"9f2c4a1b7e0d5c33","seq":17,"dir":"U"}` — `dir` ∈ `U D L R`.
`seq` is a per-client counter that increases with every new key press. The server accepts an INPUT only if
`seq` > last accepted `seq` for that session, so **duplicates and reordered datagrams are ignored**. The client
deliberately sends each press **twice with the same `seq`** to tolerate loss; the second copy is dropped as a
duplicate. A reversal (e.g. `L` while moving `R`) is validated and ignored. Clients never send positions.

### STATE (S→C)
```json
{"v":1,"t":"STATE","seq":240,"tick":240,
 "snakes":[{"id":3,"n":"ana","c":3,"a":1,"s":30,"x":10,"y":7,"d":"LLLRR"},
           {"id":4,"n":"bob","c":4,"a":0,"s":0}],
 "food":[[5,5],[20,31]]}
```
`seq` is the snapshot counter (strictly increasing), `tick` the simulation tick. Per snake: `id`, `n` name,
`c` colour index, `a` alive(0/1), `s` score; if alive also `x`,`y` (head cell) and `d` (one `U/D/L/R` per step
from each segment to the next, towards the tail — so the body length is `len(d)+1`). Sent to every session at
`snapshot_rate` (default 12 Hz). The same bytes go to all clients.
**Client rule:** discard a STATE whose `seq` ≤ the highest `seq` already applied (stale/reordered). Lost
snapshots are *not* retransmitted; the next one supersedes them.

### PING (C→S) / PONG (S→C)
`{"v":1,"t":"PING","tok":"…","seq":4,"ts":1234.5}` → `{"v":1,"t":"PONG","seq":4,"ts":1234.5,"tick":240}`
`ts` is the client's own clock value, echoed back so the client computes RTT. Any valid message refreshes the
session, so PING is the keep-alive when the player sends no input.

### LEAVE (C→S)
`{"v":1,"t":"LEAVE","tok":"…"}` — removes the session. Idempotent: leaving twice (the client sends it twice
in case one datagram is lost) or with an unknown token produces no error. If both are lost, the timeout removes the player.

### ERROR (S→C)
`{"v":1,"t":"ERROR","code":"BAD_FIELD","msg":"INPUT.dir: expected one of ('U', 'D', 'L', 'R')","ref":"INPUT"}`
(`ref` optional: the type that caused it).

| Code | Cause | Client behaviour |
|---|---|---|
| `BAD_JSON` | Not UTF-8 JSON object | Log; show error. |
| `BAD_VERSION` | `v` ≠ 1 | Fail (no retry): incompatible server. |
| `BAD_TYPE` | Unknown type / wrong direction | Log. |
| `BAD_FIELD` | Missing or invalid field | Log. |
| `TOO_LARGE` | Datagram over limit | Log. |
| `BAD_SESSION` | Unknown token, or token used from a different address | Treat as lost; re-JOIN. |
| `SERVER_FULL` | No free slot | Fail, show message. |
| `RATE_LIMITED` | INPUT flood | Log. |
| `SESSION_EXPIRED` | Idle past timeout | Treat as lost; re-JOIN. |
| `SERVER_SHUTDOWN` | Server closing | Fail, show message. |

`ERROR` is best-effort: the receiver may never see it; correctness never depends on it arriving.

## 5. Sessions

* Identity = secret `tok` **and** the source `(ip, port)` it was issued to. A token replayed from another address → `BAD_SESSION`.
  (Tokens travel in clear text; this prevents accidental/blind cross-player commands, not an on-path attacker.)
* A client crash that restarts from the same port within the timeout is re-attached to its old session (same `pid`).
* The server drops a session after `session_timeout` without any valid message and sends `SESSION_EXPIRED` (best effort).
* Client-side: no datagram from the server for 2 s → status *connection lost*, automatic re-JOIN (5 attempts), then *failed*.

## 6. Reliability summary

| Traffic | Strategy |
|---|---|
| STATE | Unreliable. Sequence numbers; client drops stale; next snapshot repairs loss. |
| INPUT | Sequence numbers + 2 copies per press; server drops duplicates. A fully lost press is lost (player presses again). |
| JOIN | Bounded retries (5 × 0.5 s); server side idempotent; outcome is WELCOME, ERROR, or client-side timeout. |
| LEAVE | Sent twice; idempotent; timeout is the safety net. |

Limitations: no encryption or authentication of players; no IPv6; `seq` is not wrap-around aware (Python ints, session-length matches); a client behind NAT that changes port gets a new session.
