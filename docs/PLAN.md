# SnakeNet — Plano: ciclos e tarefas

Prazo: **28/10/2026**. Fonte para sincronizar: [`project-management/plane/plan.json`](../project-management/plane/plan.json) (mesmos IDs `SN-n`).

> **Sincronização com o Plane: NÃO feita.** Não há valores de `PLANE_API_KEY`/`PLANE_BASE_URL`/identificador do projeto neste ambiente (o repositório do JuriSense só nomeia as variáveis; `~/.config/Plane` é o cache do app desktop, de onde deliberadamente não foram extraídos tokens de sessão). Depois de exportar as quatro variáveis: `python tools/plane_sync.py` (simulação) e depois `python tools/plane_sync.py --apply`. Use um projeto dedicado ao SnakeNet.

"Feito" significa escrito **e** coberto pela execução observada do `pytest` (59 passaram) ou por uma execução real observada, salvo indicação na linha.


## Ciclo 1 - Núcleo de rede (2026-10-15 → 2026-10-17)

| ID | Tarefa | Estado |
|---|---|---|
| SN-1 | Inspecionar repositório e PDF do enunciado | ✅ feito |
| SN-2 | Pacote de protocolo: schemas, validadores, codec, limites | ✅ feito |
| SN-3 | Simulação do jogo (domínio puro) | ✅ feito |
| SN-4 | Servidor UDP: sessões, validação, loop de ticks, expiração | ✅ feito |
| SN-5 | Camada de rede do cliente (thread, retentativa de JOIN, descarte de antigos, detecção de perda) | ✅ feito |
| SN-6 | Configuração do repositório (git, .gitignore, dependências, pytest) | ✅ feito |

## Ciclo 2 - Jogo jogável e testes (2026-10-18 → 2026-10-21)

| ID | Tarefa | Estado |
|---|---|---|
| SN-7 | Interface pygame: arena, cobras, comida, placar, faixa de status | ✅ feito |
| SN-8 | Cliente bot para demonstrações e capturas | ✅ feito |
| SN-9 | Testes automatizados dos 14 cenários exigidos | ✅ feito |
| SN-10 | Teste de fumaça da UI sem janela + captura de tela | ✅ feito |
| SN-11 | Execução observada com vários clientes em localhost | ✅ feito |

## Ciclo 3 - Evidências e documentação (2026-10-22 → 2026-10-25)

| ID | Tarefa | Estado |
|---|---|---|
| SN-12 | README com todos os itens exigidos pelo PDF | ✅ feito |
| SN-13 | Especificação do protocolo | ✅ feito |
| SN-14 | Diagrama da arquitetura | ✅ feito |
| SN-15 | Guia do Wireshark e script auxiliar de captura | ✅ feito |
| SN-16 | Captura real no Wireshark e telas em evidence/ | 🧍 pendente (precisa da equipe) |
| SN-17 | Teste em LAN com uma segunda máquina (registrar IPs/portas reais) | 🧍 pendente (precisa da equipe) |
| SN-18 | Tabela de rastreabilidade com o enunciado | ✅ feito |

## Ciclo 4 - Apresentação e folga (2026-10-26 → 2026-10-28)

| ID | Tarefa | Estado |
|---|---|---|
| SN-19 | Plano da apresentação e perguntas e respostas | ✅ feito |
| SN-20 | Ensaiar a demonstração de 10 minutos; todos explicam o código | 🧍 pendente (precisa da equipe) |
| SN-21 | Verificação final dos comandos documentados em venv limpo | ⬜ a fazer |
| SN-22 | Definir o papel de cada integrante no README | 🧍 pendente (precisa da equipe) |
| SN-23 | Opcional: boost, som, menu (só se todo o resto estiver pronto) | ⬜ a fazer |

## Trabalho restante (tudo depende da equipe)
1. **SN-16 Captura no Wireshark** — única entrega obrigatória que falta; siga [WIRESHARK.md](WIRESHARK.md).
2. SN-17 teste em LAN com duas máquinas, SN-20 ensaio, SN-22 nomes da equipe, SN-21 verificação em venv limpo.

## Riscos
| Risco | Mitigação |
|---|---|
| Sem permissão de captura no ambiente de desenvolvimento | Capturar em uma máquina da equipe; procedimento e filtros prontos; a evidência precisa ser genuína |
| Firewall bloqueia UDP 5000 de entrada na demonstração em LAN | Testar cedo (SN-17); plano B: demonstração em localhost |
| Escolha da interface de loopback no Wireshark | Documentado (`lo` / Npcap Loopback Adapter) |
| Crescimento do tamanho do snapshot | Limites (8 jogadores, tamanho 40, comida ≤ alvo+10) + teste do pior caso |
| Pacote pygame sem fontes no Python 3.14 | Troca para `pygame-ce` (documentado no README) |
