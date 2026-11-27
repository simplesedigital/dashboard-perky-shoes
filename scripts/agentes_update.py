#!/usr/bin/env python3
"""Atualiza os pedidos de agentes (vendedores) embutidos no index.html (linha `const AGENTES = ...;`).

Uso:  python3 scripts/agentes_update.py [--desde AAAA-MM-DD] [--completo]

Busca os pedidos na API v2 da VNDA e guarda só os que têm agente (campo `agent`),
mais o total de pedidos/receita do site por dia e status (para o % do total).
Por padrão reaproveita o que já está gravado e busca de novo só os últimos 60 dias
(status e valores podem mudar: cancelamentos, reembolsos). `--completo` refaz tudo.

Token: em sessões do Claude o proxy injeta a credencial da VNDA; em outra máquina,
defina a variável VNDA_TOKEN.
Não grava dados pessoais do cliente (nome, e-mail, documento, endereço).
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

BASE = "https://api.vnda.com.br/api/v2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
TOKEN = os.environ.get("VNDA_TOKEN", "proxy-injected")
BRT = timezone(timedelta(hours=-3))
INICIO_HISTORICO = "2023-07-01"
JANELA_REFRESH = 60  # dias rebuscados a cada execução

# Nome de exibição de cada código de agente (o código vem da VNDA). Preencha quando souber.
NOMES = {
    "MORAES": "MORAES",
    "MARI SAMPAIO": "MARI SAMPAIO",
}

PREFIXO = "const AGENTES = "
MARCADOR = "/* ---------------- VENDAS: AGENTES"


def get(path, tries=5):
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers={
                "Authorization": "Bearer " + TOKEN, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def pedidos_do_mes(ini, fim):
    """Todos os pedidos (qualquer status) recebidos entre ini e fim (inclusive)."""
    out, p = [], 1
    while True:
        r = get(f"/orders?start={ini}&finish={fim}&per_page=100&page={p}")
        if not r or not isinstance(r, list):
            break
        out += r
        p += 1
    return out


def meses(ini, fim):
    d = date.fromisoformat(ini).replace(day=1)
    fim_d = date.fromisoformat(fim)
    while d <= fim_d:
        prox = (d.replace(day=28) + timedelta(days=4)).replace(day=1)
        a = max(d, date.fromisoformat(ini))
        b = min(prox - timedelta(days=1), fim_d)
        yield a.isoformat(), b.isoformat()
        d = prox


def load_previous():
    for l in open(INDEX, encoding="utf-8", newline=""):
        if l.startswith(PREFIXO):
            return json.loads(l[len(PREFIXO):].rstrip().rstrip(";"))
    return None


def main():
    hoje = datetime.now(BRT).date()
    completo = "--completo" in sys.argv
    prev = None if completo else load_previous()
    if "--desde" in sys.argv:
        desde = sys.argv[sys.argv.index("--desde") + 1]
    elif prev:
        desde = (hoje - timedelta(days=JANELA_REFRESH)).isoformat()
    else:
        desde = INICIO_HISTORICO
    fim = (hoje + timedelta(days=1)).isoformat()

    janelas = list(meses(desde, fim))
    with ThreadPoolExecutor(4) as ex:
        lotes = list(ex.map(lambda j: pedidos_do_mes(*j), janelas))
    vistos, pedidos = set(), []
    for lote in lotes:
        for o in lote:
            if o["code"] in vistos:
                continue
            vistos.add(o["code"])
            pedidos.append(o)
    print(f"VNDA: {len(pedidos)} pedidos de {desde} a {hoje}", file=sys.stderr)

    rows, totais = [], {}
    for o in pedidos:
        dia = (o.get("received_at") or "")[:10]
        if not dia or dia < desde:
            continue
        st = o.get("status") or ""
        t = totais.setdefault((dia, st), [0, 0.0])
        t[0] += 1
        t[1] += float(o.get("total") or 0)
        ag = (o.get("agent") or "").strip()
        if ag:
            rows.append([o["code"], dia, st, ag, round(float(o.get("total") or 0), 2),
                         o.get("coupon_code") or "", round(float(o.get("discount_price") or 0), 2)])

    # junta com o histórico anterior a `desde`
    if prev:
        rows = [r for r in prev["rows"] if r[1] < desde] + rows
        tot_old = [t for t in prev["totais"] if t[0] < desde]
    else:
        tot_old = []
    tot_new = [[d, s, n, round(v, 2)] for (d, s), (n, v) in totais.items()]
    tot = sorted(tot_old + tot_new, key=lambda t: (t[0], t[1]))
    rows.sort(key=lambda r: (r[1], r[0]))

    agentes = sorted({r[3] for r in rows})
    nomes = dict((prev or {}).get("nomes", {}))
    nomes.update({k: v for k, v in NOMES.items()})
    for a in agentes:
        nomes.setdefault(a, a)
    payload = {
        "atualizado_em": datetime.now(BRT).strftime("%Y-%m-%dT%H:%M"),
        "cols": ["pedido", "data", "status", "agente", "valor", "cupom", "desconto"],
        "totais_cols": ["data", "status", "pedidos", "receita"],
        "nomes": nomes,
        "rows": rows,
        "totais": tot,
    }
    line = PREFIXO + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"

    html = open(INDEX, encoding="utf-8", newline="").read()
    nl = "\r\n" if "\r\n" in html else "\n"
    lines = html.split(nl)
    pos = next((i for i, l in enumerate(lines) if l.startswith(PREFIXO)), None)
    if pos is not None:
        lines[pos] = line
    else:
        # longe da linha DATA (que a rotina da VNDA reescreve) para o git não ver conflito
        mpos = next(i for i, l in enumerate(lines) if l.startswith(MARCADOR))
        lines.insert(mpos, line)
    open(INDEX, "w", encoding="utf-8", newline="").write(nl.join(lines))
    print(f"AGENTES gravado: {len(rows)} pedidos de {len(agentes)} agentes, {len(tot)} linhas de totais, "
          f"{len(line)//1024} KB", file=sys.stderr)


if __name__ == "__main__":
    main()
