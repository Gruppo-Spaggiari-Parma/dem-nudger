# -*- coding: utf-8 -*-
"""Guardiano delle esclusioni obbligatorie su TUTTE le e-mail marketing (Andrea, 21/10/2026, dopo l'audit della pianificazione).

Regola: ogni invio esclude sempre
  5979  opposizione art. 21 (obbligo di legge)
  6460  consenso spaggiari.eu = No (Andrea 19/10/2026: esclusa da ogni mittente, negozio compreso)
Vale anche per le mail preparate a mano dal team (webinar, eventi, avvisi). Le mail del marchio Scuola.net restano fuori.

A ogni giro del workflow dem-nudger:
  1. mail PROGRAMMATE che partono fra piu' di 30 minuti e non hanno le due esclusioni -> tolta la programmazione, aggiunte le
     esclusioni (il resto dei destinatari resta com'e'), riletta data e stato, riprogrammata alla stessa ora. Se un controllo non
     torna la mail resta in bozza e Andrea riceve un compito;
  2. mail gia' PARTITE nelle ultime 24 ore senza la 5979 -> un compito ad Andrea (una volta per mail), perche' non si correggono.

  python guardia_liste.py --prova      dice cosa farebbe, senza toccare niente
"""
import datetime as D
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("HUBSPOT_PAT") or os.environ.get("HUBSPOT_TOKEN") or open(os.path.expanduser("~/.hubspot_pat.txt"), encoding="utf-8-sig").read().strip()
PROVA = "--prova" in sys.argv
OBBLIGATORIE = ["5979", "6460"]
BU_SCUOLANET = 18413835
MARGINE_MIN = 30
ANDREA = "pizzola@spaggiari.eu"


def api(path, body=None, method=None):
    for k in range(8):
        try:
            r = urllib.request.Request("https://api.hubapi.com" + path, data=json.dumps(body).encode() if body is not None else None,
                                       method=method or ("POST" if body is not None else "GET"),
                                       headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
            x = urllib.request.urlopen(r, timeout=120).read()
            return json.loads(x) if x else {}
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 + 3 * k)
                continue
            raise
        except (TimeoutError, socket.timeout, urllib.error.URLError):
            time.sleep(3 + 3 * k)
    raise RuntimeError("HubSpot non risponde")


def quando(iso):
    return D.datetime.fromisoformat(iso.replace("Z", "+00:00"))


def manca(e):
    esc = set(((e.get("to") or {}).get("contactIlsLists") or {}).get("exclude") or [])
    return [x for x in OBBLIGATORIE if x not in esc]


def compito(oggetto, testo):
    if PROVA:
        return
    gia = api("/crm/v3/objects/tasks/search", {"filterGroups": [{"filters": [
        {"propertyName": "hs_task_subject", "operator": "EQ", "value": oggetto}]}], "limit": 1})
    if gia.get("total"):
        return
    o = api("/crm/v3/owners?email=%s" % ANDREA).get("results") or []
    p = {"hs_task_subject": oggetto, "hs_task_body": testo, "hs_task_type": "TODO", "hs_task_priority": "HIGH",
         "hs_task_status": "NOT_STARTED", "hs_timestamp": D.datetime.now(D.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if o:
        p["hubspot_owner_id"] = o[0]["id"]
    api("/crm/v3/objects/tasks", {"properties": p})


def correggi(e):
    """Aggiunge le esclusioni a una mail programmata, con le verifiche introdotte dopo il 9/10 e il 19/10."""
    eid, pd = e["id"], e["publishDate"]
    to = e.get("to") or {}
    il = to.get("contactIlsLists") or {}
    nuovo = dict(to)
    nuovo["contactIlsLists"] = {"include": il.get("include") or [], "exclude": sorted(set(il.get("exclude") or []) | set(OBBLIGATORIE))}
    nuovo.pop("contactLists", None)            # la versione «legacy» la ricalcola HubSpot dalle liste ILS
    api("/marketing/v3/emails/%s/unpublish" % eid, {})
    time.sleep(2)
    m = api("/marketing/v3/emails/%s" % eid)
    if m.get("state") != "DRAFT":
        return "stato %s dopo l'annullamento: non la tocco" % m.get("state")
    api("/marketing/v3/emails/%s" % eid, {"to": nuovo}, "PATCH")
    m = api("/marketing/v3/emails/%s" % eid)
    if (m.get("publishDate") or "")[:16] != pd[:16]:
        api("/marketing/v3/emails/%s" % eid, {"publishDate": pd}, "PATCH")
        m = api("/marketing/v3/emails/%s" % eid)
    if m.get("state") != "DRAFT" or (m.get("publishDate") or "")[:16] != pd[:16] or manca(m):
        compito("Guardiano liste: mail lasciata in bozza (%s)" % eid,
                "La mail «%s» era programmata per %s senza le esclusioni obbligatorie 5979/6460. Dopo la correzione la data o le liste "
                "non tornavano (data letta %s): resta IN BOZZA, va riprogrammata a mano." % (e.get("name"), pd, m.get("publishDate")))
        return "controlli non tornati: lasciata in bozza, compito ad Andrea"
    api("/marketing/v3/emails/%s/publish" % eid, {})
    time.sleep(3)
    m = api("/marketing/v3/emails/%s" % eid)
    if m.get("state") != "SCHEDULED" or (m.get("publishDate") or "")[:16] != pd[:16]:
        compito("Guardiano liste: controllare la mail %s" % eid,
                "Dopo la correzione delle esclusioni la mail «%s» risulta %s con data %s (prevista %s). Controllare subito."
                % (e.get("name"), m.get("state"), m.get("publishDate"), pd))
        return "ripubblicata ma stato/data da controllare"
    return "corretta e riprogrammata alle %s" % pd


def main():
    adesso = D.datetime.now(D.timezone.utc)
    corrette, segnalate, dopo = 0, 0, None
    for _ in range(6):                          # le ultime 600 mail toccate bastano: le programmate sono recenti
        r = api("/marketing/v3/emails?limit=100&sort=-updatedAt" + ("&after=" + dopo if dopo else ""))
        for e in r.get("results", []):
            if e.get("businessUnitId") == BU_SCUOLANET or str(e.get("type", "")).startswith("AUTOMATED") or not e.get("publishDate"):
                continue
            mancano = manca(e)
            if not mancano:
                continue
            pd = quando(e["publishDate"])
            if e.get("state") == "SCHEDULED" and pd > adesso + D.timedelta(minutes=MARGINE_MIN):
                print("programmata %s %s «%s»: mancano %s" % (e["id"], e["publishDate"][:16], (e.get("name") or "")[:60], ",".join(mancano)))
                if not PROVA:
                    print("   ->", correggi(e))
                    corrette += 1
            elif e.get("state") == "PUBLISHED" and "5979" in mancano and pd > adesso - D.timedelta(hours=24):
                print("partita %s %s «%s» senza la 5979" % (e["id"], e["publishDate"][:16], (e.get("name") or "")[:60]))
                compito("Guardiano liste: mail partita senza opposizioni art.21 (%s)" % e["id"],
                        "La mail «%s» e' partita il %s senza escludere la lista 5979 (opposizione art. 21, obbligo di legge). "
                        "Non si puo' correggere: da segnalare a chi l'ha preparata." % (e.get("name"), e["publishDate"][:16]))
                segnalate += 1
        dopo = (r.get("paging") or {}).get("next", {}).get("after")
        if not dopo:
            break
    print(D.datetime.now().isoformat(timespec="seconds"), "guardia_liste: %d corrette, %d segnalate%s" % (corrette, segnalate, " (prova)" if PROVA else ""))


if __name__ == "__main__":
    main()
