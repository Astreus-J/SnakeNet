# Rastreabilidade com o enunciado

Legenda: ✅ sim · 🟡 em parte · ⬜ não. **Implementado** = o código existe; **Testado** = teste automatizado ou execução observada; **Documentado**; **Demonstrado** = mostrado ao vivo/com evidência real (ainda pendente em tudo que depende da equipe).
Nada é marcado como totalmente atendido só porque existe um arquivo. Resultado dos testes: `pytest` → 59 passaram (observado).

| Critério (pts) | Implementação | Testes | Docs | Impl. | Testado | Docs | Demo | Lacuna |
|---|---|---|---|---|---|---|---|---|
| Funcionamento cliente-servidor (2,0) | `server/app.py`, `game/world.py`, `client/network.py`, `client/ui.py` | `tests/server/test_server.py`, `tests/client/test_network.py`, `tests/game/test_world.py`, `tests/client/test_ui_smoke.py`; execução observada em localhost com 2 bots + UI | README §8 | ✅ | ✅ | ✅ | 🟡 | Partida jogada por humano e teste em LAN pendentes |
| Implementação dos sockets (1,5) | `server/app.py` (`socket`, `bind`, `recvfrom`, `sendto`, loop com timeout), `client/network.py` (socket + thread) | testes de porta em uso, liberação do socket ao encerrar, `close` do cliente, muitos clientes sem travar o loop | README §3–4, ARCHITECTURE | ✅ | ✅ | ✅ | ⬜ | Mostrar o código ao vivo |
| Protocolo da aplicação (1,5) | `snakenet/protocol/` (schemas, validators, codec, limits, errors) | `tests/protocol/test_codec.py` (18 casos malformados, limite de tamanho) + testes do servidor | `docs/PROTOCOL.md`, README §5 | ✅ | ✅ | ✅ | ⬜ | — |
| Justificativa TCP/UDP (1,5) | escolha de projeto (UDP) + camada de confiabilidade: números de sequência, retentativas, JOIN/LEAVE idempotentes | testes de JOIN duplicado, INPUT duplicado/fora de ordem, STATE antigo | README §3, PROTOCOL §6, PRESENTATION | ✅ | ✅ | ✅ | ⬜ | A equipe precisa saber defender oralmente |
| Tratamento de erros (1,0) | validação em `protocol/`, `server/app.py`, `throttle.py`, `sessions.py`, máquina de estados do cliente | tráfego malformado, limites de taxa, expiração, servidor cheio, servidor indisponível, host não resolvido, perda→recuperação | README §6, PROTOCOL §4–5 | ✅ | ✅ | ✅ | ⬜ | Perda/latência não medidas em enlace real degradado |
| Organização do código (0,5) | pacotes em camadas; os testes espelham os pacotes | — | ARCHITECTURE (tabela de camadas) | ✅ | n/a | ✅ | n/a | — |
| Documentação (0,5) | README, PROTOCOL, ARCHITECTURE, WIRESHARK, PRESENTATION, PLAN, este arquivo | — | — | ✅ | n/a | 🟡 | n/a | Papéis de cada integrante ainda a definir |
| Apresentação (0,5) | plano em `docs/PRESENTATION.md` | — | ✅ | 🟡 | n/a | ✅ | ⬜ | Ensaio pendente |
| Domínio conceitual (1,0) | Perguntas e respostas preparadas em PRESENTATION.md | — | ✅ | n/a | n/a | ✅ | ⬜ | Todos os integrantes precisam estudar |

## Entregas obrigatórias
| Entrega | Estado |
|---|---|
| 1. Código-fonte (cliente + servidor) | ✅ presente, testado |
| 2. README com todos os itens exigidos (descrição, integrantes, arquitetura, TCP/UDP, justificativa, IP/porta, protocolo, mensagens, instruções de execução) | ✅ presente; integrantes listados (papéis a definir) |
| 3. Diagrama da arquitetura | ✅ [ARCHITECTURE.md](ARCHITECTURE.md) (Mermaid) |
| 4. Captura de tráfego e análise no Wireshark | ✅ **capturas reais** (loopback; rede real com 2 computadores) **e 7 telas do Wireshark** em `evidence/` — ver [WIRESHARK.md](WIRESHARK.md) §4–7. Ressalvas: captura de rede real é do lado do servidor; `LEAVE`/`ERROR` só no loopback; experimento de perda não feito |

## As 10 perguntas do enunciado → onde são respondidas
1 problema → README §1 · 2 processos → README §2 · 3 como se comunicam → sequência em ARCHITECTURE + PROTOCOL · 4 transporte → README §3 · 5 por que é adequado → README §3 / PRESENTATION · 6 protocolo da aplicação → PROTOCOL.md · 7 mensagens → README §5 / PROTOCOL §4 · 8 e se fosse o outro protocolo → README §3 / PRESENTATION · 9–10 erros e tratamento → README §6.
