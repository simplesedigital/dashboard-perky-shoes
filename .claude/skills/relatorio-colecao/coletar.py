#!/usr/bin/env python3
"""Etapa 1 do relatório de coleção: coleta dados da VNDA e do PowerClip e monta folhas de contato.

Uso:
  python3 coletar.py --tag verao-27 --out <pasta_de_trabalho>

Gera em <out>:
  prods.json           produtos da tag (com variantes/estoque)
  imgs/<id>.json       imagens de cada produto
  orders_all.json      pedidos desde a data da imagem mais antiga da coleção
  powerclip.json       manifesto do PowerClip (vídeos das PDPs)
  thumbs/<id>_NN.jpg   miniaturas de todas as imagens
  sheets/sNN.jpg       folhas de contato (8 produtos por folha) para revisão visual
  posthog.sql          SQL pronto para rodar no PostHog (execute-sql)
  revisao.json         esqueleto da revisão visual para preencher

As chamadas a api.vnda.com.br são autenticadas pelo proxy do ambiente (sem chave no código).
"""
import argparse, json, os, glob, io, subprocess, concurrent.futures as cf, urllib.request, urllib.parse

VNDA = "https://api.vnda.com.br/api/v2"
STORE_DGUID = "D37778AC-B517-CFE7-CC3C-004D292168B3"  # Performa/PowerClip da Perky


UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
_op = urllib.request.build_opener(); _op.addheaders = [("User-Agent", UA)]; urllib.request.install_opener(_op)


def get(url, headers=False):
    import time, urllib.error
    for tent in range(6):
        req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                body = json.loads(r.read().decode())
                return (body, dict(r.headers)) if headers else body
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 504) and tent < 5:
                time.sleep(int(e.headers.get("Retry-After") or 0) or 2 ** (tent + 1)); continue
            raise


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True); os.chdir(a.out)
    for d in ("imgs", "thumbs", "sheets", "orders"): os.makedirs(d, exist_ok=True)

    # produtos
    prods, page = [], 1
    while True:
        body, h = get(f"{VNDA}/products?tag={urllib.parse.quote(a.tag)}&per_page=50&page={page}", True)
        prods += body
        pag = json.loads(h.get("X-Pagination") or h.get("x-pagination") or "{}")
        if not pag.get("next_page"): break
        page += 1
    json.dump(prods, open("prods.json", "w"), ensure_ascii=False)
    print("produtos:", len(prods))

    # imagens
    def imgs(p):
        im = get(f"{VNDA}/products/{p['id']}/images"); json.dump(im, open(f"imgs/{p['id']}.json", "w")); return im
    with cf.ThreadPoolExecutor(4) as ex: IM = dict(zip([p["id"] for p in prods], ex.map(imgs, prods)))
    first = min(i["updated_at"][:10] for v in IM.values() for i in v)
    print("imagem mais antiga (proxy de cadastro):", first)

    # pedidos desde a primeira imagem
    from datetime import date
    hoje = date.today().isoformat()
    _, h = get(f"{VNDA}/orders?start={first}&finish={hoje}&per_page=100", True)
    pages = json.loads(h.get("X-Pagination") or h.get("x-pagination"))["total_pages"]
    def op(n): return get(f"{VNDA}/orders?start={first}&finish={hoje}&per_page=100&page={n}")
    with cf.ThreadPoolExecutor(3) as ex: O = [o for chunk in ex.map(op, range(1, pages + 1)) for o in chunk]
    O = list({o["code"]: o for o in O}.values())
    json.dump(O, open("orders_all.json", "w"))
    print("pedidos:", len(O), "de", first, "a", hoje)

    # PowerClip (vídeos)
    route = urllib.parse.quote("/produto/" + prods[0]["slug"] + f"-{prods[0]['id']}", safe="")
    man = get(f"https://powerclip-media.performa.ai/v1/powerclip/manifest?store_dguid={STORE_DGUID}&domain=www.perkyshoes.com&route={route}")
    json.dump(man, open("powerclip.json", "w"))
    vids = {c["product_platform_id"] for c in man.get("clips", []) if c.get("publication_status") == "active"}
    print("produtos da tag com vídeo:", len([p for p in prods if str(p["id"]) in vids]))

    # miniaturas + folhas de contato
    jobs = []
    for pid, v in IM.items():
        for i, im in enumerate(v):
            jobs.append(("https:" + im["url"].replace("cdn.vnda.com.br/perkyshoes3", "cdn.vnda.com.br/x200/perkyshoes3"), f"thumbs/{pid}_{i:02d}.jpg"))
    def dl(j):
        if not os.path.exists(j[1]): urllib.request.urlretrieve(j[0], j[1])
    with cf.ThreadPoolExecutor(12) as ex: list(ex.map(dl, jobs))
    from PIL import Image, ImageDraw
    g = {}
    for f in sorted(glob.glob("thumbs/*.jpg")): g.setdefault(f.split("/")[1].split("_")[0], []).append(f)
    pids = sorted(g); T = 150
    for si in range(0, len(pids), 8):
        chunk = pids[si:si + 8]; sh = Image.new("RGB", (60 + T * 11, T * len(chunk)), "white"); d = ImageDraw.Draw(sh)
        for r, pid in enumerate(chunk):
            d.text((5, r * T + 60), pid, fill="black")
            for c, f in enumerate(g[pid][:11]): sh.paste(Image.open(f).convert("RGB").resize((T - 4, T - 4)), (60 + c * T, r * T + 2))
        sh.save(f"sheets/s{si // 8}.jpg", quality=85)
    print("folhas de contato:", len(glob.glob("sheets/*.jpg")), "imagens:", len(jobs))

    ids = ",".join(str(p["id"]) for p in prods)
    open("posthog.sql", "w").write(
        "SELECT toInt(extract(properties.$pathname, '-([0-9]+)/?$')) AS pid, uniq(\"$session_id\") AS sessions, min(timestamp) AS first_seen "
        "FROM events WHERE event = '$pageview' AND properties.$pathname LIKE '/produto/%' "
        f"AND timestamp >= '{first}' AND pid IN ({ids}) GROUP BY pid ORDER BY sessions DESC LIMIT 500")
    if not os.path.exists("revisao.json"):
        json.dump({"sem_modelo": [], "ultima_imagem_e_tabela_de_medidas": [], "_como_preencher":
                   "Veja sheets/*.jpg. sem_modelo = ids sem NENHUMA foto com pessoa usando o produto (pés/corpo contam). "
                   "ultima_imagem_e_tabela_de_medidas = ids cuja última imagem é o guia de medidas verde (não conta como foto)."},
                  open("revisao.json", "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
