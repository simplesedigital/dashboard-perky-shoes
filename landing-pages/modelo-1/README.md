# Modelo 1 – Landing page de pacote de viagem

Layout criado para o pacote **Buenos Aires Roteiro Completo (Uni Explorer)**, reutilizável para outros destinos e pacotes.
Arquivo único (`index.html`), com HTML, CSS e JS juntos, pronto para colar num bloco HTML do ActiveCampaign ou publicar em qualquer hospedagem.

## Seções
1. Barra de urgência fixa (vagas + data)
2. Hero com headline, checklist de inclusos e card de preço/reserva
3. Faixa de confiança (números da empresa)
4. O que está incluso (6 cards)
5. Experiências com fotos (3 cards)
6. Roteiro dia a dia (timeline)
7. Opções de hospedagem (2 planos)
8. Por que viajar com a gente + contagem regressiva
9. Depoimentos
10. Oferta final
11. FAQ
12. Rodapé + WhatsApp flutuante + barra de compra fixa no celular

## Para reutilizar
- **WhatsApp:** troque `5500000000000` pelo número (55 + DDD + número) em todos os links.
- **Imagens:** no topo do `<style>`, troque as variáveis `--img-hero`, `--img-tigre`, `--img-city`, `--img-onibus`.
- **Cores:** variáveis `--azul`, `--celeste`, `--sol` no `:root`.
- **Contagem regressiva:** data no `<script>` final (`new Date("2026-11-19T00:00:00-03:00")`).
- **Barra de vagas:** `.bar i { width: 72% }`.
- **Textos:** destino, data, preço, roteiro, hotéis, depoimentos (use só depoimentos reais) e FAQ.
