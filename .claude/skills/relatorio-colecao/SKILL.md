---
name: relatorio-colecao
description: Relatório de coleção da Perky Shoes por tag de produto da VNDA (ex. verao-27) — vendas desde o cadastro, grade/estoque, conversão por página de produto (PostHog) e checklist de PDP (fotos, foto com modelo, vídeo PowerClip) — entregue como página Artifact, PDF e mensagem curta de WhatsApp para marketing/design/social media. Use sempre que pedirem análise, relatório, status ou "drop" de uma coleção/tag de produtos, ou quais produtos divulgar, segurar ou ajustar a PDP.
---

# Relatório de coleção (modelo Perky)

Entregas, sempre as três:
1. **Página** (Artifact) no layout do Dashboard E-commerce deste repositório (`index.html`): `template.html`.
2. **PDF** da mesma página (A4 deitado) enviado ao usuário com SendUserFile para anexar no WhatsApp.
3. **Mensagem de WhatsApp** única e curta, seguindo `mensagem-whatsapp.md` à risca (linguagem de divulgação orgânica).

Escreva tudo em português. Trabalhe numa pasta do scratchpad (`$W`). `$K` = esta pasta da skill.

## Passo a passo

1. **Coleta (VNDA + PowerClip + imagens)**
   `python3 $K/coletar.py --tag <tag> --out $W`
   - api.vnda.com.br é autenticada pelo proxy; não precisa de chave.
   - Vídeo da PDP = widget **PowerClip da Performa** (não é a Bevean). O script lê o manifesto e marca com vídeo quem tem clipe ativo.
   - A API não tem data de criação do produto: usamos a data da 1ª imagem como "cadastro".

2. **Acessos (PostHog)** — projeto "Default project" (id 694276), fuso America/Sao_Paulo.
   Rode o conteúdo de `$W/posthog.sql` com `execute-sql` (siga as regras do servidor PostHog: confirme `$pageview`/`$pathname` com `read-data-schema` antes). Salve o resultado em `$W/views.csv` como linhas `id,sessoes` (sem cabeçalho).
   - Desde 25/11/2026 uma transformação "Drop Events" descarta tudo exceto `$pageview`, `purchase` e eventos de identificação (para caber na cota gratuita). Não planeje análises com autocapture, pageleave, web vitals ou exceções.
   - **Antes de tudo, confira se o PostHog está coletando**: rode `SELECT toDate(timestamp) dia, countIf(event='$pageview') FROM events WHERE timestamp >= now() - INTERVAL 30 DAY GROUP BY dia ORDER BY dia` e `billing-overview-get`. O projeto é plano gratuito (1 milhão de eventos/mês, ciclo renova dia 27); ao estourar, a coleta para (aconteceu em 12/11/2026). A janela de conversão deve terminar no último dia com coleta normal, e os pedidos devem usar **a mesma janela** que as sessões. Se houver buraco, avise o usuário e diga até quando os dados valem.
   - Defina `--posthog-inicio` = a data a partir da qual há dados para essas PDPs (o PostHog só existe desde 28/10/2026; use a maior entre essa data e o início do período pedido). Produtos sem linha no resultado = 0 sessões.

3. **Revisão visual (obrigatória, não pule)** — abra todas as folhas `$W/sheets/*.jpg` com Read e preencha `$W/revisao.json`:
   - `sem_modelo`: ids sem NENHUMA foto com pessoa usando o produto (pés/pernas/corpo contam).
   - `ultima_imagem_e_tabela_de_medidas`: ids cuja última imagem é o guia de medidas verde (não conta como foto).

4. **Montagem**
   `python3 $K/montar.py --dir $W --tag <tag> --colecao "<Nome da coleção>" --posthog-inicio AAAA-MM-DD [--posthog-fim AAAA-MM-DD] --views $W/views.csv [--nota "<b>Título:</b> texto"]`
   Gera `$W/relatorio.html` e `$W/grupos.txt` (listas por grupo para escrever a mensagem). Use `--nota` para anomalias encontradas (ex.: produto com vendas mas quase sem sessões = possível falha de rastreio).

5. **Conferir** com um screenshot (Playwright) e publicar `relatorio.html` com a ferramenta Artifact (ícone `chart`). Se for atualização da mesma coleção nesta sessão, republique o mesmo arquivo.

6. **PDF**: `node $K/pdf.js $W/relatorio.html $W/<Colecao>-Analise.pdf` e envie com SendUserFile (`display: attach`).

7. **Mensagem de WhatsApp**: escreva a partir de `grupos.txt` seguindo `mensagem-whatsapp.md`. Entregue num bloco de código para copiar. Lembre que o link do Artifact é privado até ser compartilhado pelo menu Share.

## Edições de acompanhamento (comparar com o relatório anterior)
- Compare vendas por dia (antes × últimos 7 dias), estoque/tamanhos centrais, preço e status (ativo) por produto, agrupando pelos grupos da mensagem anterior. Normalize pelo total da loja (pedidos/dia) antes de concluir.
- Monte um JSON `{desde, nota, blocos:[{titulo, tom: go|stop|warn|idle, itens:[html]}]}` e passe com `--mudancas`; vira o bloco "O que mudou" no topo da aba Ações.
- Produtos cuja página ganhou vídeo ou foto com modelo depois da janela de conversão: passe os ids em `--pagina-atualizada`. Eles vão para "Página atualizada, aguardando resultado" em vez de "página completa, mas não vende" (a conversão medida é de antes da mudança).
- Publique como Artifact novo (o anterior fica como histórico) e na mensagem destaque o que o time de design/social já entregou.

## Grupos (regras em `montar.py`; mantenha-as salvo pedido do usuário)

Média de referência = pedidos ÷ sessões da coleção na janela do PostHog (sem os recentes).
- **Segurar divulgação** (`pausar`): calçado com ≥2 tamanhos centrais (35–38) zerados, ou <60% da grade, ou <10 pares; acessório (variante única) com ≤3 un.
- **Sem ser destaque** (`atencao`): calçado com exatamente 1 tamanho central zerado.
- **Dar mais destaque** (`escalar`): grade saudável (≥80% dos tamanhos, nenhum central zerado, ≥12 pares; acessório ≥6 un.), ≥3 pedidos na janela, conversão ≥1,3× a média e ≤500 sessões.
- **Manter o ritmo** (`manter`): grade cheia ou quase (≥70%, nenhum central zerado, ≥12 pares), conversão ≥ média e ≥4 pedidos.
- **Página incompleta** (`pdp`): grade saudável, ≥90 sessões, conversão <70% da média e falta algum dos 3 elementos (mais de 1 foto, foto com modelo, vídeo).
- **Página completa, mas não vende** (`pdp_ok`): mesmo critério, mas já tem os 3 elementos.
- **Página atualizada, aguardando** (`pdp_novo`): página completada depois da janela de conversão (via `--pagina-atualizada`).
- **Monitorar** e **Recente** (cadastro há <10 dias ou <20 sessões): ficam só na tabela, fora da mensagem.

## Exemplo de referência
`exemplos/` traz a entrega da coleção Verão 27 (17/11/2026): página HTML e PDF. A mensagem correspondente está em `mensagem-whatsapp.md`.
