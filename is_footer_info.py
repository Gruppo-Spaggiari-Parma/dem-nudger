# -*- coding: utf-8 -*-
"""ItaliaScuola (Andrea, 15/10/2026): dal pie' di pagina delle DEM si toglie «o richiedere maggiori informazioni contattandoci
tramite la casella mail info@italiascuola.it» (la casella e' stata soppressa), senza mettere niente al suo posto.

Tocca: i tre modelli [DEM v5 IS] (T14, T3, T1), la mail di annullamento IS e ogni email [DEM v6] non ancora partita che contiene la frase.
Le email gia' PUBBLICATE (inviate) restano come sono. Le PROGRAMMATE si aggiornano con la procedura sicura del 9/10:
annulla -> controlla BOZZA -> aggiorna -> controlla che la data sia rimasta -> ripubblica -> controlla PROGRAMMATA alla stessa data.

  python is_footer_info.py --prova     elenca cosa farebbe
  python is_footer_info.py             applica
"""
import datetime as D
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("HUBSPOT_PAT") or open(os.path.expanduser("~/.hubspot_pat.txt"), encoding="utf-8-sig").read().strip()
PROVA = "--prova" in sys.argv
MODELLI = ["465634433262", "465634433265", "465634433268", "478763222253"]
FRASE = re.compile(r"\s*o richiedere maggiori informazioni contattandoci tramite la casella mail(?:&nbsp;|\s)*"
                   r"(?:<a\b[^>]*>)?\s*info@italiascuola\.it\s*(?:</a>)?", re.I)
QUI = os.path.dirname(os.path.abspath(__file__))


def api(path, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    for k in range(5):
        r = urllib.request.Request("https://api.hubapi.com" + path, data=data, method=method,
                                   headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(r, timeout=90) as x:
                b = x.read()
                return json.loads(b) if b else {}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(3 * (k + 1)); continue
            raise RuntimeError("%s %s -> %d %s" % (method, path, e.code, e.read().decode()[:300]))


def togli(o):
    """Applica la sostituzione a ogni stringa; restituisce (nuovo, numero di sostituzioni)."""
    if isinstance(o, str):
        n = len(FRASE.findall(o))
        return (FRASE.sub(".", o), n) if n else (o, 0)
    if isinstance(o, list):
        r = [togli(x) for x in o]
        return [a for a, _ in r], sum(n for _, n in r)
    if isinstance(o, dict):
        r = {k: togli(v) for k, v in o.items()}
        return {k: a for k, (a, _) in r.items()}, sum(n for _, n in r.values())
    return o, 0


def email_da_toccare():
    ids = list(MODELLI)
    dopo = None
    for _ in range(30):
        r = api("/marketing/v3/emails?limit=100&createdAfter=2026-09-25T00:00:00Z" + ("&after=" + dopo if dopo else ""))
        for e in r.get("results", []):
            if e["name"].startswith("[DEM v6]") and e["id"] not in ids:
                ids.append(e["id"])
        dopo = (r.get("paging") or {}).get("next", {}).get("after")
        if not dopo:
            break
    return ids


def automatica(e, content):
    """Modello AUTOMATED (usato dai flussi v5): bozza -> pubblicazione."""
    json.dump(e, open(os.path.join(QUI, "is_footer_backup_%s.json" % e["id"]), "w", encoding="utf-8"), ensure_ascii=False)
    api("/marketing/v3/emails/%s/draft" % e["id"], {"content": content}, "PATCH")
    api("/marketing/v3/emails/%s/publish" % e["id"], {}, "POST")
    time.sleep(2)
    v = api("/marketing/v3/emails/%s" % e["id"])
    return togli(v["content"])[1] == 0 and v["state"] == "AUTOMATED"


def programmata(e, content):
    atteso = D.datetime.fromisoformat(e["publishDate"].replace("Z", "+00:00"))
    ore = (atteso - D.datetime.now(D.timezone.utc)).total_seconds() / 3600
    if ore < 3:
        print("    invio fra %.1f ore: la lascio com'e'" % ore)
        return None
    json.dump(e, open(os.path.join(QUI, "is_footer_backup_%s.json" % e["id"]), "w", encoding="utf-8"), ensure_ascii=False)
    api("/marketing/v3/emails/%s/unpublish" % e["id"], {}, "POST")
    time.sleep(2)
    m = api("/marketing/v3/emails/%s" % e["id"])
    if m["state"] != "DRAFT":
        print("    ALLERTA: dopo l'annullamento lo stato e' %s: mi fermo" % m["state"]); return False
    api("/marketing/v3/emails/%s" % e["id"], {"content": content}, "PATCH")
    m = api("/marketing/v3/emails/%s" % e["id"])
    pd = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
    if m["state"] != "DRAFT" or pd != atteso:
        api("/marketing/v3/emails/%s" % e["id"], {"publishDate": atteso.isoformat().replace("+00:00", "Z")}, "PATCH")
        m = api("/marketing/v3/emails/%s" % e["id"])
        pd = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
        if m["state"] != "DRAFT" or pd != atteso:
            print("    ALLERTA: data %s (prevista %s): NON ripubblicata, resta in bozza" % (pd, atteso)); return False
    api("/marketing/v3/emails/%s/publish" % e["id"], {}, "POST")
    time.sleep(3)
    m = api("/marketing/v3/emails/%s" % e["id"])
    pd = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
    ok = m["state"] == "SCHEDULED" and pd == atteso and togli(m["content"])[1] == 0
    if not ok:
        print("    ALLERTA: dopo la ripubblicazione stato %s data %s" % (m["state"], pd))
    return ok


def main():
    tot = {"sostituite": 0, "ok": 0, "problemi": 0, "inviate_lasciate": 0, "senza_frase": 0}
    for i in email_da_toccare():
        e = api("/marketing/v3/emails/%s" % i)
        content, n = togli(e["content"])
        if not n:
            tot["senza_frase"] += 1
            continue
        st = e["state"]
        print("%s %s [%s]: frase presente %d volte" % (i, e["name"][:70], st, n))
        if st in ("PUBLISHED",):
            tot["inviate_lasciate"] += 1; print("    gia' partita: la lascio"); continue
        if PROVA:
            continue
        if st == "AUTOMATED":
            ok = automatica(e, content)
        elif st == "SCHEDULED":
            ok = programmata(e, content)
            if ok is None:
                tot["inviate_lasciate"] += 1; continue
        elif st == "DRAFT":
            api("/marketing/v3/emails/%s" % i, {"content": content}, "PATCH"); ok = True
        else:
            print("    stato %s: salto" % st); continue
        tot["ok" if ok else "problemi"] += 1
        print("    ->", "fatto e verificato" if ok else "NON verificato")
    print(tot)


if __name__ == "__main__":
    main()
