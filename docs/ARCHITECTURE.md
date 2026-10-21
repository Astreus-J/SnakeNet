# Arquitetura do SnakeNet

```mermaid
flowchart LR
  subgraph PC1["Máquina A (cliente)"]
    UI1["client/ui.py<br/>desenho pygame + teclado"]
    NET1["client/network.py<br/>thread de rede"]
    S1(("socket UDP<br/>porta efêmera"))
    UI1 <-->|"último STATE protegido por lock / send_input()"| NET1
    NET1 --- S1
  end
  subgraph PC2["Máquina B (cliente)"]
    UI2["client/ui.py"] <--> NET2["client/network.py"]
    NET2 --- S2(("socket UDP<br/>porta efêmera"))
  end
  subgraph SRV["Máquina do servidor  (--host / --port, padrão UDP 5000)"]
    SS(("socket UDP<br/>IP:PORTA do bind"))
    LOOP["server/app.py<br/>loop único:<br/>recv → protocol.decode → valida"]
    SESS["server/sessions.py<br/>token + endereço + limite de taxa"]
    WORLD["game/world.py World<br/>estado autoritativo<br/>tick fixo de 8 Hz"]
    SS --> LOOP --> SESS --> WORLD
    WORLD -->|"snapshot a cada tick"| LOOP --> SS
  end
  S1 -- "JOIN / INPUT / PING / LEAVE  (UDP, JSON)" --> SS
  S2 -- "JOIN / INPUT / PING / LEAVE" --> SS
  SS -- "WELCOME / STATE / PONG / ERROR" --> S1
  SS -- "WELCOME / STATE / PONG / ERROR" --> S2
```

## Sequência: entrar e jogar

```mermaid
sequenceDiagram
  participant C as Cliente
  participant S as Servidor
  C->>S: JOIN {name}
  S-->>C: WELCOME {pid, tok, w, h}
  loop a cada tecla
    C->>S: INPUT {tok, seq, dir} (x2, mesmo seq)
  end
  loop a cada tick (8 Hz)
    Note over S: valida entradas, move, come, colide, pontua
    S-->>C: STATE {seq, snakes, food}
  end
  C->>S: PING {tok, seq, ts}
  S-->>C: PONG {seq, ts, tick}
  C->>S: LEAVE {tok} (x2)
```

## Responsabilidades

| Processo | Faz | Nunca faz |
|---|---|---|
| **Servidor** (`snakenet/server/`, `snakenet/game/`) | Faz o bind do socket UDP; valida todo datagrama; é dono das sessões; roda a simulação em passo fixo; decide movimento, comida, crescimento, colisões, mortes e pontos; envia os snapshots; expira sessões inativas | Confiar em posição/pontos enviados pelo cliente; travar esperando um cliente |
| **Cliente** (`snakenet/client/`) | Tem socket UDP próprio; faz JOIN com retentativa; envia direções validadas; recebe snapshots em uma thread de rede; descarta os antigos; desenha; mostra o estado da conexão; sai de forma limpa | Simular o jogo ou enviar estado |

## Camadas e mapa de módulos (as dependências só apontam para baixo)

```
 server/__main__.py   client/__main__.py   client/bot.py        pontos de entrada (CLI, argumentos)
        |                    |                  |
 server/app.py         client/ui.py  ──►  client/network.py      aplicação / adaptadores (E/S UDP, pygame)
        |    \                                   |
 server/sessions.py  server/throttle.py          |               estado por jogador, limitadores de abuso
        |                                         |
        └──────────►  protocol/  ◄───────────────┘               contrato na rede: schemas, validação, codec
        └──────────►  game/      (só o servidor; o cliente usa decode_body para desenhar)   domínio puro, sem E/S
                      config.py                                  dataclasses de configuração
```

| Pacote | Responsabilidade única | Conhece |
|---|---|---|
| `protocol/` | constantes de `limits`, códigos de `errors`, `validators`, `schemas` (catálogo de mensagens), `codec` (bytes ⇄ dict validado) | nada além de si |
| `game/` | Regras e simulação (`world.py`); determinístico, testável sem sockets | nada além de si |
| `server/sessions.py` | Identidade da sessão, limitador token bucket de entradas, checagem de sequência | nada além de si |
| `server/throttle.py` | Orçamento de ERROR por endereço, log sem repetição | nada além de si |
| `server/app.py` | Socket UDP, recepção/despacho, loop de ticks, broadcast | protocol, game, sessions, throttle |
| `client/network.py` | Socket + thread + máquina de estados da conexão (sem pygame) | protocol |
| `client/ui.py`, `client/bot.py` | Apresentação / piloto automático sobre o `NetClient` | client.network, game (só decodificação) |

## Modelo de concorrência

* **Servidor:** uma única thread. Sem estado mutável compartilhado e sem locks. A leitura do socket usa um timeout igual ao tempo até o próximo tick, então o loop acorda tanto por um datagrama quanto por um tick. No máximo 256 datagramas são consumidos por iteração, de modo que um flood não consegue travar a simulação.
* **Cliente:** a thread da UI desenha; uma thread de rede recebe. Elas compartilham apenas o último snapshot validado e o status, trocados sob um único `threading.Lock`; a UI copia o valor. Os contadores de sequência também são usados sob o mesmo lock.
