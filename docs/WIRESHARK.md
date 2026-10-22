# Guia de captura e análise no Wireshark

> **Estado: existem capturas reais (loopback e rede real com 2 computadores) e 7 telas do Wireshark** — seções 4 a 7.
> **Ainda faltam:** o experimento de perda de pacotes e `LEAVE`/`ERROR` capturados em rede real (só existem no loopback).
> Nada foi inventado; as tabelas vêm dos arquivos `.pcapng` (analisados com `tshark`).

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
| Telas do Wireshark | **tiradas**: ver §7 (`evidence/wireshark-01…07-*.png`) |

Comandos usados para extrair esses números: `tshark -r evidence/snakenet.pcapng -q -z conv,udp` (conversas) e
`tshark -r evidence/snakenet.pcapng -T fields -e udp.srcport -e udp.dstport -e data.data` (payloads, decodificados em JSON).

## 5. Captura em rede real, dois computadores (hotspot do celular)

Arquivo: [`evidence/snakenet-rede-real.pcapng`](../evidence/snakenet-rede-real.pcapng) — 726 pacotes, **60 s**, capturado em **22/10/2026** com `dumpcap`
na interface Wi-Fi `wlp4s0` **do computador do servidor**, filtro de captura `udp port 5000`, 0 pacotes descartados pela interface.
O servidor já estava rodando (14 min) e a sessão já estava aberta quando a captura começou; por isso **não aparecem `JOIN`, `WELCOME`, `LEAVE` nem `ERROR`** neste arquivo (eles estão na captura de loopback, §4).

| Item | Valor |
|---|---|
| Servidor | `10.209.198.22:5000` |
| Cliente remoto (notebook da colega) | `10.209.198.154:36099` (porta efêmera) |
| Rede | hotspot do celular, `10.209.198.0/24` (dois IPs diferentes, mesma sub-rede) |
| Cliente → servidor | `INPUT` 176 pacotes (64 B; 88 `seq` únicos, ou seja, **2 cópias de cada tecla**) + `PING` 35 pacotes (70–72 B) |
| Servidor → cliente | `STATE` 480 pacotes (404–475 B, mediana 438 B) + `PONG` 35 pacotes (57–59 B) |
| Taxa de `STATE` | 480 em 60 s = **8/s**; intervalo médio 0,125 s, máximo 0,126 s |
| Sequência do `STATE` | `seq` 505 → 984, **0 faltando, 0 duplicados, ordem crescente** |
| `PING` | 35 em 60 s ≈ 1 a cada 1,7 s (`timeout/3`) |

Como interpretar (e limites desta evidência):
* A captura foi feita **no servidor**. Ela mostra o que o servidor *enviou* e *recebeu*. Um pacote perdido **depois** de sair do servidor (no hotspot ou no Wi-Fi do cliente) **apareceria como entregue aqui**. A ausência de lacunas no `seq` mostra que o servidor enviou tudo em ordem, não que o cliente recebeu tudo. Para medir perda de verdade, compare com um contador no cliente (`stale` e `rx` na barra lateral) ou capture também no notebook do cliente.
* O intervalo entre `PING` e `PONG` visto aqui (0,22–0,45 ms) é só o **tempo de resposta do servidor**, não o RTT da rede. O RTT real aparece como "ping" na barra lateral do cliente.

## 6. Segunda captura em rede real — com `JOIN` e `WELCOME`

Arquivo: [`evidence/snakenet-rede-real-join.pcapng`](../evidence/snakenet-rede-real-join.pcapng) — 1119 pacotes, **90 s**, 22/10/2026, `dumpcap` em `wlp4s0`
no computador do servidor, filtro `udp port 5000`, 0 descartados pela interface. Mesmos endereços da §5: servidor `10.209.198.22:5000`, cliente remoto `10.209.198.154:36099`.

| Item | Valor |
|---|---|
| Tipos de mensagem | `STATE` 721 · `INPUT` 286 · `PING` 53 · `PONG` 53 · `JOIN` 3 · `WELCOME` 3 |
| `STATE` | `seq` 2714 → 3434: **0 faltando, 0 duplicados, crescente**; maior intervalo entre pacotes 0,126 s (8/s) |
| `INPUT` | em pares com o mesmo `seq` (ex.: #3 e #4, `seq=493`, `dir=L`, mesmo instante) |
| `JOIN` (C→S) | 3 pacotes, 34 B, todos de `10.209.198.154:36099` com `name:"zeninn"`, em t = 57,04 s, 59,14 s e 60,00 s |
| `WELCOME` (S→C) | 3 pacotes, 98 B, **idênticos**: `pid:1`, `tok:075d4679e517c94b`, arena 60×40, `tick_rate:8.0`, `timeout:5.0` |

O que isto mostra: **`JOIN` repetido é idempotente**. Os três `JOIN` vieram do mesmo endereço, e o servidor respondeu cada um com o **mesmo `pid` e o mesmo `tok`**, sem criar jogador duplicado.
Os `JOIN` repetidos, em intervalos de ~2 s e ~1 s, parecem ter sido causados por reconexões manuais com a tecla `R` no cliente (é uma inferência: a captura não registra teclas).
O `STATE` continuou sem lacunas durante e depois das reconexões.

**Ainda não capturado em rede real:** `LEAVE` (nenhum cliente saiu com `Esc` durante a janela) e `ERROR`. Ambos estão na captura de loopback (§4).
A ressalva da §5 continua valendo: a captura é do lado do servidor e não mede perda que ocorra depois que o pacote sai dele.

## 7. Telas do Wireshark (evidências)

Geradas em 22/10/2026 abrindo os `.pcapng` no Wireshark 4.7.4 e fotografando **só a janela do Wireshark** (`spectacle`), sem editar. Em todas, a lista de pacotes mostra
IP e porta de origem/destino, o painel de detalhes mostra *Ethernet II → IPv4 → UDP → Data* e o painel de bytes mostra o **JSON em texto** (o Wireshark o chama de "Data" porque não tem dissector para o protocolo próprio).

| Tela | Captura | Filtro de exibição | O que mostra |
|---|---|---|---|
| [01](../evidence/wireshark-01-visao-geral-rede-real.png) | rede real | `udp.port == 5000` | Visão geral: `10.209.198.22:5000` ⇄ `10.209.198.154:36099`; `STATE` de 496 B (Len=454) a cada ~0,125 s e `INPUT` de 106 B (Len=64) em pares; no painel de bytes, o JSON do `STATE` |
| [02](../evidence/wireshark-02-join-rede-real.png) | rede real | `frame contains "\"t\":\"JOIN\""` | Os 3 `JOIN` (#684, #705, #715), `36099 → 5000`, Len=34; bytes: `{"v":1,"t":"JOIN","name":"zeninn"}` |
| [03](../evidence/wireshark-03-welcome-rede-real.png) | rede real | `frame contains "\"t\":\"WELCOME\""` | Os 3 `WELCOME` (#685, #706, #716), `5000 → 36099`, Len=98; bytes: `pid:1`, `tok`, arena 60×40, `tick_rate` 8.0, `timeout` 5.0 |
| [04](../evidence/wireshark-04-input-em-pares-rede-real.png) | rede real | `frame contains "\"t\":\"INPUT\""` | 286 `INPUT` exibidos; #3 e #4 chegam com ~0,9 µs de diferença (par com o mesmo `seq`); bytes: `{"v":1,"t":"INPUT","tok":…,"seq":493,"dir":"L"}` |
| [05](../evidence/wireshark-05-state-rede-real.png) | rede real | `frame contains "\"t\":\"STATE\""` | Snapshots do servidor (`seq`, `tick`, cobras, comida) a 8/s |
| [06](../evidence/wireshark-06-error-bad-json-loopback.png) | loopback | `frame contains "\"t\":\"ERROR\""` | `ERROR` com `code:"BAD_JSON"` (`5100 → 35367`, Len=78) em resposta ao `hello` |
| [07](../evidence/wireshark-07-leave-loopback.png) | loopback | `frame contains "\"t\":\"LEAVE\""` | 4 `LEAVE` (2 de cada cliente, Len=44), enviados em dobro |

Limites: as telas 06 e 07 são do **loopback** (`127.0.0.1`, porta 5100). Em rede real ainda não há `LEAVE` nem `ERROR` capturados. A captura de rede real foi feita no servidor (ver ressalva da §5).
As telas mostram os painéis de detalhes **recolhidos**; para expandir, clique no pacote e use *Análise → Expandir subárvores*.
