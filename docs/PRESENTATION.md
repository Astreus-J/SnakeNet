# Presentation plan (≤ 10 minutes)

| # | Min | Topic | What to show / say |
|---|---|---|---|
| 1 | 1:00 | Problem and solution | Real-time multiplayer needs many processes to share one consistent world with low latency. SnakeNet: arena where several clients play the same match through one authoritative server. |
| 2 | 1:00 | Architecture | [ARCHITECTURE.md](ARCHITECTURE.md) diagram: N clients ⇄ 1 server, each with its own UDP socket; server owns the state; clients send *inputs*, receive *snapshots*. |
| 3 | 1:30 | Socket implementation | `server/app.py`: `socket(AF_INET, SOCK_DGRAM)`, `bind`, `recvfrom`/`sendto`, timeout = time to next tick. `client/network.py`: own socket, receive thread so rendering never blocks. Point at ip:port config. |
| 4 | 1:30 | Why UDP (vs TCP) | Next section. |
| 5 | 1:30 | Application protocol | [PROTOCOL.md](PROTOCOL.md): JSON envelope `{v,t,...}`; JOIN/WELCOME/INPUT/STATE/PING/PONG/LEAVE/ERROR; seq numbers; validation. |
| 6 | 2:00 | Live demo | Server + 2–3 clients (one human, bots). Eat, grow, die, leaderboard. Kill the server → client shows *connection lost*; restart → R reconnects. Send junk with `nc -u` → server survives. |
| 7 | 1:00 | Wireshark | Open the real capture: UDP, ports, `JOIN`, repeating `INPUT` pairs, 12 Hz `STATE`, `ERROR`. (Must be your own capture – see [WIRESHARK.md](WIRESHARK.md).) |
| 8 | 0:30 | Errors and conclusion | Table of failure → handling; limitations; what we learned. |

## UDP vs TCP (talking points)

* A new snapshot **supersedes** the previous one, so retransmitting an old one is wasted work. TCP would retransmit and *block* newer data behind the lost segment (**head-of-line blocking**), producing visible stutter.
* UDP has no connection setup: the first datagram is already `JOIN`. No per-client connection state in the kernel; the server tracks sessions itself (token + address + timeout).
* **Message boundaries:** one datagram = one message, so no framing code. TCP is a byte stream: we would need length-prefix or delimiters, and a read could return half a message.
* What UDP costs us and what we added: loss/reorder/duplication → sequence numbers (stale `STATE` dropped, duplicate `INPUT` ignored), JOIN retries (bounded, idempotent), timeouts for dead peers, redundancy for inputs. We did *not* rebuild TCP.
* If we used TCP: simpler reliability and framing is our job; join = 3-way handshake; one connection per player; a lost segment stalls all later state; Nagle/delayed-ACK tuning (`TCP_NODELAY`); but it would be a better choice for chat, login or file transfer.

## Likely individual questions

| Question | Short answer |
|---|---|
| Is UDP reliable/ordered? | No. Datagrams may be lost, duplicated, reordered. We handle it in the application only where it matters. |
| What identifies a UDP "connection"? | There is none. The server keys sessions by the secret token and source (IP, port). |
| What is a socket? | The OS endpoint for a process, identified by protocol + local IP + port. |
| Why does the client not bind to a port? | The OS assigns an ephemeral source port on first `sendto`; the server replies to that address. |
| IP vs port? | IP selects the host (network layer); port selects the process on it (transport layer). |
| What if a `STATE` is lost? | Nothing: the next arrives in ~83 ms and carries the full world. |
| What if `JOIN` or its `WELCOME` is lost? | Client retries (5 × 0.5 s); server answers a repeated JOIN with the same `WELCOME`, so no duplicate player. Else *server unavailable*. |
| Why must the server be authoritative? | Clients can lie or lag; the server validates inputs and decides outcomes, so all clients converge on one state. |
| Why send input twice? | Cheap loss insurance; same `seq` so the server ignores the copy. |
| Max datagram size? | UDP payload up to ~65 507 B, but we cap server packets at 1472 B (MTU − IP − UDP) to avoid IP fragmentation. |
| What does a client do on `BAD_SESSION`? | Treats the session as gone and re-JOINs. |
| Can someone steal my snake? | They'd need the token *and* my IP:port; tokens are unencrypted, so an on-path attacker could (documented limitation). |
| Why JSON? | Human-readable in Wireshark and easy to validate; costs bytes versus a binary format. |
| Why is the server single-threaded? | No shared-state races; one loop reads, simulates, sends. UDP sends never wait for the receiver. |
