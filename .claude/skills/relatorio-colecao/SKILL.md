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
   - Defina `--posthog-inicio` = a data a partir da qual há dados para essas PDPs (o PostHog só existe desde 28/10/2026; use a maior entre essa data e o início do período pedido). Produtos sem linha no resultado = 0 sessões.

3. **Revisão visual (obrigatória, não pule)** — abra todas as folhas `$W/sheets/*.jpg` com Read e preencha `$W/revisao.json`:
   - `sem_modelo`: ids sem NENHUMA foto com pessoa usando o produto (pés/pernas/corpo contam).
   - `ultima_imagem_e_tabela_de_medidas`: ids cuja última imagem é o guia de medidas verde (não conta como foto).

4. **Montagem**
   `python3 $K/montar.py --dir $W --tag <tag> --colecao "<Nome da coleção>" --posthog-inicio AAAA-MM-DD --views $W/views.csv [--nota "<b>Título:</b> texto"]`
   Gera `$W/relatorio.html` e `$W/grupos.txt` (listas por grupo para escrever a mensagem). Use `--nota` para anomalias encontradas (ex.: produto com vendas mas quase sem sessões = possível falha de rastreio).

5. **Conferir** com um screenshot (Playwright) e publicar `relatorio.html` com a ferramenta Artifact (ícone `chart`). Se for atualização da mesma coleção nesta sessão, republique o mesmo arquivo.

6. **PDF**: `node $K/pdf.js $W/relatorio.html $W/<Colecao>-Analise.pdf` e envie com SendUserFile (`display: attach`).

7. **Mensagem de WhatsApp**: escreva a partir de `grupos.txt` seguindo `mensagem-whatsapp.md`. Entregue num bloco de código para copiar. Lembre que o link do Artifact é privado até ser compartilhado pelo menu Share.

## Grupos (regras em `montar.py`; mantenha-as salvo pedido do usuário)

Média de referência = pedidos ÷ sessões da coleção na janela do PostHog (sem os recentes).
- **Segurar divulgação** (`pausar`): calçado com ≥2 tamanhos centrais (35–38) zerados, ou <60% da grade, ou <10 pares; acessório (variante única) com ≤3 un.
- **Sem ser destaque** (`atencao`): calçado com exatamente 1 tamanho central zerado.
- **Dar mais destaque** (`escalar`): grade saudável (≥80% dos tamanhos, nenhum central zerado, ≥12 pares; acessório ≥6 un.), ≥3 pedidos na janela, conversão ≥1,3× a média e ≤500 sessões.
- **Manter o ritmo** (`manter`): grade cheia ou quase (≥70%, nenhum central zerado, ≥12 pares), conversão ≥ média e ≥4 pedidos.
- **Página incompleta** (`pdp`): grade saudável, ≥90 sessões, conversão <70% da média e falta algum dos 3 elementos (mais de 1 foto, foto com modelo, vídeo).
- **Página completa, mas não vende** (`pdp_ok`): mesmo critério, mas já tem os 3 elementos.
- **Monitorar** e **Recente** (cadastro há <10 dias ou <20 sessões): ficam só na tabela, fora da mensagem.

## Exemplo de referência
`exemplos/` traz a entrega da coleção Verão 27 (17/11/2026): página HTML e PDF. A mensagem correspondente está em `mensagem-whatsapp.md`.
