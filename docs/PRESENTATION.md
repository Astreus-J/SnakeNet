# Plano da apresentação (≤ 10 minutos)

Apresentadora: **Maria Pereira**. Apoio na demonstração: Jeiel Santos.

| # | Min | Tópico | O que mostrar / dizer |
|---|---|---|---|
| 1 | 1:00 | Problema e solução | Jogo multiplayer em tempo real exige que vários processos compartilhem um mundo consistente com baixa latência. SnakeNet: arena em que vários clientes jogam a mesma partida por meio de um servidor autoritativo. |
| 2 | 1:00 | Arquitetura | Diagrama de [ARCHITECTURE.md](ARCHITECTURE.md): N clientes ⇄ 1 servidor, cada um com seu socket UDP; o servidor é dono do estado; os clientes enviam *entradas* e recebem *snapshots*. |
| 3 | 1:30 | Implementação dos sockets | `server/app.py`: `socket(AF_INET, SOCK_DGRAM)`, `bind`, `recvfrom`/`sendto`, timeout = tempo até o próximo tick. `client/network.py`: socket próprio e thread de recepção, para o desenho nunca travar. Mostrar a configuração de ip:porta. |
| 4 | 1:30 | Por que UDP (e não TCP) | Próxima seção. |
| 5 | 1:30 | Protocolo da aplicação | [PROTOCOL.md](PROTOCOL.md): envelope JSON `{v,t,...}`; JOIN/WELCOME/INPUT/STATE/PING/PONG/LEAVE/ERROR; números de sequência; validação. |
| 6 | 2:00 | Demonstração ao vivo | Servidor + 2–3 clientes (um humano, bots). Comer, crescer, morrer, placar. Derrubar o servidor → o cliente mostra *connection lost*; reiniciar → `R` reconecta. Enviar lixo com `nc -u` → o servidor sobrevive. |
| 7 | 1:00 | Wireshark | Abrir `evidence/snakenet.pcapng` (captura real, 558 pacotes) e seguir o roteiro da seção "Evidências reais" abaixo. |
| 8 | 0:30 | Erros e conclusão | Tabela falha → tratamento; limitações; o que aprendemos. |

## Evidências reais para mostrar (Wireshark)

Arquivo: `evidence/snakenet.pcapng` — captura real feita em 22/10/2026 no loopback, filtro de captura `udp port 5100`, 558 pacotes.
Abrir com: `wireshark evidence/snakenet.pcapng` (se der "sem permissão", use `newgrp wireshark` antes, ou faça logout/login).

**Roteiro de 1 minuto no Wireshark** (aplique o filtro na barra superior):

| Passo | Filtro | O que apontar |
|---|---|---|
| 1. Visão geral | `udp.port == 5100` | Só UDP, sem SYN/ACK de handshake. O primeiro pacote já é o `JOIN`. |
| 2. Entrada | `frame contains "\"t\":\"JOIN\""` | Origem `127.0.0.1:57362` → destino `127.0.0.1:5100`. A porta do cliente é efêmera; a do servidor é fixa. |
| 3. Resposta | `frame contains "\"t\":\"WELCOME\""` | `pid`, `tok` e o tamanho da arena (60×40). Botão direito → *Follow → UDP Stream* mostra o JSON em texto. |
| 4. Entrada de teclas | `frame contains "\"t\":\"INPUT\""` | Pequeno (63 bytes) e **sempre em pares com o mesmo `seq`** (redundância contra perda). |
| 5. Estado | `frame contains "\"t\":\"STATE\""` | ~418 bytes, 8 por segundo para cada cliente, com `seq` crescente (1…96, nenhum faltando). |
| 6. Erro | `frame contains "\"t\":\"ERROR\""` | Resposta `BAD_JSON` ao `hello` enviado com `nc`. O servidor continuou funcionando. |

**Números para citar:** 2 clientes, 278 pacotes com cada um; `INPUT` 324 pacotes; `STATE` 192 (96 por cliente); `PING`/`PONG` 16/16 (a cada ~1,67 s); `LEAVE` 4 (2 por cliente, enviados em dobro). Fonte: tabela em [WIRESHARK.md](WIRESHARK.md) §4.

**Captura em rede real (dois computadores):** `evidence/snakenet-rede-real.pcapng` — 726 pacotes em 60 s, servidor `10.209.198.22:5000` e cliente `10.209.198.154:36099` (hotspot do celular). Filtro: `udp.port == 5000`. Mostrar: IPs de origem e destino diferentes; `STATE` 480 pacotes (8/s, `seq` 505→984 sem lacunas); `INPUT` 176 pacotes em pares com o mesmo `seq`; `PING`/`PONG` ≈ a cada 1,7 s. Detalhes e ressalvas em [WIRESHARK.md](WIRESHARK.md) §5.

**Segunda captura em rede real, com `JOIN`/`WELCOME`:** `evidence/snakenet-rede-real-join.pcapng` — 1119 pacotes em 90 s. Filtro `frame contains "\"t\":\"JOIN\""`: três `JOIN` do mesmo `10.209.198.154:36099` (#684, #705, #715) e três `WELCOME` **idênticos** (`pid:1`, mesmo `tok`) — prova de que o `JOIN` repetido é idempotente e não duplica o jogador. `STATE` seq 2714→3434 sem lacunas.

**Limites da evidência (dizer com honestidade se perguntarem):** a captura de loopback usa `127.0.0.1` nos dois lados. A de rede real foi feita **no servidor**, então mostra o que ele enviou; perda que ocorra depois, no hotspot, não aparece ali. Em rede real ainda não há `LEAVE` nem `ERROR` (só na captura de loopback). O experimento com perda simulada (`tc netem`) não foi feito.

### Para a demonstração ao vivo e a captura em rede real (fazer antes de apresentar)
- [x] (feito em 22/10) Os dois notebooks no **mesmo hotspot do celular** (o Wi-Fi da faculdade pode isolar os clientes: `ping` falha com "destino inalcançável").
- [ ] Servidor no notebook do Jeiel: `.venv/bin/python -m snakenet.server --host 0.0.0.0 --port 5000`; anotar o IP com `ip -4 addr show wlp4s0`.
- [ ] Maria roda: `python -m snakenet.client --host IP_DO_SERVIDOR --port 5000 --name maria` (clone novo do repositório + `pip install -r requirements.txt`).
- [ ] Firewall do servidor liberando UDP 5000 (`sudo nft insert rule inet filter input udp dport 5000 accept`).
- [ ] Capturar na interface do Wi-Fi (`wlp4s0`) com filtro `udp port 5000`; salvar em `evidence/` e anotar os IPs reais em [WIRESHARK.md](WIRESHARK.md) §4.
- [ ] Plano B se a rede não colaborar: demonstrar tudo em um só computador (servidor + 2 clientes) e mostrar a captura do loopback acima.

## UDP × TCP (argumentos)

* Um novo snapshot **substitui** o anterior, então retransmitir um antigo é trabalho desperdiçado. O TCP retransmitiria e *seguraria* os dados novos atrás do segmento perdido (**bloqueio de cabeça de fila**, *head-of-line blocking*), causando travadas visíveis.
* O UDP não tem estabelecimento de conexão: o primeiro datagrama já é o `JOIN`. Não há estado de conexão por cliente no kernel; o servidor controla as sessões por conta própria (token + endereço + timeout).
* **Fronteiras de mensagem:** um datagrama = uma mensagem, então não há código de enquadramento. O TCP é um fluxo de bytes: precisaríamos de prefixo de tamanho ou delimitadores, e uma leitura poderia devolver meia mensagem.
* O que o UDP nos custa e o que acrescentamos: perda/reordenação/duplicação → números de sequência (`STATE` antigo descartado, `INPUT` duplicado ignorado), retentativas de JOIN (limitadas e idempotentes), timeouts para pares mortos, redundância nas entradas. **Não** reconstruímos o TCP.
* Se usássemos TCP: a confiabilidade ficaria mais simples, mas o enquadramento passaria a ser problema nosso; entrar = handshake de 3 vias; uma conexão por jogador; um segmento perdido trava todo o estado seguinte; seria preciso ajustar Nagle/ACK atrasado (`TCP_NODELAY`). Em compensação, seria a melhor escolha para chat, login ou transferência de arquivos.

## Perguntas individuais prováveis

| Pergunta | Resposta curta |
|---|---|
| O UDP é confiável/ordenado? | Não. Datagramas podem se perder, duplicar ou chegar fora de ordem. Tratamos isso na aplicação, só onde importa. |
| O que identifica uma "conexão" UDP? | Não existe conexão. O servidor indexa as sessões pelo token secreto e pela origem (IP, porta). |
| O que é um socket? | O ponto de comunicação do processo no sistema operacional, identificado por protocolo + IP local + porta. |
| Por que o cliente não faz bind em uma porta? | O SO atribui uma porta de origem efêmera no primeiro `sendto`; o servidor responde para esse endereço. |
| IP × porta? | O IP escolhe a máquina (camada de rede); a porta escolhe o processo nela (camada de transporte). |
| E se um `STATE` se perder? | Nada: o próximo chega em ~125 ms e traz o mundo inteiro. |
| E se o `JOIN` ou o seu `WELCOME` se perder? | O cliente tenta de novo (5 × 0,5 s); o servidor responde a um JOIN repetido com o mesmo `WELCOME`, então não há jogador duplicado. Senão: *server unavailable*. |
| Por que o servidor precisa ser autoritativo? | Clientes podem mentir ou atrasar; o servidor valida as entradas e decide os resultados, assim todos convergem para um único estado. |
| Por que enviar a entrada duas vezes? | Seguro barato contra perda; mesmo `seq`, então o servidor ignora a cópia. |
| Tamanho máximo do datagrama? | O payload UDP vai até ~65 507 B, mas limitamos os pacotes do servidor a 1472 B (MTU − IP − UDP) para evitar fragmentação IP. |
| O que o cliente faz ao receber `BAD_SESSION`? | Considera a sessão perdida e faz JOIN de novo. |
| Alguém consegue roubar minha cobra? | Precisaria do token **e** do meu IP:porta; os tokens não são criptografados, então um atacante no caminho conseguiria (limitação documentada). |
| Por que JSON? | Legível no Wireshark e fácil de validar; custa bytes em comparação a um formato binário. |
| Por que o servidor tem uma só thread? | Sem condições de corrida em estado compartilhado; um loop lê, simula e envia. O envio UDP nunca espera o receptor. |
