# Guia de captura e análise no Wireshark

> **Estado: existe uma captura real em loopback** — [`evidence/snakenet.pcapng`](../evidence/snakenet.pcapng) (558 pacotes, feita com
> `dumpcap` em 22/10/2026 e analisada com `tshark`). **Ainda faltam:** telas do Wireshark (interface gráfica), captura em rede real entre duas
> máquinas e o experimento de perda de pacotes. Nada foi inventado; a tabela da seção 4 vem do arquivo. Para a apresentação,
> abra o `.pcapng` no Wireshark e tire as telas, ou refaça a captura seguindo o procedimento abaixo.
> (`evidence/screenshot-headless.png` é uma tela do *cliente do jogo*, não do Wireshark.)

> **Permissão no Linux:** se o Wireshark disser "Você não tem permissão para capturar", seu usuário precisa estar no grupo `wireshark`
> (`sudo usermod -aG wireshark $USER`) **e** a sessão precisa ser nova (logout/login). Sem reiniciar a sessão, abra o Wireshark com
> `newgrp wireshark` seguido de `wireshark`.

## 1. Procedimento reproduzível (mesma máquina, loopback)

1. Instale o Wireshark (Linux: entre no grupo `wireshark`; Windows: instale o Npcap com suporte a *loopback*).
2. Abra o Wireshark, escolha a interface de **loopback** (`lo` no Linux, *Npcap Loopback Adapter* no Windows), filtro de captura `udp port 5000`, e inicie a captura.
3. Terminal 1: `python -m snakenet.server --host 127.0.0.1 --port 5000`
4. Terminais 2–3: `python -m snakenet.client --port 5000 --name ana` e `... --name bob` (ou `tools/demo_local.sh` para bots).
5. Entre, movimente com as setas por ~20 s e depois feche um cliente (ESC) para gerar o `LEAVE`.
6. Erro controlado: `printf 'hello' | nc -u -w1 127.0.0.1 5000` → o servidor responde `ERROR BAD_JSON`.
7. Pare a captura, salve como `evidence/snakenet.pcapng` e coloque as telas em `evidence/`.

Alternativa por linha de comando: `tools/capture.sh lo 5000` (usa o `dumpcap`; depois abra o arquivo no Wireshark).
Em LAN: suba o servidor com `--host 0.0.0.0`, capture na interface real (por exemplo `wlan0`/`eth0`) e anote os IPs reais.

## 2. Filtros de exibição

| Objetivo | Filtro |
|---|---|
| Todo o tráfego do jogo | `udp.port == 5000` |
| Só cliente → servidor | `udp.dstport == 5000` |
| Só servidor → clientes | `udp.srcport == 5000` |
| Um tipo de mensagem | `frame contains "\"t\":\"JOIN\""` (também `INPUT`, `STATE`, `PING`, `PONG`, `LEAVE`, `ERROR`) |
| Erros vindos do servidor | `udp.srcport == 5000 && frame contains "\"t\":\"ERROR\""` |
| Um cliente | `udp.port == <porta efêmera do cliente>` |

## 3. O que apontar na captura

* **IPs/portas:** em *Packet Details → Internet Protocol / User Datagram Protocol*. O servidor sempre usa a porta configurada (5000); cada cliente usa uma **porta de origem efêmera** diferente, escolhida pelo seu sistema operacional — esse par `(ip, porta)` é como o servidor distingue os jogadores.
* **Datagramas UDP:** sem handshake, sem ACKs, sem estabelecimento de conexão — o primeiro pacote já é o `JOIN`. Compare com SYN/SYN-ACK/ACK do TCP.
* **Payload:** o JSON é texto puro, visível no painel de bytes ou em *Follow → UDP Stream*. O Wireshark mostra como "Data" porque não tem dissector para este protocolo próprio (o payload não é criptografado, por isso é legível).
* **Entrada × estado:** o payload JSON de um `INPUT` é pequeno (63 bytes num caso típico; medido com o codec), enviado só quando há tecla, **em pares com o mesmo `seq`** (redundância contra perda). Os payloads de `STATE` são maiores (399 bytes com 2 cobras novas e 30 comidas; crescem com jogadores e tamanho, teto rígido de 1472 bytes), enviados ~8×/s para *todos* os clientes, com `seq` crescente, independentemente de haver entrada.
* **Fluxo da sessão:** `JOIN` → `WELCOME` (traz `pid`, `tok`) → `STATE` contínuo → `PING`/`PONG` a cada `timeout/3` ≈ 1,67 s → `LEAVE` ×2.
* **Perda / atraso de pacotes (experimento opcional):** no Linux, `sudo tc qdisc add dev lo root netem loss 20% delay 80ms` (desfaça com `sudo tc qdisc del dev lo root`). Depois procure lacunas no `STATE.seq` (use *Statistics → I/O Graphs* ou compare o `seq` de pacotes sucessivos) e, na barra lateral do cliente, observe `stale` ou o ping mudarem. O jogo continua porque os snapshots seguintes substituem os perdidos.

## 4. Observado (da captura real `evidence/snakenet.pcapng`)

Capturado em **22/10/2026**, interface **loopback (`lo`)**, filtro de captura `udp port 5100`, duração 12 s de tráfego, **558 pacotes**.
Servidor na porta **5100** (não a 5000, que estava ocupada por outro servidor em uso). Dois bots (`maria` e `jeiel`) jogaram 12 s e foi enviado um datagrama inválido (`hello`) com `nc -u`.

| Item | Valor |
|---|---|
| IP:porta do servidor | `127.0.0.1:5100` |
| Cliente 1 (`maria`) | `127.0.0.1:57362` (porta efêmera) |
| Cliente 2 (`jeiel`) | `127.0.0.1:48344` (porta efêmera) |
| Origem do datagrama inválido | `127.0.0.1:35367` |
| Conversas UDP | 3 conversas: 278 pacotes com cada cliente (105 cliente→servidor, 173 servidor→cliente) + 2 do datagrama inválido |
| JOIN (C→S) | 2 pacotes, 33 B de payload |
| WELCOME (S→C) | 2 pacotes, 98 B |
| INPUT (C→S) | 324 pacotes, 62–63 B — **sempre em pares com o mesmo `seq`** (ex.: #11 e #12, `seq=1`) |
| STATE (S→C) | 192 pacotes (96 por cliente = 8/s × 12 s), 409–435 B (mediana 418 B, 2 cobras) |
| PING / PONG | 16 / 16 pacotes (≈ 1 a cada 1,67 s por cliente), 71–72 B / 56–58 B |
| LEAVE (C→S) | 4 pacotes (2 por cliente, 44 B) |
| ERROR (S→C) | 1 pacote, 78 B: `{"code":"BAD_JSON","msg":"datagram is not valid UTF-8 JSON"}` em resposta ao `hello` (5 B) |
| Perda de `STATE` | **0** (seq 1…96 completo e crescente nos dois clientes) — loopback não perde pacotes |
| Experimento de perda (`tc netem`) | **não executado** |
| Telas do Wireshark | **ainda não tiradas** |

Comandos usados para extrair esses números: `tshark -r evidence/snakenet.pcapng -q -z conv,udp` (conversas) e
`tshark -r evidence/snakenet.pcapng -T fields -e udp.srcport -e udp.dstport -e data.data` (payloads, decodificados em JSON).
