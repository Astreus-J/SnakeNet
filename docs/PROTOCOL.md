# Protocolo da aplicação SnakeNet — versão 1

Transporte: **UDP** (IPv4). Porta padrão do servidor: **UDP 5000** (configurável).
Codificação: **um objeto JSON UTF-8 por datagrama**. Fonte da verdade: o pacote [`snakenet/protocol/`](../snakenet/protocol/) (`schemas.py`, `validators.py`, `codec.py`, `errors.py`, `limits.py`).

> O UDP **não** é confiável nem ordenado. Toda regra abaixo que pareça confiabilidade (números de sequência,
> retentativas, idempotência) é implementada pela *aplicação*, por cima de datagramas "melhor esforço".

## 1. Enquadramento (framing)

O UDP preserva as fronteiras das mensagens: um `sendto` produz exatamente um `recvfrom`. Por isso cada datagrama
carrega exatamente uma mensagem e **não é preciso prefixo de tamanho nem delimitador** (o TCP, que é um fluxo de bytes, precisaria).

## 2. Envelope

```json
{"v": 1, "t": "INPUT", "...": "campos específicos do tipo"}
```

| Campo | Tipo | Regra |
|---|---|---|
| `v` | int | Deve ser `1`. Ausente → `BAD_FIELD`; outro valor → `BAD_VERSION`. |
| `t` | string | Um dos tipos abaixo **e** válido para o sentido em que foi enviado; senão `BAD_TYPE`. |

Campos extras desconhecidos são ignorados e descartados. Booleanos nunca são aceitos como inteiros.

## 3. Limites

| Limite | Valor | Motivo |
|---|---|---|
| Datagrama cliente → servidor | ≤ 1024 bytes | As mensagens reais têm < 150 B; limita o custo de parsing. Maior → `TOO_LARGE`. |
| Datagrama servidor → cliente | ≤ 1472 bytes | 1500 (MTU Ethernet) − 20 (IPv4) − 8 (UDP): nunca é fragmentado pelo IP. |
| Nome do jogador | 1–12 caracteres imprimíveis | |
| Timeout de sessão | 5 s de silêncio (`--session-timeout`) | |
| Taxa de INPUT | 30/s sustentado, rajada de 30 (por sessão) | Token bucket. |
| Respostas ERROR | ≤ 5/s por endereço de origem | Limita reflexão e spam de log. |

## 4. Mensagens

Sentido: **C→S** cliente para servidor, **S→C** servidor para cliente. `tok` é o token de sessão (16 caracteres hexadecimais).

### JOIN (C→S)
`{"v":1,"t":"JOIN","name":"ana"}` — pedido para entrar na partida. O cliente repete a cada 0,5 s, até 5 vezes.
Servidor: cria uma sessão (novo `pid`, `tok` aleatório) e responde `WELCOME`; se aquele endereço já tem sessão, o mesmo
`WELCOME` é reenviado (**idempotente**, sem jogador duplicado). Partida cheia → `ERROR SERVER_FULL`.

### WELCOME (S→C)
`{"v":1,"t":"WELCOME","pid":3,"tok":"9f2c4a1b7e0d5c33","w":60,"h":40,"tick_rate":8,"timeout":5}`
`pid` é o id do jogador; `tok` deve acompanhar toda mensagem seguinte do cliente; `w`/`h` são o tamanho da arena em células;
`timeout` diz ao cliente com que frequência enviar keep-alives (ele envia PING a cada `timeout/3`).

### INPUT (C→S)
`{"v":1,"t":"INPUT","tok":"9f2c4a1b7e0d5c33","seq":17,"dir":"U"}` — `dir` ∈ `U D L R`.
`seq` é um contador por cliente que cresce a cada nova tecla. O servidor só aceita um INPUT se `seq` for maior que o último
`seq` aceito daquela sessão; assim **duplicatas e datagramas fora de ordem são ignorados**. O cliente envia propositalmente
cada tecla **duas vezes com o mesmo `seq`**, para tolerar perda; a segunda cópia é descartada como duplicata.
Uma inversão de sentido (por exemplo `L` enquanto anda para `R`) é validada e ignorada. O cliente nunca envia posições.

### STATE (S→C)
```json
{"v":1,"t":"STATE","seq":240,"tick":240,
 "snakes":[{"id":3,"n":"ana","c":3,"a":1,"s":30,"x":10,"y":7,"d":"LLLRR"},
           {"id":4,"n":"bob","c":4,"a":0,"s":0}],
 "food":[[5,5],[20,31]]}
```
`seq` é o contador de snapshots (estritamente crescente); `tick` é o tick da simulação. Por cobra: `id`, `n` nome,
`c` índice da cor, `a` viva (0/1), `s` pontuação; se estiver viva, também `x`,`y` (célula da cabeça) e `d` (um caractere
`U/D/L/R` por passo, de cada segmento para o seguinte, em direção à cauda — logo o comprimento do corpo é `len(d)+1`).
Enviado a todas as sessões na `snapshot_rate` (padrão 8 Hz). Os mesmos bytes vão para todos os clientes.
**Regra do cliente:** descartar um STATE cujo `seq` seja ≤ ao maior `seq` já aplicado (antigo/reordenado). Snapshots perdidos
**não** são retransmitidos; o seguinte os substitui.

### PING (C→S) / PONG (S→C)
`{"v":1,"t":"PING","tok":"…","seq":4,"ts":1234.5}` → `{"v":1,"t":"PONG","seq":4,"ts":1234.5,"tick":240}`
`ts` é o valor do relógio do próprio cliente, devolvido para ele calcular o RTT. Qualquer mensagem válida renova a sessão,
então o PING é o keep-alive quando o jogador não envia teclas.

### LEAVE (C→S)
`{"v":1,"t":"LEAVE","tok":"…"}` — remove a sessão. Idempotente: sair duas vezes (o cliente envia duas vezes, caso um datagrama
se perca) ou com token desconhecido não gera erro. Se ambos se perderem, o timeout remove o jogador.

### ERROR (S→C)
`{"v":1,"t":"ERROR","code":"BAD_FIELD","msg":"INPUT.dir: expected one of ('U', 'D', 'L', 'R')","ref":"INPUT"}`
(`ref` é opcional: o tipo que causou o erro).

| Código | Causa | Comportamento do cliente |
|---|---|---|
| `BAD_JSON` | Não é um objeto JSON UTF-8 | Registra em log; mostra o erro. |
| `BAD_VERSION` | `v` ≠ 1 | Falha (sem retentativa): servidor incompatível. |
| `BAD_TYPE` | Tipo desconhecido / sentido errado | Registra em log. |
| `BAD_FIELD` | Campo ausente ou inválido | Registra em log. |
| `TOO_LARGE` | Datagrama acima do limite | Registra em log. |
| `BAD_SESSION` | Token desconhecido, ou usado a partir de outro endereço | Considera perdida; faz JOIN de novo. |
| `SERVER_FULL` | Sem vaga | Falha e mostra a mensagem. |
| `RATE_LIMITED` | Flood de INPUT | Registra em log. |
| `SESSION_EXPIRED` | Inativo além do timeout | Considera perdida; faz JOIN de novo. |
| `SERVER_SHUTDOWN` | Servidor encerrando | Falha e mostra a mensagem. |

O `ERROR` é "melhor esforço": o receptor pode nunca vê-lo; a correção nunca depende de ele chegar.

## 5. Sessões

* Identidade = `tok` secreto **e** o `(ip, porta)` de origem para o qual foi emitido. Um token repetido a partir de outro endereço → `BAD_SESSION`.
  (Os tokens trafegam em texto claro; isso evita comandos acidentais/às cegas entre jogadores, não um atacante no caminho da rede.)
* Um cliente que cai e reinicia a partir da mesma porta dentro do timeout é reanexado à sessão antiga (mesmo `pid`).
* O servidor descarta a sessão após `session_timeout` sem nenhuma mensagem válida e envia `SESSION_EXPIRED` (melhor esforço).
* No cliente: 2 s sem nenhum datagrama do servidor → estado *connection lost* e novo JOIN automático (5 tentativas); depois, *failed*.

## 6. Resumo da confiabilidade

| Tráfego | Estratégia |
|---|---|
| STATE | Não confiável. Números de sequência; o cliente descarta os antigos; o próximo snapshot repara a perda. |
| INPUT | Números de sequência + 2 cópias por tecla; o servidor descarta duplicatas. Uma tecla totalmente perdida se perde (o jogador aperta de novo). |
| JOIN | Retentativas limitadas (5 × 0,5 s); idempotente no servidor; o resultado é WELCOME, ERROR ou timeout no cliente. |
| LEAVE | Enviado duas vezes; idempotente; o timeout é a rede de segurança. |

Limitações: sem criptografia nem autenticação de jogadores; sem IPv6; `seq` não trata estouro (inteiros do Python, suficientes para a duração de uma sessão); um cliente atrás de NAT que mude de porta recebe uma nova sessão.
