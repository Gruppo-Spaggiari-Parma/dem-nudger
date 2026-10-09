# -*- coding: utf-8 -*-
"""Lista degli iscritti agli eventi Didacta Lanciano (DID-LAN*): esclusi dagli invii della campagna (Andrea, 9/10/2026).

La campagna Didacta manda un'email a giorni alterni a tutti; chi si e' gia' iscritto a un evento non deve piu' ricevere
«iscriviti». Questo script tiene allineata una lista statica (6237): dentro ci sono i contatti con una iscrizione non annullata
a un evento DID-LAN; ne esce chi ha annullato. Le email della campagna escludono quella lista.
Gira nel workflow dem-nudger (ogni giro).
"""
import json
import os
import time
import urllib.error
import urllib.request

TOKEN = os.environ.get("HUBSPOT_PAT") or open(os.path.expanduser("~/.hubspot_pat.txt")).read().strip()
LISTA = "6237"
EV, REG = "2-143900361", "2-143900355"


def api(path, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    for k in range(5):
        req = urllib.request.Request("https://api.hubapi.com" + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                return json.loads(b) if b else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 * (k + 1)); continue
            raise RuntimeError("%s %s -> %s %s" % (method, path, e.code, e.read().decode()[:300]))
    raise RuntimeError("troppi tentativi su " + path)


def cerca(oggetto, filtri, props, tetto=100):
    out, dopo = [], None
    for _ in range(tetto):
        r = api("/crm/v3/objects/%s/search" % oggetto, {"filterGroups": [{"filters": filtri}], "properties": props, "limit": 100,
                                                          **({"after": dopo} if dopo else {})}, "POST")
        out += r.get("results", [])
        dopo = (r.get("paging") or {}).get("next", {}).get("after")
        if not dopo:
            break
    return out


def main():
    eventi = [e["id"] for e in cerca(EV, [{"propertyName": "external_id", "operator": "CONTAINS_TOKEN", "value": "DID-LAN*"}], ["external_id"])]
    emails = set()
    for ev in eventi:
        for x in cerca(REG, [{"propertyName": "event_id", "operator": "EQ", "value": ev}, {"propertyName": "status", "operator": "NEQ", "value": "Canceled"}], ["email"]):
            e = (x["properties"].get("email") or "").strip().lower()
            if e:
                emails.add(e)
    ids = set()
    lista = sorted(emails)
    for i in range(0, len(lista), 100):
        r = api("/crm/v3/objects/contacts/batch/read", {"idProperty": "email", "properties": ["email"], "inputs": [{"id": e} for e in lista[i:i + 100]]}, "POST")
        ids |= {x["id"] for x in r.get("results", [])}
    attuali, dopo = set(), None
    while True:
        r = api("/crm/v3/lists/%s/memberships?limit=250%s" % (LISTA, "&after=" + dopo if dopo else ""))
        attuali |= {str(x["recordId"]) for x in r.get("results", [])}
        dopo = (r.get("paging") or {}).get("next", {}).get("after")
        if not dopo:
            break
    da_aggiungere, da_togliere = sorted(ids - attuali), sorted(attuali - ids)
    for i in range(0, len(da_aggiungere), 100):
        api("/crm/v3/lists/%s/memberships/add" % LISTA, da_aggiungere[i:i + 100], "PUT")
    for i in range(0, len(da_togliere), 100):
        api("/crm/v3/lists/%s/memberships/remove" % LISTA, da_togliere[i:i + 100], "PUT")
    print("didacta_esclusi: eventi %d, iscritti %d (contatti trovati %d) | aggiunti %d, tolti %d" %
          (len(eventi), len(emails), len(ids), len(da_aggiungere), len(da_togliere)))


if __name__ == "__main__":
    main()
