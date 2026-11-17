#!/usr/bin/env python3
"""Atualiza os dados da Troquecommerce embutidos no index.html (linha `const TROQUE = ...;`).

Uso:  python3 scripts/troque_update.py [--cache DIR]

Token: header `token` da API pública. Em sessões do Claude o proxy injeta o token;
em outra máquina, defina a variável TROQUE_TOKEN.
Não grava dados pessoais do cliente (nome, e-mail, documento, endereço, comentários).
"""
import json, os, re, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

BASE = "https://www.troquecommerce.com.br/api/public"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(ROOT, "index.html")
TOKEN = os.environ.get("TROQUE_TOKEN", "proxy-injected")
BRT = timezone(timedelta(hours=-3))
CACHE = None
if "--cache" in sys.argv:
    CACHE = sys.argv[sys.argv.index("--cache") + 1]
    os.makedirs(CACHE, exist_ok=True)


def get(path, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(BASE + path, headers={"token": TOKEN, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if i == tries - 1:
                raise
            time.sleep(2 * (i + 1))


def detail(oid):
    if CACHE:
        p = os.path.join(CACHE, oid + ".json")
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            return d
    d = get("/order?id=" + oid)
    if CACHE:
        json.dump(d, open(os.path.join(CACHE, oid + ".json"), "w", encoding="utf-8"))
    return d


def brt_date(s):
    if not s:
        return None
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(BRT).strftime("%Y-%m-%d")


def ref_of(sku):
    # SKU pode vir como referência (MINITOT35406) ou variante (ACW25807-34)
    return re.sub(r"-[^-]+$", "", sku) if sku and re.search(r"-\d{2}$", sku) else (sku or "")


def load_previous():
    """Solicitações já gravadas no index.html: id -> (updated_at, linha)."""
    for l in open(INDEX, encoding="utf-8", newline=""):
        if l.startswith("const TROQUE = "):
            old = json.loads(l[len("const TROQUE = "):].rstrip().rstrip(";"))
            if "ids" not in old:
                return {}
            dicts = {k: old[k] for k in ("tipos", "status", "motivos", "submotivos", "transportadoras")}
            return {i: (u, r, dicts) for (i, u), r in zip(old["ids"], old["rows"])}
    return {}


def main():
    prev = load_previous()
    first = get("/order/list?page=1")
    pages = first.get("total_pages", 1)
    rows = list(first["list"])
    for p in range(2, pages + 1):
        rows += get(f"/order/list?page={p}")["list"]
    print(f"lista: {len(rows)} solicitações em {pages} páginas", file=sys.stderr)

    # só busca o detalhe do que é novo ou mudou desde a última atualização
    novos = [r["id"] for r in rows if r["id"] not in prev or prev[r["id"]][0] != r.get("updated_at")]
    print(f"detalhes a buscar: {len(novos)} (reaproveitando {len(rows) - len(novos)})", file=sys.stderr)
    with ThreadPoolExecutor(6) as ex:
        fetched = dict(zip(novos, ex.map(detail, novos)))

    reasons, subs, types, statuses, couriers = [], [], [], [], []
    def idx(lst, v):
        v = v or ""
        if v not in lst:
            lst.append(v)
        return lst.index(v)

    def remap(row, dd):
        # linha antiga usa índices dos dicionários antigos: reindexa nos novos
        row = list(row)
        row[2] = idx(types, dd["tipos"][row[2]])
        row[3] = idx(statuses, dd["status"][row[3]])
        row[7] = idx(couriers, dd["transportadoras"][row[7]])
        row[12] = [[*it[:4], idx(reasons, dd["motivos"][it[4]]), idx(subs, dd["submotivos"][it[5]]), *it[6:]]
                   for it in row[12]]
        return row

    out, id_list = [], []
    for r in rows:
        oid, upd = r["id"], r.get("updated_at")
        if oid not in fetched:
            out.append(remap(prev[oid][1], prev[oid][2]))
            id_list.append([oid, upd])
            continue
        d = fetched[oid]
        id_list.append([oid, upd])
        tr = d.get("tracking") or {}
        items = []
        for it in d.get("items") or []:
            if it.get("is_added_by_operator") and not it.get("reason"):
                continue
            rs = it.get("reason") or {}
            items.append([
                ref_of(it.get("sku")),
                it.get("sku") or "",
                it.get("quantity") or it.get("original_quantity") or 1,
                round(it.get("price") or 0, 2),
                idx(reasons, rs.get("description")),
                idx(subs, rs.get("sub_reason")),
                1 if it.get("is_exchange") else 0,
                it.get("replaced_item_sku") or "",
                1 if it.get("is_removed") else 0,
            ])
        out.append([
            d.get("ecommerce_number") or "",
            brt_date(d.get("created_at")),
            idx(types, d.get("reverse_type")),
            idx(statuses, d.get("status")),
            round(d.get("price") or 0, 2),
            round(d.get("exchange_value") or 0, 2),
            round(d.get("refund_value") or 0, 2),
            idx(couriers, tr.get("courier_company")),
            brt_date(tr.get("posted_date")),
            brt_date(tr.get("delivery_date")),
            1 if d.get("is_complete") else 0,
            1 if d.get("is_second_request") or d.get("is_second_reverse") else 0,
            items,
        ])
    order = sorted(range(len(out)), key=lambda i: out[i][1] or "")
    out = [out[i] for i in order]
    id_list = [id_list[i] for i in order]
    payload = {
        "atualizado_em": datetime.now(BRT).strftime("%Y-%m-%dT%H:%M"),
        "cols": ["pedido", "data", "tipo", "status", "valor", "valor_troca", "valor_reembolso",
                 "transportadora", "postado", "entregue", "concluida", "segunda_solicitacao", "itens"],
        "item_cols": ["ref", "sku", "qtd", "preco", "motivo", "submotivo", "troca", "sku_novo", "removido"],
        "tipos": types, "status": statuses, "motivos": reasons, "submotivos": subs, "transportadoras": couriers,
        "rows": out,
        "ids": id_list,
    }
    line = "const TROQUE = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";"

    html = open(INDEX, encoding="utf-8", newline="").read()
    lines = html.split("\n")
    pos = next((i for i, l in enumerate(lines) if l.startswith("const TROQUE = ")), None)
    if pos is not None:
        lines[pos] = line
    else:
        # longe da linha DATA (que a rotina da VNDA reescreve) para o git não ver conflito
        dpos = next(i for i, l in enumerate(lines) if l.startswith("/* ---------------- LOGÍSTICA: TROCAS E DEVOLUÇÕES"))
        lines.insert(dpos, line)
    open(INDEX, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print(f"TROQUE gravado: {len(out)} solicitações, {sum(len(r[-1]) for r in out)} itens, {len(line)//1024} KB",
          file=sys.stderr)


if __name__ == "__main__":
    main()
