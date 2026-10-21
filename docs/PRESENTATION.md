# Plano da apresentação (≤ 10 minutos)

| # | Min | Tópico | O que mostrar / dizer |
|---|---|---|---|
| 1 | 1:00 | Problema e solução | Jogo multiplayer em tempo real exige que vários processos compartilhem um mundo consistente com baixa latência. SnakeNet: arena em que vários clientes jogam a mesma partida por meio de um servidor autoritativo. |
| 2 | 1:00 | Arquitetura | Diagrama de [ARCHITECTURE.md](ARCHITECTURE.md): N clientes ⇄ 1 servidor, cada um com seu socket UDP; o servidor é dono do estado; os clientes enviam *entradas* e recebem *snapshots*. |
| 3 | 1:30 | Implementação dos sockets | `server/app.py`: `socket(AF_INET, SOCK_DGRAM)`, `bind`, `recvfrom`/`sendto`, timeout = tempo até o próximo tick. `client/network.py`: socket próprio e thread de recepção, para o desenho nunca travar. Mostrar a configuração de ip:porta. |
| 4 | 1:30 | Por que UDP (e não TCP) | Próxima seção. |
| 5 | 1:30 | Protocolo da aplicação | [PROTOCOL.md](PROTOCOL.md): envelope JSON `{v,t,...}`; JOIN/WELCOME/INPUT/STATE/PING/PONG/LEAVE/ERROR; números de sequência; validação. |
| 6 | 2:00 | Demonstração ao vivo | Servidor + 2–3 clientes (um humano, bots). Comer, crescer, morrer, placar. Derrubar o servidor → o cliente mostra *connection lost*; reiniciar → `R` reconecta. Enviar lixo com `nc -u` → o servidor sobrevive. |
| 7 | 1:00 | Wireshark | Abrir a captura real: UDP, portas, `JOIN`, pares de `INPUT`, `STATE` a 8 Hz, `ERROR`. (Tem que ser a captura de vocês — veja [WIRESHARK.md](WIRESHARK.md).) |
| 8 | 0:30 | Erros e conclusão | Tabela falha → tratamento; limitações; o que aprendemos. |

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
