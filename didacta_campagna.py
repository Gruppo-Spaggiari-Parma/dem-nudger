# -*- coding: utf-8 -*-
"""Campagna Didacta Lanciano (21-23 ottobre 2026): 6 email a giorni alterni (Andrea, 9/10/2026).

  python didacta_campagna.py anteprima        scrive le 6 anteprime HTML in anteprima_didacta/ (niente su HubSpot)
  python didacta_campagna.py crea             crea le 6 email come BOZZE in HubSpot (non programma, non invia)
  python didacta_campagna.py aggiorna         riscrive il contenuto delle bozze gia' create (id in didacta_email_ids.json)

Il programma degli incontri si legge da HubSpot (eventi DID-LAN pubblicati): si rilancia 'aggiorna' prima di ogni invio.
"""
import datetime as D
import html as H
import io
import json
import os
import re
import sys
import time
import urllib.request
from zoneinfo import ZoneInfo

ROMA = ZoneInfo("Europe/Rome")
TOKEN = os.environ.get("HUBSPOT_PAT") or open(os.path.expanduser("~/.hubspot_pat.txt"), encoding="utf-8-sig").read().strip()
QUI = os.path.dirname(os.path.abspath(__file__))
IDS = os.path.join(QUI, "didacta_email_ids.json")
MODELLO = os.path.join(QUI, "tpl_T14_spaggiari.json")          # struttura (testata, piede, iscrizione) delle DEM v5
PAGINA = "https://www.spaggiari.eu/didacta-2026-lanciano"
UTM = "?utm_source=hubspot&utm_medium=email&utm_campaign=didacta-lanciano-2026&utm_content=%s"
PADIGLIONE = "Padiglione C"
STAND = "Stand 19"
LISTE = ["2352", "65", "129", "2323", "1492", "1493", "1494", "1495", "1035", "1037"]      # come Didacta Firenze (marzo 2026)
ESCLUDI = ["610", "5979"]          # lista di esclusione del sito, opposizioni art.21 (+ la lista degli iscritti, vedi ESCLUSI_ISCRITTI)
ESCLUSI_ISCRITTI = os.path.join(QUI, "didacta_lista_iscritti.txt")

PETROLIO, ORO, NERO, GRIGIO = "#05484C", "#e8b547", "#0E2A4D", "#51606E"
FONT_T = "'Gilroy',Arial,sans-serif"
FONT_B = "'Benton Sans Pro',Arial,sans-serif"

# (chiave, quando, oggetto, anteprima, etichetta, titolo, sottotitolo)
TOCCHI = [
    ("T1", (2026, 10, 11), "Didacta Lanciano: proiettati nel futuro, anche per i prossimi 100 anni",
     "21-23 ottobre a Lanciano o in live streaming. Iscriviti e ricevi in omaggio il biglietto di 3 giorni per Didacta.",
     "Didacta Lanciano 2026", "Proiettati nel futuro, anche per i prossimi 100 anni",
     "21&ndash;23 ottobre 2026 &middot; Lanciano o in live streaming"),
    ("T2", (2026, 10, 13), "Didacta Lanciano: il tuo biglietto in omaggio, iscriviti agli eventi Spaggiari",
     "Un solo evento basta: la fiera ti invia il biglietto valido 3 giorni, del valore di 30 euro.",
     "Biglietto in omaggio", "Il tuo biglietto per Didacta, in omaggio",
     "Valido per i 3 giorni di fiera &middot; valore 30 &euro;"),
    ("T3", (2026, 10, 15), "Didacta Lanciano: il programma per dirigenti, DSGA e docenti",
     "Incontri brevi e concreti, in fiera o in streaming. Scegli i tuoi e iscriviti.",
     "Il programma", "Il programma Spaggiari a Didacta Lanciano",
     "Incontri brevi e concreti, in fiera o in streaming"),
    ("T4", (2026, 10, 17), "Didacta Lanciano: ultimi giorni per ricevere il biglietto in omaggio",
     "Iscriviti a un evento Spaggiari entro il 22 ottobre: la fiera ti invia il biglietto di 3 giorni, valido anche per l'ultimo giorno.",
     "Ultimi giorni", "Ultimi giorni per ricevere il biglietto in omaggio",
     "Didacta Lanciano &middot; 21&ndash;23 ottobre"),
    ("T5", (2026, 10, 19), "Didacta Lanciano: mercoledì si parte, scegli i tuoi incontri",
     "I primi incontri di mercoledì 21 ottobre, in fiera o in streaming.",
     "Mercoled&igrave; si parte", "Mercoled&igrave; 21 ottobre si parte",
     "Scegli gli incontri che ti servono"),
    ("T6", (2026, 10, 21), "Didacta Lanciano: oggi gli incontri anche in diretta",
     "Gli incontri di oggi, anche in streaming. Iscriviti e ricevi il link.",
     "Oggi a Didacta Lanciano", "Oggi si parte: segui gli incontri in diretta",
     "Anche in live streaming, dal tuo computer"),
    ("T7", (2026, 10, 22), "Didacta Lanciano: gli incontri di gioved\u00ec, in diretta",
     "Anche oggi gli incontri sono in live streaming. Iscriviti e ricevi il link per collegarti.",
     "Gioved&igrave; 22 ottobre", "Oggi a Didacta Lanciano: gli incontri della giornata",
     "Segui in diretta, dove sei"),
    ("T8", (2026, 10, 23), "Didacta Lanciano: ultimo giorno, gli incontri in diretta",
     "Gli incontri di oggi, in live streaming. Iscriviti e ricevi il link per collegarti.",
     "Venerd&igrave; 23 ottobre", "Ultimo giorno a Didacta Lanciano",
     "Gli incontri di oggi, in diretta"),
]


def api(m, u, b=None):
    time.sleep(0.15)
    r = urllib.request.Request("https://api.hubapi.com" + u, data=json.dumps(b).encode() if b is not None else None, method=m,
                               headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        x = urllib.request.urlopen(r, timeout=90).read()
        return json.loads(x) if x else {}
    except urllib.error.HTTPError as e:
        raise RuntimeError("%s %s -> %s %s" % (m, u[:60], e.code, e.read().decode()[:300]))


def programma():
    """{giorno(date): [dict(ora, fine, nome, id, ext)]} dagli eventi DID-LAN pubblicati."""
    r = api("POST", "/crm/v3/objects/2-143900361/search", {"filterGroups": [{"filters": [
        {"propertyName": "external_id", "operator": "CONTAINS_TOKEN", "value": "DID-LAN*"}]}],
        "properties": ["name", "start_datetime", "end_datetime", "is_published", "annullato", "external_id"], "limit": 100})
    out = {}
    for e in r["results"]:
        p = e["properties"]
        if p.get("is_published") != "true" or p.get("annullato") == "true" or p["external_id"] == "DID-LAN":
            continue
        i = D.datetime.fromisoformat(p["start_datetime"].replace("Z", "+00:00")).astimezone(ROMA)
        f = D.datetime.fromisoformat(p["end_datetime"].replace("Z", "+00:00")).astimezone(ROMA)
        out.setdefault(i.date(), []).append({"ora": i.strftime("%H:%M"), "fine": f.strftime("%H:%M"), "nome": p["name"], "id": e["id"], "ext": p["external_id"]})
    for g in out:
        out[g].sort(key=lambda x: x["ora"])
    return out


def descrizioni():
    """{id evento: descrizione breve} dalle schede della pagina pubblica (testo gia' approvato)."""
    try:
        h = urllib.request.urlopen(urllib.request.Request(PAGINA, headers={"User-Agent": "Mozilla/5.0"}), timeout=60).read().decode("utf-8", "replace")
    except Exception:
        return {}
    out = {}
    for c in re.findall(r'<div class="orca-event-card">(.*?)</a>\s*</div>', h, re.S):
        i = re.findall(r"registrazione/nosession/(\d+)", c)
        d = re.findall(r'class="orca-event-description"[^>]*>(.*?)</p>', c, re.S)
        if i and d:
            out[i[0]] = H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", d[0]))).strip()
    return out


# Scelte di Andrea (9/10/2026): nessun incontro ripetuto sulle tre giornate (basta una volta); Jobiri fuori da tutte le mail.
# Le card (in evidenza) sono quelle indicate da lui, per giornata; gli altri incontri restano nell'elenco compatto, una volta sola.
IN_EVIDENZA = {"DID-LAN03", "DID-LAN09", "DID-LAN10",              # mer 21: Ver.Di & Vo.Ce, ForSchool e LearnIN, Dreamshaper
               "DID-LAN12", "DID-LAN14", "DID-LAN21", "DID-LAN22",  # gio 22: PLS, BoxDox, Prima Visione Web, ScuolaSHOP (che e' il 22 alle 17:00)
               "DID-LAN23", "DID-LAN26"}                            # ven 23: FaVoLab, Vittoriale (D'Annunzio)
ESCLUSI_TITOLO = ("Jobiri",)
GIORNO_UNICO = {"Ver.Di": 21, "PLS": 22}       # incontri replicati in piu' giornate: si tiene una sola occorrenza, in questo giorno


def pulisci(prog):
    """Toglie Jobiri e le repliche: ogni incontro compare una volta sola nelle tre giornate."""
    out, visti = {}, set()
    for g in sorted(prog):
        for ev in prog[g]:
            if any(k in ev["nome"] for k in ESCLUSI_TITOLO):
                continue
            chiave = next((k for k in GIORNO_UNICO if k in ev["nome"]), None)
            if chiave and g.day != GIORNO_UNICO[chiave]:
                continue
            if ev["nome"] in visti:
                continue
            visti.add(ev["nome"])
            out.setdefault(g, []).append(ev)
    return out


GIORNI = ["luned&igrave;", "marted&igrave;", "mercoled&igrave;", "gioved&igrave;", "venerd&igrave;", "sabato", "domenica"]


def p(t, extra=""):
    return '<p style="margin:0 0 14px 0;font-family:%s;font-size:16px;line-height:1.65;color:#1a2b3c;%s">%s</p>' % (FONT_B, extra, t)


def cta(testo, chiave):
    # pulsante «a prova di client»: un solo elemento con lo sfondo, padding uguale sui quattro lati, niente tag <font> sovrapposti
    return ('<table role="presentation" align="center" cellpadding="0" cellspacing="0" border="0" style="margin:26px auto 14px auto;border-collapse:separate;"><tr>'
            '<td align="center" bgcolor="%s" style="background-color:%s;border-radius:999px;mso-padding-alt:20px 56px;">'
            '<a href="%s" style="display:block;background-color:%s;color:%s;padding:20px 56px;line-height:20px;text-decoration:none;font-size:15px;font-weight:bold;'
            'border-radius:999px;text-transform:uppercase;letter-spacing:0.6px;font-family:%s;text-align:center;">%s</a></td></tr></table>'
            ) % (ORO, ORO, PAGINA + UTM % chiave, ORO, PETROLIO, FONT_T, testo)


def riquadro(titolo, righe, colore="#FFF7E0", barra=ORO):
    r = "".join('<div style="font-family:%s;font-size:15px;line-height:1.6;color:#1a2b3c;margin:0 0 6px 0;">%s</div>' % (FONT_B, x) for x in righe)
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="width:100%%;border-collapse:separate;margin:8px 0 18px 0;">'
            '<tr><td width="6" bgcolor="%s" style="background-color:%s;border-radius:6px 0 0 6px;">&nbsp;</td>'
            '<td bgcolor="%s" style="background-color:%s;padding:16px 20px;border-radius:0 12px 12px 0;">'
            '<div style="font-family:%s;font-size:14px;font-weight:800;letter-spacing:0.8px;text-transform:uppercase;color:%s;margin:0 0 8px 0;">%s</div>%s</td></tr></table>'
            ) % (barra, barra, colore, colore, FONT_T, PETROLIO, titolo, r)


def box_biglietto():
    return riquadro("Biglietto di 3 giorni in omaggio", [
        "Iscriviti a un nostro evento: <strong>la fiera di Didacta ti invia direttamente il biglietto</strong>, valido per tutti e tre i giorni, del valore di 30 &euro;.",
        "Puoi iscriverti <strong>fino al 22 ottobre</strong>: il biglietto &egrave; valido anche per l&rsquo;ultimo giorno.",
        "Inserisci con attenzione il tuo indirizzo e-mail: &egrave; quello a cui arriva il biglietto."])


def box_dove():
    return riquadro("Dove trovarci", [
        "<strong>Quando</strong> &middot; 21&ndash;23 ottobre 2026",
        "<strong>Dove</strong> &middot; Polo Fieristico d&rsquo;Abruzzo, Loc. Iconicella snc, Lanciano (CH)",
        "<strong>Padiglione e stand</strong> &middot; %s &middot; %s" % (PADIGLIONE, STAND),
        "Oppure <strong>in live streaming</strong>, dal tuo computer."], colore="#E9F3F2", barra=PETROLIO)


def sfumato(i, n, fine=0.58):
    """Petrolio con trasparenza progressiva lungo la giornata: la prima card e' piena, l'ultima arriva a `fine` (0-1).
    Fuso sul bianco, perche' i client di posta non gestiscono rgba."""
    alfa = 1.0 if n <= 1 else 1.0 - (1.0 - fine) * i / (n - 1)
    base = (0x05, 0x48, 0x4C)
    return "#%02X%02X%02X" % tuple(round(c * alfa + 255 * (1 - alfa)) for c in base)


def card(ev, desc, colore=PETROLIO):
    link = "https://www.spaggiari.eu/eventi/registrazione/nosession/%s?hsLang=it&amp;utm_source=hubspot&amp;utm_medium=email&amp;utm_campaign=didacta-lanciano-2026&amp;utm_content=card" % ev["id"]
    d = ('<div style="font-family:%s;font-size:14px;line-height:1.5;color:%s;margin:0 0 10px 0;">%s</div>' % (FONT_B, GRIGIO, H.escape(desc))) if desc else ""
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="width:100%%;border-collapse:separate;margin:0 0 12px 0;border:1px solid #DCE5E8;border-radius:14px;">'
            '<tr><td width="92" valign="middle" align="center" bgcolor="%s" style="background-color:%s;border-radius:13px 0 0 13px;padding:16px 8px;">'
            '<div style="font-family:%s;font-size:22px;font-weight:800;line-height:1.1;color:#ffffff;">%s</div>'
            '<div style="font-family:%s;font-size:12px;line-height:1.3;color:#FFFFFF;margin-top:4px;">%s</div></td>'
            '<td valign="middle" style="padding:16px 18px;">'
            '<div style="font-family:%s;font-size:16px;font-weight:800;line-height:1.3;color:%s;margin:0 0 6px 0;">%s</div>%s'
            '<a href="%s" style="font-family:%s;font-size:14px;font-weight:bold;color:%s;text-decoration:underline;">Iscriviti all&rsquo;incontro &rarr;</a></td></tr></table>'
            ) % (colore, colore, FONT_T, ev["ora"], FONT_B, "fino alle " + ev["fine"], FONT_T, NERO, H.escape(ev["nome"]), d, link, FONT_B, PETROLIO)


def programma_card(prog, giorni=None):
    """Le tre giornate: card per gli incontri in evidenza, elenco compatto per gli altri."""
    desc = descrizioni()
    prog = pulisci(prog)
    out = ""
    for g in sorted(prog):
        if giorni and g not in giorni:
            continue
        evs = prog[g]
        out += ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="width:100%%;margin:26px 0 12px 0;"><tr>'
                '<td style="border-bottom:3px solid %s;padding:0 0 8px 0;"><span style="font-family:%s;font-size:21px;font-weight:800;color:%s;">%s %d ottobre</span>'
                '<span style="font-family:%s;font-size:13px;color:%s;"> &nbsp;&middot;&nbsp; %d incontri</span></td></tr></table>'
                ) % (ORO, FONT_T, NERO, GIORNI[g.weekday()].capitalize(), g.day, FONT_B, GRIGIO, len(evs))
        evidenza = [ev for ev in evs if ev["ext"] in IN_EVIDENZA]
        for i, ev in enumerate(evidenza):
            out += card(ev, desc.get(ev["id"], ""), sfumato(i, len(evidenza)))
        altri = [ev for ev in evs if ev["ext"] not in IN_EVIDENZA]
        if altri:
            out += '<div style="font-family:%s;font-size:13px;font-weight:800;letter-spacing:0.8px;text-transform:uppercase;color:%s;margin:14px 0 6px 0;">Anche in giornata</div>' % (FONT_T, PETROLIO)
            for ev in altri:
                out += ('<div style="font-family:%s;font-size:15px;line-height:1.5;color:#1a2b3c;margin:0 0 6px 0;padding:0 0 6px 0;border-bottom:1px solid #E3E9EC;">'
                        '<span style="display:inline-block;min-width:96px;font-weight:bold;color:%s;">%s&ndash;%s</span> %s</div>'
                        ) % (FONT_B, PETROLIO, ev["ora"], ev["fine"], H.escape(ev["nome"]))
    return out


def programma_giorno(prog, giorno):
    """Tutti gli incontri di UNA giornata come card (Jobiri escluso, come in tutte le mail)."""
    desc = descrizioni()
    evs = [ev for ev in prog.get(giorno, []) if not any(k in ev["nome"] for k in ESCLUSI_TITOLO)]
    out = ""
    for i, ev in enumerate(evs):
        out += card(ev, desc.get(ev["id"], ""), sfumato(i, len(evs)))
    return out


def corpo(chiave, prog):
    if chiave == "T1":
        return (p("A Lanciano guardiamo avanti, con gli strumenti e le idee che accompagnano dirigenti, DSGA e docenti nei prossimi 100 anni.")
                + p("Tre giorni di incontri brevi e concreti, da seguire in fiera o da casa: "
                    "riunioni e votazioni digitali, affidamenti e acquisti, progettazione didattica, sicurezza e formazione, il sito della scuola, ScuolaSHOP. "
                    "Ogni giorno si aggiungono nuovi appuntamenti: sulla pagina trovi sempre il programma aggiornato.")
                + box_biglietto() + cta("Scopri gli eventi e iscriviti", "t1") + box_dove())
    if chiave == "T2":
        return (p("Iscrivendoti anche a <strong>un solo evento</strong> Spaggiari a Didacta Lanciano, ricevi gratuitamente il biglietto valido per i tre giorni di fiera. Hai tempo fino al <strong>22 ottobre</strong>: il biglietto vale anche per l&rsquo;ultimo giorno.")
                + riquadro("Come si fa", ["<strong>1.</strong> Scegli un incontro dal programma.",
                                          "<strong>2.</strong> Inserisci i tuoi dati e un indirizzo e-mail corretto.",
                                          "<strong>3.</strong> La fiera di Didacta ti invia il biglietto direttamente a quell&rsquo;indirizzo."],
                           colore="#E9F3F2", barra=PETROLIO)
                + p("Se non puoi essere a Lanciano, ti aspettiamo in live streaming: gli incontri si seguono dal computer, con lo stesso link di iscrizione.")
                + cta("Iscriviti e ricevi il biglietto", "t2") + box_dove())
    if chiave == "T3":
        return (p("Incontri di 25&ndash;60 minuti, pensati per chi lavora nella scuola, in tre giornate. Scegli quelli che ti servono e iscriviti: "
                  "ricevi in omaggio il biglietto di 3 giorni per Didacta.")
                + programma_card(prog) + cta("Vedi tutto il programma", "t3") + box_biglietto() + box_dove())
    if chiave == "T4":
        return (p("Mancano pochi giorni a Didacta Lanciano. Iscriviti a un nostro evento <strong>entro gioved&igrave; 22 ottobre</strong>: "
                  "la fiera ti invia il biglietto di 3 giorni, valido anche per l&rsquo;ultimo giorno, all&rsquo;indirizzo e-mail che indichi.")
                + box_biglietto()
                + p("Ecco gli incontri delle tre giornate: partecipi in fiera o in live streaming, come preferisci.")
                + programma_card(prog) + cta("Iscriviti ora", "t4") + box_dove())
    if chiave == "T5":
        return (p("Mercoled&igrave; si parte. Tre giornate di incontri brevi e concreti: scegli quelli che ti servono e partecipa in fiera o in live streaming. "
                  "Se ti iscrivi entro gioved&igrave; 22 ottobre ricevi in omaggio il biglietto per Didacta.")
                + programma_card(prog) + cta("Scegli i tuoi incontri", "t5") + box_dove())
    if chiave == "T6":
        return (p("Da oggi a venerd&igrave; siamo a Didacta Lanciano. Questi sono gli incontri di oggi: puoi seguirli in live streaming dal tuo computer, "
                  "senza spostarti. Iscriviti e ricevi il link per collegarti. "
                  "Hai tempo fino a domani, gioved&igrave; 22 ottobre, per ricevere in omaggio il biglietto di Didacta, valido anche per l&rsquo;ultimo giorno.")
                + programma_giorno(prog, D.date(2026, 10, 21)) + cta("Iscriviti e segui in diretta", "t6") + box_dove())
    if chiave == "T7":
        return (p("Anche oggi gli incontri sono in live streaming: scegli quelli che ti servono, iscriviti e ricevi il link per collegarti. "
                  "<strong>Oggi &egrave; l&rsquo;ultimo giorno</strong> per iscriverti e ricevere in omaggio il biglietto di Didacta, valido anche per domani.")
                + programma_giorno(prog, D.date(2026, 10, 22)) + cta("Iscriviti e segui in diretta", "t7") + box_dove())
    if chiave == "T8":
        return (p("Oggi chiudiamo tre giornate di incontri a Didacta Lanciano. Gli incontri di oggi si seguono in live streaming dal tuo computer: "
                  "iscriviti e ricevi il link per collegarti.")
                + programma_giorno(prog, D.date(2026, 10, 23)) + cta("Iscriviti e segui in diretta", "t8") + box_dove())


def html_modulo(t, prog):
    chiave, _, oggetto, anteprima, etichetta, titolo, sotto = t
    testata = ('<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%%" style="width:100%%;border-collapse:separate;background-color:%s;border-radius:20px;">'
               '<tr><td style="padding:32px 30px 0 30px;" align="center"><img src="https://144406271.fs1.hubspotusercontent-eu1.net/hubfs/144406271/Spaggiari/Loghi/logo_spaggiari_foglia_neg_400.png" alt="Spaggiari" width="190" style="width:190px;max-width:60%%;height:auto;border:0;"></td></tr>'
               '<tr><td align="center" style="padding:22px 30px 0 30px;font-family:%s;color:%s;font-size:12px;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;">%s</td></tr>'
               '<tr><td align="center" style="padding:10px 34px 0 34px;"><h1 style="margin:0;font-family:%s;font-size:31px;font-weight:800;line-height:1.2;color:#ffffff;">%s</h1></td></tr>'
               '<tr><td align="center" style="padding:14px 34px 34px 34px;font-family:%s;font-size:16px;line-height:1.5;color:#CFE6E4;">%s</td></tr></table>'
               ) % (PETROLIO, FONT_T, ORO, etichetta, FONT_T, titolo, FONT_B, sotto)
    firma = ('<p style="margin:22px 0 0 0;font-family:%s;font-size:16px;line-height:1.6;color:#1a2b3c;font-style:italic;">A presto a Lanciano,<br>Spaggiari</p>' % FONT_B)
    return ('{{ include_custom_fonts({"Benton Sans Pro":["Chiaro","Corsivo chiaro","Corsivo extra grassetto","Corsivo normale","Corsivo semi grassetto","Extra grassetto","Normale","Semi grassetto"]}) }}\n'
            + testata
            + '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" border="0" style="width:100%%;"><tr><td style="padding:26px 6px 0 6px;">'
            + corpo(chiave, prog) + firma + '</td></tr></table>'
            + '<div style="font-family:%s;font-size:12.5px;line-height:1.6;color:#6a7a82;text-align:center;margin:18px 0 0 0;">Spaggiari &egrave; al fianco della scuola dal 1926, con software e servizi per la didattica, la segreteria e le famiglie.</div>' % FONT_B)


def contenuto(t, prog):
    m = json.load(io.open(MODELLO, encoding="utf-8"))
    c = m["content"]
    c["widgets"]["module_17787858993112"]["body"]["html"] = html_modulo(t, prog)
    c["widgets"]["preview_text"] = {**c["widgets"].get("preview_text", {}), "body": {"value": t[3]}, "name": "preview_text", "type": "text"} \
        if "preview_text" in c["widgets"] else c["widgets"].get("preview_text")
    return m, c


def lista_esclusi():
    """Liste statiche escluse: iscritti agli eventi (6237, tenuta dal motore) e contatti gia' raggiunti dalle 8 mail partite per errore il 9/10 (6238)."""
    out = []
    for nome in (ESCLUSI_ISCRITTI, os.path.join(QUI, "didacta_lista_raggiunti.txt")):
        try:
            out += [x.strip() for x in io.open(nome, encoding="utf-8") if x.strip()]
        except FileNotFoundError:
            pass
    return out


def corpo_email(t, prog):
    m, c = contenuto(t, prog)
    d = D.datetime(*t[1], 9, 0, tzinfo=ROMA)
    return {"name": "[DIDACTA LANCIANO] %s - %s" % (t[0], t[2][:70]), "subject": t[2], "content": c, "from": {"fromName": "Spaggiari", "replyTo": "marketing@spaggiari.eu"},
            "subscriptionDetails": m["subscriptionDetails"], "subcategory": "batch", "businessUnitId": m.get("businessUnitId"), "language": "it",
            "to": {"contactIlsLists": {"include": LISTE, "exclude": ESCLUDI + lista_esclusi()}, "limitSendFrequency": False, "suppressGraymail": True},
            "webversion": {"enabled": False}}, d


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "anteprima"
    prog = programma()
    if cmd == "anteprima":
        os.makedirs(os.path.join(QUI, "anteprima_didacta"), exist_ok=True)
        for t in TOCCHI:
            h = html_modulo(t, prog).replace("{{ include_custom_fonts", "<!--").replace(") }}\n", "-->\n", 1)
            io.open(os.path.join(QUI, "anteprima_didacta", t[0] + ".html"), "w", encoding="utf-8").write(
                '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#EEF2F4"><div style="max-width:640px;margin:0 auto;background:#fff;padding:24px 20px">'
                '<div style="font:12px Arial;color:#666;margin-bottom:6px">Oggetto: %s<br>Anteprima: %s</div>%s</div>' % (t[2], t[3], h))
        print("anteprime scritte:", len(TOCCHI))
        return
    ids = json.load(io.open(IDS)) if os.path.exists(IDS) else {}
    for t in TOCCHI:
        corpo_, d = corpo_email(t, prog)
        if cmd == "crea" and t[0] not in ids:
            corpo_["publishDate"] = d.astimezone(D.timezone.utc).isoformat().replace("+00:00", "Z")     # data nel corpo alla creazione (PATCH poi publish ha mandato tutto subito il 9/10)
            corpo_["name"] = corpo_["name"] + " (v2)"
            e = api("POST", "/marketing/v3/emails", corpo_)
            ids[t[0]] = e["id"]; print("creata", t[0], e["id"], e["state"])
        elif cmd == "aggiorna" and t[0] in ids:
            r = api("PATCH", "/marketing/v3/emails/%s" % ids[t[0]], {"subject": corpo_["subject"], "content": corpo_["content"], "to": corpo_["to"]})
            print("aggiornata", t[0], ids[t[0]], r.get("state"))
        io.open(IDS, "w").write(json.dumps(ids))


if __name__ == "__main__":
    main()
