#!/usr/bin/env python3
"""Etapa 2 do relatório de coleção: cruza vendas, estoque, acessos e revisão visual e gera o HTML.

Uso:
  python3 montar.py --dir <pasta_de_trabalho> --tag verao-27 --colecao "Verão 27" \
      --posthog-inicio 2026-10-28 --views views.csv [--nota "texto extra para Fontes e critérios"]

views.csv: uma linha por produto "id,sessoes" (resultado do posthog.sql).
--posthog-inicio: início da janela de conversão (data a partir da qual o PostHog tem dados confiáveis
                  para essas PDPs). Pedidos para a conversão contam a partir dessa data.

Saídas em <dir>: relatorio.html (página final) e grupos.txt (listas por grupo para a mensagem de WhatsApp).
"""
import argparse, json, os, io, base64, collections, statistics as st
from datetime import date, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
CORE = ("35", "36", "37", "38")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True); ap.add_argument("--tag", required=True)
    ap.add_argument("--colecao", required=True); ap.add_argument("--posthog-inicio", required=True)
    ap.add_argument("--views", required=True); ap.add_argument("--nota", action="append", default=[])
    ap.add_argument("--data-fim", default=date.today().isoformat())
    a = ap.parse_args()
    os.chdir(a.dir)
    P = {p["id"]: p for p in json.load(open("prods.json"))}
    V = {}
    for l in open(a.views).read().split():
        k, v = l.split(","); V[int(k)] = int(v)
    O = [o for o in json.load(open("orders_all.json")) if o["status"] != "canceled"]
    IM = {pid: json.load(open(f"imgs/{pid}.json")) for pid in P}
    rev = json.load(open("revisao.json"))
    NO_MODEL = set(map(int, rev["sem_modelo"])); CHART = set(map(int, rev["ultima_imagem_e_tabela_de_medidas"]))
    man = json.load(open("powerclip.json"))
    VIDEO = {int(c["product_platform_id"]) for c in man.get("clips", []) if c.get("publication_status") == "active" and str(c.get("product_platform_id", "")).isdigit()}

    s = collections.defaultdict(lambda: {"q": 0, "rev": 0.0, "ord": set(), "first": None, "ord28": set()})
    for o in O:
        r_ = o["received_at"][:10]
        for it in o.get("items", []):
            pid = it["product_id"]
            if pid in P:
                d = s[pid]; d["q"] += it["quantity"]; d["rev"] += it["price"] * it["quantity"]; d["ord"].add(o["code"])
                d["first"] = min(d["first"] or r_, r_)
                if r_ >= a.posthog_inicio: d["ord28"].add(o["code"])

    recente = (date.fromisoformat(a.data_fim) - timedelta(days=10)).isoformat()
    rows = []
    for pid, p in P.items():
        vs = [v for vv in p["variants"] for v in vv.values()]
        sizes = [((v["attribute2"] or v["sku"].split("-")[-1]), v["stock"]) for v in vs]
        single = len(vs) == 1
        units = sum(max(x, 0) for _, x in sizes); avail = sum(1 for _, x in sizes if x > 0)
        d = s[pid]; sess = V.get(pid, 0)
        order = sorted({sz for sz, _ in sizes}, key=lambda z: (not z.isdigit(), int(z) if z.isdigit() else 0, z))
        rows.append(dict(
            id=pid, ref=p["reference"], nome=p["name"].strip(), cat="Acessório" if single else "Calçado",
            preco=p["price"], preco_atual=p["sale_price"],
            cadastro=min((i["updated_at"] for i in IM[pid]), default=a.data_fim)[:10], primeira_venda=d["first"],
            pecas=d["q"], receita=round(d["rev"], 2), pedidos=len(d["ord"]), pedidos28=len(d["ord28"]), sessoes=sess,
            conv=(len(d["ord28"]) / sess * 100 if sess else None), estoque=units, tamanhos_total=len(sizes), tamanhos_ok=avail,
            tamanhos_zerados=[z for z, x in sizes if x <= 0], core_zerados=[z for z, x in sizes if z in CORE and x <= 0],
            grade_pct=avail / len(sizes) * 100 if sizes else 0, single=single,
            fotos=len(IM[pid]) - (1 if pid in CHART else 0), modelo=pid not in NO_MODEL, video=pid in VIDEO,
            url=p["url"], _sizes=order))

    base = [r for r in rows if not (r["cadastro"] >= recente or r["sessoes"] < 20)]
    ref = sum(r["pedidos28"] for r in base) / max(1, sum(r["sessoes"] for r in base)) * 100
    for r in rows:
        if r["cadastro"] >= recente or r["sessoes"] < 20: r["grupo"] = "novo"; continue
        if r["single"]:
            broken = r["estoque"] <= 3; warn = False; healthy = r["estoque"] >= 6
        else:
            broken = len(r["core_zerados"]) >= 2 or r["grade_pct"] < 60 or r["estoque"] < 10
            warn = len(r["core_zerados"]) == 1
            healthy = not broken and not warn and r["grade_pct"] >= 80 and r["estoque"] >= 12
        c = r["conv"] or 0
        keep = (not broken) and (not warn) and (r["single"] or (not r["core_zerados"] and r["grade_pct"] >= 70 and r["estoque"] >= 12)) and c >= ref and r["pedidos28"] >= 4
        if broken: g = "pausar"
        elif warn: g = "atencao"
        elif healthy and r["pedidos28"] >= 3 and c >= ref * 1.3 and r["sessoes"] <= 500: g = "escalar"
        elif keep: g = "manter"
        elif healthy and r["sessoes"] >= 90 and c < ref * 0.7: g = "pdp_ok" if (r["fotos"] > 1 and r["modelo"] and r["video"]) else "pdp"
        else: g = "monitorar"
        r["grupo"] = g

    from PIL import Image
    for r in rows:
        f = f"thumbs/{r['id']}_00.jpg"
        if os.path.exists(f):
            b = io.BytesIO(); Image.open(f).convert("RGB").resize((96, 96)).save(b, "JPEG", quality=72)
            r["thumb"] = "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()
        else: r["thumb"] = ""
    meta = dict(colecao=a.colecao, tag=a.tag, data_fim=a.data_fim, posthog_inicio=a.posthog_inicio,
                pedidos_inicio=min(o["received_at"][:10] for o in O), n_pedidos=len(json.load(open("orders_all.json"))),
                n_imagens=sum(len(v) for v in IM.values()), notas=a.nota)
    data = {"rows": rows, "ref": ref, "meta": meta}
    t = open(os.path.join(AQUI, "template.html")).read()
    t = t.replace("__TITULO__", a.colecao).replace("__DATA__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    open("relatorio.html", "w").write(t)

    nomes = {"pausar": "SEGURAR", "atencao": "SEM SER DESTAQUE (falta 1 tamanho central)", "escalar": "DAR MAIS DESTAQUE",
             "manter": "MANTER O RITMO", "pdp": "PÁGINA INCOMPLETA", "pdp_ok": "PÁGINA COMPLETA, MAS NÃO VENDE",
             "monitorar": "MONITORAR (não entra na mensagem)", "novo": "RECENTE / DADOS INSUFICIENTES"}
    out = [f"{a.colecao}: {sum(r['pecas'] for r in rows)} peças, R$ {sum(r['receita'] for r in rows):,.0f}, conversão média {ref:.2f}%".replace(",", ".")]
    for g, lab in nomes.items():
        L = sorted([r for r in rows if r["grupo"] == g], key=lambda r: -r["sessoes"])
        out.append(f"\n== {lab} ({len(L)})")
        for r in L:
            falta = [x for x, ok in (("mais fotos", r["fotos"] > 1), ("foto com modelo", r["modelo"]), ("vídeo", r["video"])) if not ok]
            out.append(f"- {r['nome']} | vendas {r['pecas']} | sessões {r['sessoes']} | conv {r['conv'] or 0:.2f}% | estoque {r['estoque']} | zerados {','.join(r['tamanhos_zerados']) or '-'}"
                       + (f" | falta: {', '.join(falta)}" if g in ("pdp", "pdp_ok") else ""))
    open("grupos.txt", "w").write("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
