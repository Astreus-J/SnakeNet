# Guia de captura e análise no Wireshark

> **Estado: a captura AINDA NÃO foi feita.** O ambiente de desenvolvimento não tinha permissão de captura (sem `tshark`/`tcpdump`,
> sem `sudo`, sockets raw negados), então não existe `.pcapng` nem tela do Wireshark. Nada aqui foi inventado:
> siga o procedimento na sua máquina, salve os arquivos em [`evidence/`](../evidence/) e depois preencha a tabela
> "Observado" no final com o que você realmente viu.
> (`evidence/screenshot-headless.png` é uma tela do *cliente do jogo*, não uma captura do Wireshark.)

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

## 4. Observado (preencha com a sua captura real)

| Item | Valor |
|---|---|
| Data / máquina / interface | _TODO_ |
| IP:porta do servidor | _TODO_ |
| IP:porta do cliente 1 | _TODO_ |
| IP:porta do cliente 2 | _TODO_ |
| Tamanho típico do STATE | _TODO_ |
| Tamanho típico do INPUT | _TODO_ |
| Resultado do experimento de perda de pacotes | _TODO / não executado_ |
| Arquivos salvos | _TODO (`evidence/...`)_ |
