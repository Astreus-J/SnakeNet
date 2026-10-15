# Wireshark capture and analysis guide

> **Status: capture NOT yet performed.** The development sandbox had no capture rights (no `tshark`/`tcpdump`,
> no `sudo`, raw sockets denied), so no `.pcapng` or Wireshark screenshot exists yet. Nothing here is fabricated:
> follow the procedure on your own machine, save the files in [`evidence/`](../evidence/) and then fill in the
> "Observed" table at the bottom with what you actually saw.
> (`evidence/screenshot-headless.png` is a screenshot of the *game client*, not a Wireshark capture.)

## 1. Reproducible procedure (same machine, loopback)

1. Install Wireshark (Linux: add yourself to the `wireshark` group; Windows: install Npcap with *loopback* support).
2. Start Wireshark, choose the **loopback** interface (`lo` on Linux, *Npcap Loopback Adapter* on Windows), capture filter `udp port 5000`, start capturing.
3. Terminal 1: `python -m snakenet.server --host 127.0.0.1 --port 5000`
4. Terminals 2–3: `python -m snakenet.client --port 5000 --name ana` and `... --name bob` (or `tools/demo_local.sh` for bots).
5. Join, steer with the arrow keys for ~20 s, then close one client (ESC) to produce `LEAVE`.
6. Controlled error: `printf 'hello' | nc -u -w1 127.0.0.1 5000` → the server answers `ERROR BAD_JSON`.
7. Stop capture, save as `evidence/snakenet.pcapng`; take screenshots into `evidence/`.

CLI alternative: `tools/capture.sh lo 5000` (uses `dumpcap`, then open the file in Wireshark).
LAN: bind the server with `--host 0.0.0.0`, capture on the real interface (e.g. `wlan0`/`eth0`), and record the real IPs.

## 2. Display filters

| Goal | Filter |
|---|---|
| All game traffic | `udp.port == 5000` |
| Only client → server | `udp.dstport == 5000` |
| Only server → clients | `udp.srcport == 5000` |
| One message type | `frame contains "\"t\":\"JOIN\""` (also `INPUT`, `STATE`, `PING`, `PONG`, `LEAVE`, `ERROR`) |
| Errors from the server | `udp.srcport == 5000 && frame contains "\"t\":\"ERROR\""` |
| One client | `udp.port == <client ephemeral port>` |

## 3. What to point at in the capture

* **IPs/ports:** in *Packet Details → Internet Protocol / User Datagram Protocol*. The server always uses the configured port (5000); every client uses a different **ephemeral source port** chosen by its OS – that pair `(ip, port)` is how the server tells players apart.
* **UDP datagrams:** no handshake, no ACKs, no connection setup – the first packet is already `JOIN`. Contrast with TCP's SYN/SYN-ACK/ACK.
* **Payload:** JSON is plain text, visible in the bytes pane or via *Follow → UDP Stream*. Wireshark labels it "Data" because it has no dissector for this custom protocol (the payload is unencrypted, so it is readable).
* **Input vs. state:** `INPUT` JSON payloads are small (63 bytes for a typical one; measured with the codec), sent only on key presses, **in pairs with the same `seq`** (redundancy against loss). `STATE` payloads are larger (399 bytes with 2 fresh snakes and 30 food; grows with players and length, hard cap 1472 bytes), sent ~8×/s to *every* client with an increasing `seq`, regardless of input.
* **Session flow:** `JOIN` → `WELCOME` (contains `pid`, `tok`) → continuous `STATE` → `PING`/`PONG` every `timeout/3` ≈ 1.67 s → `LEAVE` ×2.
* **Packet loss / delay (optional experiment):** on Linux, `sudo tc qdisc add dev lo root netem loss 20% delay 80ms` (undo with `sudo tc qdisc del dev lo root`). Then look for gaps in `STATE.seq` (use *Statistics → I/O Graphs* or compare `seq` in successive packets), and in the client sidebar watch `stale` or ping change. The game continues because later snapshots supersede lost ones.

## 4. Observed (fill in from your real capture)

| Item | Value |
|---|---|
| Date / machine / interface | _TODO_ |
| Server IP:port | _TODO_ |
| Client 1 IP:port | _TODO_ |
| Client 2 IP:port | _TODO_ |
| Typical STATE size | _TODO_ |
| Typical INPUT size | _TODO_ |
| Packet-loss experiment result | _TODO / not run_ |
| Files saved | _TODO (`evidence/...`)_ |
