# SnakeNet

Arena multiplayer de cobrinhas para desktop, original, construída sobre **sockets UDP puros** (`socket` do Python + pygame).
Trabalho de *Fundamentos de Redes de Computadores* — "Desenvolvimento de Aplicação em Rede utilizando Sockets" (entrega: 28/10/2026).

## Integrantes

| Nome               | Papel      |
| ------------------ | ---------- |
| Jeiel Santos | _[a definir]_ |
| Maria Pereira | _[a definir]_ 
| Josué Silva | _[a definir]_ ||

## 1. Problema e solução

**Problema:** várias pessoas, em máquinas diferentes, querem jogar no *mesmo* mundo em tempo real. Isso exige comunicação de baixa latência entre processos e uma visão única e consistente do jogo.
**Solução:** um processo **servidor** é dono do mundo (autoritativo) e simula 8 passos por segundo. Cada processo **cliente** envia apenas as *teclas* do jogador e desenha os *snapshots* (fotografias do estado) que recebe. Comer comida aumenta a cobra e a pontuação; bater na parede ou no corpo de uma cobra mata; um placar ordena os jogadores.

## 2. Arquitetura

Diagrama e diagrama de sequência: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** (Mermaid, renderiza no GitHub e no VS Code).

```
 cliente A ──UDP──┐                         ┌── server/app.py      (bind do socket, recv → valida → despacha)
 cliente B ──UDP──┼──►  <IP_SERVIDOR>:5000 ─┤── server/sessions.py (token + endereço, limite de taxa)
 cliente C ──UDP──┘   ◄── STATE a 8 Hz ─────└── game/world.py       (simulação autoritativa)
```

* **Processos:** `snakenet.server` (1 por partida) e `snakenet.client` / `snakenet.client.bot` (N).
* **Servidor:** faz o bind do UDP, valida todo datagrama, mantém as sessões, simula o jogo, envia `STATE` a todos e expira sessões inativas.
* **Cliente:** socket UDP próprio + thread de rede (nunca trava o desenho), JOIN com retentativas, envia as teclas, descarta snapshots antigos e mostra o estado da conexão.
* **Organização:** `snakenet/protocol/` (contrato das mensagens) · `game/` (regras puras) · `server/` · `client/` · `tests/` (espelha os pacotes) · `docs/` · `tools/` · `evidence/`.

## 3. Transporte: UDP — e por quê

Escolhido: **UDP** (`SOCK_DGRAM`). O estado de um jogo em tempo real é *substituível*: o próximo snapshot (≈125 ms depois) torna irrelevante o que se perdeu. A retransmissão e a entrega em ordem do TCP só adicionariam **bloqueio de cabeça de fila** (*head-of-line blocking*) e latência. O UDP também não tem handshake e preserva as fronteiras das mensagens (um datagrama = uma mensagem). Acrescentamos só a confiabilidade que importa (números de sequência, retentativas limitadas de JOIN, mensagens de controle idempotentes e timeouts) — veja [PROTOCOL.md §6](docs/PROTOCOL.md).

**Se fosse TCP:** seria preciso enquadrar as mensagens manualmente (prefixo de tamanho) sobre um fluxo de bytes; haveria uma conexão por jogador, com handshake de 3 vias; o kernel retransmitiria posições velhas e seguraria as novas atrás de um segmento perdido; e seria necessário ajustar Nagle / `TCP_NODELAY`. O TCP seria a escolha certa para login, chat ou transferência de arquivos. Detalhes em [docs/PRESENTATION.md](docs/PRESENTATION.md).

O UDP **não** é confiável nem ordenado; as limitações estão na seção 10.

## 4. Endereço IP e porta (configuráveis)

| Opção   | Servidor                                                                                             | Cliente                                                  |
| --------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------- |
| Endereço | `--host` (padrão `127.0.0.1`; `0.0.0.0` = todas as interfaces) ou variável `SNAKENET_HOST` | `--host` (IP ou nome do servidor) ou `SNAKENET_HOST` |
| Porta     | `--port` (padrão **UDP 5000**) ou variável `SNAKENET_PORT`                               | `--port`                                               |

Outras opções do servidor: `--tick-rate` (8; maior = cobras mais rápidas), `--snapshot-rate` (8), `--session-timeout` (5 s, mínimo 0,5), `--max-players` (8), `--seed`. Os limites ficam em `snakenet/config.py` e `snakenet/protocol/limits.py`.

## 5. Protocolo da aplicação e mensagens

Especificação completa (campos, validação, erros, exemplos): **[docs/PROTOCOL.md](docs/PROTOCOL.md)**. Um objeto JSON UTF-8 por datagrama: `{"v":1,"t":"<TIPO>",...}`.

| Tipo                | Sentido     | Finalidade                                                                        |
| ------------------- | ----------- | --------------------------------------------------------------------------------- |
| `JOIN`            | C→S        | pedido para entrar na partida                                                     |
| `WELCOME`         | S→C        | admissão: `pid`, `tok` da sessão, tamanho da arena                          |
| `INPUT`           | C→S        | direção `U/D/L/R` + número de sequência                                     |
| `STATE`           | S→C        | snapshot autoritativo (cobras, comida, pontos), com `seq` para detectar antigos |
| `PING` / `PONG` | C→S / S→C | keep-alive e medição de RTT                                                     |
| `LEAVE`           | C→S        | sair (idempotente)                                                                |
| `ERROR`           | S→C        | erro estruturado: `code` + `msg`                                              |

Exemplos:

```json
{"v":1,"t":"JOIN","name":"ana"}
{"v":1,"t":"WELCOME","pid":1,"tok":"9f2c4a1b7e0d5c33","w":60,"h":40,"tick_rate":8.0,"timeout":5.0}
{"v":1,"t":"INPUT","tok":"9f2c4a1b7e0d5c33","seq":17,"dir":"U"}
{"v":1,"t":"ERROR","code":"BAD_FIELD","msg":"INPUT.dir: expected one of ('U', 'D', 'L', 'R')","ref":"INPUT"}
```

## 6. Tratamento de erros (o que pode dar errado → o que acontece)

| Situação                                                                                             | Tratamento                                                                                                                          |
| ------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------- |
| Servidor fora do ar / inalcançável                                                                   | O cliente tenta JOIN 5 vezes (a cada 0,5 s) e mostra **FAILED: server unavailable** (sem travar); a tecla `R` tenta de novo |
| Nome do servidor não resolve                                                                          | FAILED imediato, com mensagem                                                                                                       |
| Porta em uso / bind inválido                                                                          | O servidor imprime `cannot bind UDP host:port: …` e sai com código 2                                                            |
| JSON inválido, versão errada, tipo desconhecido, campos ausentes/inválidos, datagrama grande demais | Rejeitado antes de tocar no estado do jogo; resposta `ERROR` (até 5/s por endereço); log com limitação de repetição         |
| Entradas: inversão de sentido, direção inválida, flood                                             | Inversão e direção inválida são ignoradas; flood é limitado por token bucket → `RATE_LIMITED`                              |
| `INPUT` duplicado ou fora de ordem, `JOIN` repetido, `LEAVE` repetido                            | Idempotente: ignorado, ou o mesmo `WELCOME` é reenviado; nunca executa duas vezes                                                |
| `STATE` antigo ou duplicado                                                                          | O cliente descarta (`seq` ≤ último aplicado)                                                                                    |
| Datagramas perdidos                                                                                    | O próximo `STATE` substitui o perdido; as teclas são enviadas duas vezes                                                        |
| Token falso, ou token vindo de outro endereço                                                         | `BAD_SESSION`, sem alterar o estado                                                                                               |
| Cliente some                                                                                           | O servidor expira a sessão após o timeout e libera a cobra                                                                        |
| Servidor some / reinicia                                                                               | Cliente: 2 s sem dados → **LOST** e novo JOIN automático; com `SERVER_SHUTDOWN` → FAILED                                 |
| Servidor lotado                                                                                        | `SERVER_FULL` é mostrado ao jogador                                                                                              |
| Exceções inesperadas                                                                                 | Capturadas por datagrama e por tick; o servidor continua rodando                                                                    |

## 7. Pré-requisitos e instalação

Python 3.10+ (desenvolvido no 3.14).

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt        # Windows: .venv\Scripts\pip ...
```

Observação sobre dependência: usa-se o `pygame-ce` (mesma API do `import pygame`) porque o pacote `pygame 2.6.1` para Python 3.14 veio **sem o módulo de fontes**. Servidor, protocolo, jogo e a camada de rede do cliente usam apenas a biblioteca padrão.

## 8. Como executar

```bash
# Terminal 1 – servidor
.venv/bin/python -m snakenet.server --host 127.0.0.1 --port 5000

# Terminais 2, 3, … – clientes (setas / WASD = mover, R = reconectar, Esc = sair)
.venv/bin/python -m snakenet.client --host 127.0.0.1 --port 5000 --name ana
.venv/bin/python -m snakenet.client --host 127.0.0.1 --port 5000 --name bob

# Opcional – bots sem janela, para demonstração/captura
.venv/bin/python -m snakenet.client.bot --port 5000 --name bot1 --duration 60
tools/demo_local.sh            # servidor + 2 bots
```

**Vários clientes no mesmo computador:** rode o comando do cliente em vários terminais; cada um recebe uma porta de origem efêmera própria.
**Em rede local:** na máquina do servidor, rode com `--host 0.0.0.0 --port 5000`, descubra o IP dela na LAN (`ip addr` / `ipconfig`), libere a porta **UDP 5000** no firewall e, nas outras máquinas, rode `python -m snakenet.client --host <IP_DO_SERVIDOR> --port 5000`. *Testado em 22/10/2026 com duas máquinas reais no mesmo hotspot de celular (servidor `10.209.198.22`, cliente `10.209.198.154`); a rede Wi-Fi da faculdade pode isolar os clientes e impedir a conexão. Jogo pela internet não é suportado nem foi testado.*

## 9. Testes e Wireshark

```bash
.venv/bin/python -m pytest          # protocolo, regras do jogo, servidor (UDP real em localhost), cliente e UI sem janela
```

Captura e análise no Wireshark: **[docs/WIRESHARK.md](docs/WIRESHARK.md)** (filtro `udp.port == 5000`). Rastreabilidade com o enunciado: **[docs/COMPLIANCE.md](docs/COMPLIANCE.md)**; apresentação: **[docs/PRESENTATION.md](docs/PRESENTATION.md)**; cronograma: **[docs/PLAN.md](docs/PLAN.md)**.

## 10. Limitações conhecidas

* UDP: sem garantia de entrega; uma tecla totalmente perdida simplesmente se perde. Sem criptografia; os tokens são legíveis na rede. Só IPv4; uma partida por servidor; sem persistência.
* Movimentos simultâneos: duas cabeças que trocam de célula adjacente não colidem. Máximo de 8 jogadores e cobra com no máximo 40 segmentos (mantém o `STATE` ≤ 1472 bytes, testado no pior caso).
* O cliente só aceita datagramas vindos exatamente do IP:porta para o qual enviou (um servidor com várias interfaces que responda por outro IP seria ignorado).
* O comportamento sob perda/latência é coberto por testes de lógica, mas ainda não foi medido com `tc netem`.

## 11. Estado da verificação (resumo honesto)

| Item                                                                                                  | Estado                                                                                                    |
| ----------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| Testes automatizados                                                                                  | **59 passaram** (`pytest`, ~5 s). Mapeamento em COMPLIANCE.md                                     |
| Execução real: servidor + 2 bots + cliente com UI sem janela em localhost, parada limpa com SIGTERM | Observado OK (captura de tela: `evidence/screenshot-headless.png`)                                      |
| Jogo em duas máquinas (janela real) | **Executado em 22/10/2026** (servidor + cliente remoto; teclas do cliente remoto aparecem na captura). Impressão de jogabilidade (velocidade) é subjetiva e não foi medida |
| Teste entre duas máquinas | **Feito em 22/10/2026** pelo hotspot do celular (servidor `10.209.198.22`, cliente `10.209.198.154`); tráfego capturado |
| Captura do Wireshark | **Feita**: 3 capturas reais (loopback e rede real com 2 computadores) + 7 telas do Wireshark em `evidence/`. Análise em docs/WIRESHARK.md §4–7. Falta o experimento de perda de pacotes |
| Experimento de perda de pacotes (`tc netem`)                                                        | Não executado                                                                                            |
