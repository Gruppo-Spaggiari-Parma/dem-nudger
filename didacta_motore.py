# -*- coding: utf-8 -*-
"""Motore della campagna Didacta Lanciano (Andrea, 9-10/10/2026): tiene aggiornate le 8 email PROGRAMMATE.

Una email programmata non si puo' modificare. Le card col programma degli incontri (T3-T8) pero' cambiano se si aggiungono o
si spostano eventi. Questo script gira a ogni giro del workflow dem-nudger:

  per ogni email della campagna (didacta_email_ids.json) ancora PROGRAMMATA, il cui invio e' fra 3 e 40 ore:
    1. ricostruisce il contenuto dagli eventi pubblicati (didacta_campagna.py);
    2. se e' uguale a quello programmato, non fa niente;
    3. altrimenti: annulla la programmazione -> aggiorna -> controlla che sia ancora BOZZA e che la data d'invio sia
       rimasta quella giusta -> ripubblica -> controlla che sia di nuovo PROGRAMMATA alla data giusta.
       Se un controllo non torna, NON pubblica e apre un compito per Andrea su HubSpot.

Le verifiche sono quelle introdotte dopo l'errore del 9/10 (8 mail partite subito): niente si pubblica senza aver letto la
data; niente si tocca a meno di 3 ore dall'invio; un'email che non e' in stato atteso viene lasciata com'e'.

  python didacta_motore.py             giro normale
  python didacta_motore.py --prova     dice cosa farebbe, senza toccare niente
"""
import datetime as D
import io
import json
import os
import sys
import time

import didacta_campagna as C

PROVA = "--prova" in sys.argv
MIN_ORE, MAX_ORE = 3, 40            # finestra: si rigenera solo se l'invio e' fra 3 e 40 ore
MODULO = "module_17787858993112"


def allerta(testo):
    """Compito su HubSpot per Andrea (e riga in log): un controllo non e' tornato, la mail e' rimasta com'e'."""
    print("ALLERTA DIDACTA:", testo)
    if PROVA:
        return
    try:
        o = C.api("GET", "/crm/v3/owners?email=pizzola@spaggiari.eu").get("results") or []
        t = {"hs_task_subject": "Didacta Lanciano: controllo email campagna non riuscito",
             "hs_task_body": testo, "hs_task_type": "TODO", "hs_task_priority": "HIGH", "hs_task_status": "NOT_STARTED",
             "hs_timestamp": D.datetime.now(D.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        if o:
            t["hubspot_owner_id"] = o[0]["id"]
        C.api("POST", "/crm/v3/objects/tasks", {"properties": t})
    except Exception as e:
        print("  compito non creato:", type(e).__name__, str(e)[:100])


def rigenera(eid, t, prog, adesso, destinatari=None):
    """Aggiorna una email programmata. Restituisce una stringa col risultato."""
    m = C.api("GET", "/marketing/v3/emails/%s" % eid)
    if m["state"] != "SCHEDULED":
        return "stato %s: non la tocco" % m["state"]
    atteso = D.datetime(*t[1], 9, 0, tzinfo=C.ROMA).astimezone(D.timezone.utc)
    pd = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
    if pd != atteso:
        allerta("%s: la data programmata (%s) non e' quella prevista (%s). Non la modifico." % (t[0], pd.isoformat(), atteso.isoformat()))
        return "data diversa dal previsto: non la tocco"
    ore = (pd - adesso).total_seconds() / 3600
    if not (MIN_ORE < ore <= MAX_ORE):
        return "invio fra %.1f ore: fuori finestra" % ore
    corpo, _ = C.corpo_email(t, prog)
    if destinatari:                    # solo per le prove: destinatari diversi da quelli della campagna
        corpo["to"] = destinatari
    nuovo = corpo["content"]["widgets"][MODULO]["body"]["html"]
    vecchio = m["content"]["widgets"][MODULO]["body"]["html"]
    if nuovo == vecchio and corpo["subject"] == m["subject"]:
        return "gia' aggiornata"
    if PROVA:
        return "da rigenerare (prova: non lo faccio)"
    # 1) annulla la programmazione (consentito solo se l'invio e' lontano)
    C.api("POST", "/marketing/v3/emails/%s/unpublish" % eid, {})
    time.sleep(2)
    m = C.api("GET", "/marketing/v3/emails/%s" % eid)
    if m["state"] != "DRAFT":
        allerta("%s: dopo l'annullamento lo stato e' %s e non BOZZA. Mi fermo: controllare a mano." % (t[0], m["state"]))
        return "stato inatteso dopo unpublish"
    # 2) aggiorna contenuto, oggetto e destinatari
    C.api("PATCH", "/marketing/v3/emails/%s" % eid, {"subject": corpo["subject"], "content": corpo["content"], "to": corpo["to"]})
    m = C.api("GET", "/marketing/v3/emails/%s" % eid)
    pd2 = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
    if m["state"] != "DRAFT" or pd2 != atteso:
        # la data e' cambiata: la rimetto e la rileggo; se ancora diversa NON pubblico (sarebbe un invio immediato)
        C.api("PATCH", "/marketing/v3/emails/%s" % eid, {"publishDate": atteso.isoformat().replace("+00:00", "Z")})
        m = C.api("GET", "/marketing/v3/emails/%s" % eid)
        pd2 = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
        if m["state"] != "DRAFT" or pd2 != atteso:
            allerta("%s: dopo l'aggiornamento la data d'invio e' %s (prevista %s) e lo stato %s. NON ripubblicata: resta in bozza, va "
                    "programmata a mano." % (t[0], pd2.isoformat(), atteso.isoformat(), m["state"]))
            return "data non tornata: lasciata in bozza"
    # 3) ripubblica e controlla
    C.api("POST", "/marketing/v3/emails/%s/publish" % eid, {})
    time.sleep(3)
    m = C.api("GET", "/marketing/v3/emails/%s" % eid)
    pd3 = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
    if m["state"] != "SCHEDULED" or pd3 != atteso:
        allerta("%s: dopo la ripubblicazione lo stato e' %s e la data %s (prevista %s). Controllare subito su HubSpot." %
                (t[0], m["state"], pd3.isoformat(), atteso.isoformat()))
        return "ripubblicata ma stato/data non conformi"
    return "rigenerata e riprogrammata (%s, %s)" % (m["state"], pd3.strftime("%d/%m %H:%M UTC"))


def main():
    ids = json.load(io.open(os.path.join(C.QUI, "didacta_email_ids.json"), encoding="utf-8"))
    adesso = D.datetime.now(D.timezone.utc)
    prog = None
    for t in C.TOCCHI:
        eid = ids.get(t[0])
        if not eid:
            continue
        d = D.datetime(*t[1], 9, 0, tzinfo=C.ROMA).astimezone(D.timezone.utc)
        if not (MIN_ORE < (d - adesso).total_seconds() / 3600 <= MAX_ORE):
            continue                   # niente chiamate se l'invio e' lontano o troppo vicino
        if prog is None:
            prog = C.programma()
        try:
            print("didacta %s (%s): %s" % (t[0], eid, rigenera(eid, t, prog, adesso)))
        except Exception as e:
            allerta("%s: errore imprevisto (%s %s). Non modificata." % (t[0], type(e).__name__, str(e)[:160]))
    print(D.datetime.now().isoformat(timespec="seconds"), "didacta_motore: fatto")


if __name__ == "__main__":
    main()
