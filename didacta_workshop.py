# -*- coding: utf-8 -*-
"""Didacta Lanciano: tre mail dedicate ai workshop principali (Andrea, 14/10/2026).

«ClasseViva Docenti, App Dirigente, Orientamento: sono workshop importanti di Didacta, a cui sarebbe bene partecipassero
anche dallo streaming. Possiamo creare delle comunicazioni dedicate, da far uscire da domani.»

Stessa grafica e stessi destinatari della campagna (didacta_campagna.py); per ogni mail si escludono solo gli iscritti a
QUEL workshop (gli iscritti ad altri incontri la ricevono).

  python didacta_workshop.py anteprima     scrive audit/anteprima_didacta/W1..W3.html
  python didacta_workshop.py crea          crea le bozze (DRAFT, nessuna data)
  python didacta_workshop.py aggiorna      riscrive le bozze e rinfresca le liste degli iscritti
  python didacta_workshop.py programma     programma le bozze alle date di QUANDO (solo dopo l'ok di Andrea)
"""
import datetime as D
import io
import json
import os
import sys
import time

import didacta_campagna as C

IDS = os.path.join(C.QUI, "didacta_workshop_ids.json")
OGGETTO_EVENTO = "2-143900361"

# (chiave, invio, evento, ext, oggetto, anteprima, etichetta, titolo, sottotitolo)
W = [
    ("W1", (2026, 10, 15, 15, 0), "455460125935", "DID-LAN06",
     "ClasseViva Docenti, la nuova App: in diretta da Didacta mercoledì 21 ottobre",
     "Appello, voti e registro a portata di mano. Alle 13:10, a Lanciano o in live streaming.",
     "Didacta Lanciano &middot; Workshop", "ClasseViva Docenti: la nuova App per il lavoro in classe",
     "Mercoled&igrave; 21 ottobre &middot; 13:10&ndash;14:10 &middot; a Lanciano o in live streaming"),
    ("W2", (2026, 10, 16, 9, 0), "455243489497", "DID-LAN17",
     "App Dirigente, la scuola in tasca: in diretta da Didacta giovedì 22 ottobre",
     "Didattica, segreteria e gestione dell'istituto in un unico cruscotto. Alle 13:10, a Lanciano o in live streaming.",
     "Didacta Lanciano &middot; Workshop", "App Dirigente: la scuola in tasca",
     "Gioved&igrave; 22 ottobre &middot; 13:10&ndash;14:10 &middot; a Lanciano o in live streaming"),
    ("W3", (2026, 10, 20, 9, 0), "454933178575", "DID-LAN24",
     "Orientamento, percorsi digitali per gli studenti: in diretta da Didacta venerdì 23 ottobre",
     "Accompagnare la scelta degli studenti lungo tutto l'anno. Alle 10:45, a Lanciano o in live streaming.",
     "Didacta Lanciano &middot; Workshop", "Orientamento: percorsi digitali verso il futuro degli studenti",
     "Venerd&igrave; 23 ottobre &middot; 10:45&ndash;11:45 &middot; a Lanciano o in live streaming"),
]


def link(evento, chiave):
    return ("https://www.spaggiari.eu/eventi/registrazione/nosession/%s?hsLang=it&utm_source=hubspot&utm_medium=email"
            "&utm_campaign=didacta-lanciano-2026&utm_content=%s" % (evento, chiave.lower()))


def cta_evento(testo, evento, chiave):
    """Il pulsante della campagna, ma porta dritto all'iscrizione del workshop."""
    h = C.cta(testo, chiave.lower())
    return h.replace(C.PAGINA + C.UTM % chiave.lower(), link(evento, chiave).replace("&", "&amp;"))


def streaming():
    return C.riquadro("Come partecipare", [
        "<strong>A Lanciano</strong> &middot; Polo Fieristico d&rsquo;Abruzzo, Loc. Iconicella snc, %s &middot; %s." % (C.PADIGLIONE, C.STAND),
        "<strong>In live streaming</strong> &middot; dal computer, ovunque vi troviate: il link per collegarsi arriva con l&rsquo;iscrizione.",
        "Con l&rsquo;iscrizione, chi viene in fiera riceve dalla fiera di Didacta il biglietto di 3 giorni in omaggio."],
        colore="#E9F3F2", barra=C.PETROLIO)


def corpo(chiave, evento):
    p, riq = C.p, C.riquadro
    if chiave == "W1":
        return (p("La nuova App ClasseViva Docenti porta sullo smartphone e sul tablet il lavoro di ogni giorno in classe: "
                  "appello, voti e registro a portata di mano, in pochi tocchi.")
                + riq("Nell&rsquo;incontro, l&rsquo;App in uso", [
                    "<strong>Firma e appello</strong> &middot; direttamente dall&rsquo;aula, all&rsquo;inizio della lezione.",
                    "<strong>Voti</strong> &middot; registrati al momento, per classe e materia.",
                    "<strong>Argomenti e compiti</strong> &middot; annotati nel registro e visibili a studenti e famiglie.",
                    "<strong>Comunicazioni</strong> &middot; con studenti e famiglie, dalle sezioni del registro."])
                + p("Un&rsquo;ora per vedere l&rsquo;App al lavoro e porre le vostre domande. Si partecipa in fiera oppure in live streaming: "
                    "un modo semplice per coinvolgere anche i colleghi che restano a scuola.")
                + cta_evento("Iscriviti al workshop", evento, chiave) + streaming())
    if chiave == "W2":
        return (p("L&rsquo;App Dirigente riunisce in un unico cruscotto quello che accade nell&rsquo;istituto, aggiornato in tempo reale "
                  "e consultabile dallo smartphone: la scuola in tasca, sempre sotto controllo.")
                + riq("Nell&rsquo;incontro, il cruscotto in uso", [
                    "<strong>Didattica</strong> &middot; l&rsquo;andamento delle classi, aggiornato in tempo reale.",
                    "<strong>Segreteria</strong> &middot; il lavoro degli uffici, in un colpo d&rsquo;occhio.",
                    "<strong>Gestione dell&rsquo;istituto</strong> &middot; le informazioni per decidere, ovunque vi troviate."])
                + p("Un&rsquo;ora per vedere l&rsquo;App al lavoro e porre le vostre domande. Si partecipa in fiera oppure in live streaming, "
                    "anche tra un impegno e l&rsquo;altro.")
                + cta_evento("Iscriviti al workshop", evento, chiave) + streaming())
    if chiave == "W3":
        return (p("L&rsquo;orientamento accompagna gli studenti lungo tutto l&rsquo;anno, fino alla scelta del percorso di studi o di lavoro. "
                  "Il workshop presenta i percorsi digitali che aiutano docenti tutor, referenti e dirigenti delle scuole secondarie a costruirlo e a documentarlo.")
                + riq("Nell&rsquo;incontro", [
                    "<strong>Storie di professioni</strong> &middot; raccontate da chi le fa: studi, percorso, giornata tipo.",
                    "<strong>Percorsi di Formazione Scuola-Lavoro</strong> &middot; gi&agrave; pronti, con contenuti, attivit&agrave; e ore certificate.",
                    "<strong>Universit&agrave; e primo lavoro</strong> &middot; guide aggiornate durante l&rsquo;anno.",
                    "<strong>Attivit&agrave; documentate</strong> &middot; un orientamento tracciabile, da condividere con le famiglie."])
                + p("Un&rsquo;ora di esempi concreti e di risposte alle vostre domande. Si partecipa in fiera oppure in live streaming: "
                    "un modo semplice per coinvolgere tutto il gruppo dell&rsquo;orientamento.")
                + cta_evento("Iscriviti al workshop", evento, chiave) + streaming())


def html(w):
    chiave, _, evento = w[0], w[1], w[2]
    t = (chiave, None, w[4], w[5], w[6], w[7], w[8])          # stessa forma dei TOCCHI della campagna
    salva = C.corpo
    C.corpo = lambda k, prog: corpo(chiave, evento)
    try:
        h = C.html_modulo(t, None)
    finally:
        C.corpo = salva
    return h.replace("A presto a Lanciano,", "A presto, a Lanciano o in diretta,")


def iscritti(evento, nome):
    """Lista statica degli iscritti a QUESTO workshop, rinfrescata a ogni giro."""
    trov = [x for x in C.api("POST", "/crm/v3/lists/search", {"query": nome, "count": 5}).get("lists", []) if x.get("name") == nome]
    lid = str(trov[0]["listId"]) if trov else str(C.api("POST", "/crm/v3/lists", {"name": nome, "objectTypeId": "0-1", "processingType": "MANUAL"})["list"]["listId"])
    emails, dopo = set(), None          # iscrizioni = oggetto registrazione hapily (come didacta_esclusi.py), non associazioni dell'evento
    while True:
        r = C.api("POST", "/crm/v3/objects/2-143900355/search", {"filterGroups": [{"filters": [
            {"propertyName": "event_id", "operator": "EQ", "value": evento}, {"propertyName": "status", "operator": "NEQ", "value": "Canceled"}]}],
            "properties": ["email"], "limit": 100, **({"after": dopo} if dopo else {})})
        emails |= {(x["properties"].get("email") or "").strip().lower() for x in r.get("results", [])} - {""}
        dopo = ((r.get("paging") or {}).get("next") or {}).get("after")
        if not dopo:
            break
    ids, lista = [], sorted(emails)
    for i in range(0, len(lista), 100):
        ids += [x["id"] for x in C.api("POST", "/crm/v3/objects/contacts/batch/read", {"idProperty": "email", "properties": ["email"],
                                                                                      "inputs": [{"id": e} for e in lista[i:i + 100]]}).get("results", [])]
    for i in range(0, len(ids), 250):
        C.api("PUT", "/crm/v3/lists/%s/memberships/add" % lid, ids[i:i + 250])
    return lid, len(ids)


def corpo_email(w):
    m = json.load(io.open(C.MODELLO, encoding="utf-8"))
    c = m["content"]
    c["widgets"]["module_17787858993112"]["body"]["html"] = html(w)
    if "preview_text" in c["widgets"]:
        c["widgets"]["preview_text"] = {**c["widgets"]["preview_text"], "body": {"value": w[5]}, "name": "preview_text", "type": "text"}
    lid, n = iscritti(w[2], "DIDACTA LANCIANO - iscritti %s (%s)" % (w[3], w[0]))
    print("  %s: iscritti al workshop %d (lista %s)" % (w[0], n, lid))
    return {"name": "[DIDACTA LANCIANO] %s - %s" % (w[0], w[4][:70]), "subject": w[4], "content": c,
            "from": {"fromName": "Spaggiari", "replyTo": "marketing@spaggiari.eu"},
            "subscriptionDetails": m["subscriptionDetails"], "subcategory": "batch", "businessUnitId": m.get("businessUnitId"), "language": "it",
            # 18/10 Andrea: tutti ricevono tutto, anche gli iscritti; 6460 = consenso spaggiari.eu No (19/10)
            "to": {"contactIlsLists": {"include": C.LISTE, "exclude": ["610", "5979", "6460"]}, "limitSendFrequency": False, "suppressGraymail": False},
            "webversion": {"enabled": False}}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "anteprima"
    if cmd == "anteprima":
        cartella = os.path.join(os.path.expanduser("~"), "audit", "anteprima_didacta")
        os.makedirs(cartella, exist_ok=True)
        for w in W:
            h = html(w).replace("{{ include_custom_fonts", "<!--").replace(") }}\n", "-->\n", 1)
            io.open(os.path.join(cartella, w[0] + ".html"), "w", encoding="utf-8").write(
                '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#EEF2F4"><div style="max-width:640px;margin:0 auto;background:#fff;padding:24px 20px">'
                '<div style="font:12px Arial;color:#666;margin-bottom:6px">Oggetto: %s<br>Anteprima: %s<br>Invio: %02d/%02d alle %02d:%02d</div>%s</div>'
                % (w[4], w[5], w[1][2], w[1][1], w[1][3], w[1][4], h))
        print("anteprime in", cartella)
        return
    ids = json.load(io.open(IDS)) if os.path.exists(IDS) else {}
    for w in W:
        quando = D.datetime(*w[1], tzinfo=C.ROMA).astimezone(D.timezone.utc)
        if cmd == "crea" and w[0] not in ids:
            b = corpo_email(w)
            b["publishDate"] = quando.strftime("%Y-%m-%dT%H:%M:%SZ")      # data nel corpo alla creazione: dopo il 9/10 mai PATCH+publish a freddo
            e = C.api("POST", "/marketing/v3/emails", b)
            ids[w[0]] = e["id"]
            print("creata", w[0], e["id"], e["state"])
        elif cmd == "aggiorna" and w[0] in ids:
            b = corpo_email(w)
            r = C.api("PATCH", "/marketing/v3/emails/%s" % ids[w[0]], {"subject": b["subject"], "content": b["content"], "to": b["to"]})
            print("aggiornata", w[0], ids[w[0]], r.get("state"))
        elif cmd == "programma" and w[0] in ids:
            if quando < D.datetime.now(D.timezone.utc) + D.timedelta(minutes=30):
                print("salto", w[0], ": l'orario previsto e' gia' passato o troppo vicino")
                continue
            e = C.api("GET", "/marketing/v3/emails/%s" % ids[w[0]])
            if e["state"] != "DRAFT":
                print("salto", w[0], ": stato", e["state"])
                continue
            if e.get("publishDate", "")[:16] != quando.strftime("%Y-%m-%dT%H:%M"):
                print("NON programmo", w[0], ": data letta", e.get("publishDate"))
                continue
            C.api("POST", "/marketing/v3/emails/%s/publish" % ids[w[0]], {})
            time.sleep(3)
            e = C.api("GET", "/marketing/v3/emails/%s" % ids[w[0]])
            print("programmata", w[0], e["state"], e.get("publishDate"))
        io.open(IDS, "w").write(json.dumps(ids))


if __name__ == "__main__":
    main()
