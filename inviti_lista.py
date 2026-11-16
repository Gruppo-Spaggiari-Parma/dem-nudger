# -*- coding: utf-8 -*-
"""Inviti agli eventi SENZA record custom (Andrea, 30/9/2026).

Il sistema v5 creava un DEM Tracking per ogni destinatario di ogni evento: il 30 set erano
767.458 e hanno portato il portale al tetto dei 2.500.000 record custom, bloccando HubSpot.
Qui ogni evento ha tre EMAIL MARKETING normali, programmate sulle sue liste:

    T-14 invito · T-3 promemoria · T-1 promemoria        (alle ORA del giorno, Europe/Rome)

- destinatari: le liste `dem_target_list_ids` dell'evento, meno la 5979 (opposizioni art.21);
- le email nascono dai modelli v5 (T14/T3/T1): i dati dell'evento si scrivono DENTRO l'email,
  al posto dei token p144406271_dem_tracking.* che prima leggevano dal record;
- un invio il cui momento e' gia' passato non si fa (niente recuperi a sorpresa);
- gli id delle email stanno sull'evento, in `dem_v6_email_ids` ("T14:id,T3:id,T1:id"),
  cosi' ogni giro sa cosa ha gia' fatto: e' idempotente.

Quali eventi: `dem_strategy=LIVE`, non annullati, futuri, con `dem_v6_attivo=true`.
Il bootstrap v5 salta gli eventi con `dem_v6_attivo=true`.

Uso:  python inviti_lista.py [--prova <id evento>]   (--prova: solo lista interna 4236)
"""
import datetime as D
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("HUBSPOT_PAT") or open(os.path.expanduser("~/.hubspot_pat.txt")).read().strip()
BASE = "https://api.hubapi.com"
EV = "2-143900361"
MODELLI = {"T14": ("412313264319", 14), "T3": ("412278645961", 3), "T1": ("412278645964", 1)}
# eventi ItaliaScuola: stessi modelli ma col marchio proprio (mittente redazione@italiascuola.it, verde, footer IS) - clonati il 4/9/2026
MODELLI_IS = {"T14": ("465634433262", 14), "T3": ("465634433265", 3), "T1": ("465634433268", 1)}


def modelli(ev):
    return MODELLI_IS if (ev["properties"].get("brand") or "") == "Italia Scuola" else MODELLI
ORA = 9                                  # ora di invio, Europe/Rome
OPPOSIZIONI = "5979"                     # lista sempre esclusa (privacy art.21)
CONSENSO_NO = "6460"                     # consenso spaggiari.eu = No: esclusa da ogni invio (Andrea 19/10/2026)
CONSENSO_MAI_RAGGIUNTI = "6454"          # consenso si', mai raggiunti: sempre inclusa (Andrea 19/10/2026)
LISTA_PROVA = "4236"
ROMA = ZoneInfo("Europe/Rome")
PROVA = sys.argv[sys.argv.index("--prova") + 1] if "--prova" in sys.argv else None


def api(path, body=None, method="GET"):
    data = json.dumps(body).encode() if body is not None else None
    for k in range(5):
        req = urllib.request.Request(BASE + path, data=data, method=method,
                                     headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
                return json.loads(b) if b else {}
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                time.sleep(2 * (k + 1)); continue
            raise RuntimeError("%s %s -> %s %s" % (method, path, e.code, e.read().decode()[:400]))
    raise RuntimeError("troppi tentativi su " + path)


def ms(v):
    s = str(v or "").strip()
    if s.isdigit():
        return int(s)
    return int(D.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def valori(ev):
    """I valori che prima stavano sul DEM Tracking, calcolati una volta per evento."""
    p = ev["properties"]
    d = D.datetime.fromtimestamp(ms(p["start_datetime"]) / 1000, ROMA)
    giorni = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    mesi = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
            "settembre", "ottobre", "novembre", "dicembre"]
    return {
        "dem_v5_evento_nome": p.get("name") or "",
        "dem_v5_evento_data_display": "%s %d %s %d" % (giorni[d.weekday()], d.day, mesi[d.month - 1], d.year),
        "dem_v5_evento_orario_display": d.strftime("%H:%M"),
        "dem_v5_evento_venue": p.get("venue") or "",
        "dem_v5_evento_meeting_link": p.get("meeting_link") or "",
        "dem_v5_evento_featured_image": p.get("featured_image") or "",
        "dem_v5_evento_page_body": p.get("page_body_content") or "",
        "dem_v5_landing_url": p.get("dem_landing_url") or p.get("registration_page") or "",
    }, d


TOK = re.compile(r"\{\{\s*p144406271_dem_tracking\.(\w+)\s*\}\}")


NUDO = re.compile(r"p144406271_dem_tracking\.(\w+)")


def letterale(v):
    """Un valore come stringa HubL tra virgolette: i modelli usano il campo anche dentro
    {% if %}, {% set %} e filtri (|default, |regex_replace), non solo in {{ }}."""
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return '"' + " ".join(s.split("\n")).replace(chr(13), " ") + '"'


def riempi(x, val):
    """Sostituisce i campi del tracking con i valori dell'evento, dentro ogni stringa:
    prima {{ campo }} semplice -> testo, poi ogni altro riferimento -> stringa HubL."""
    if isinstance(x, str):
        x = TOK.sub(lambda m: val.get(m.group(1), ""), x)
        return NUDO.sub(lambda m: letterale(val.get(m.group(1), "")), x)
    if isinstance(x, list):
        return [riempi(y, val) for y in x]
    if isinstance(x, dict):
        return {k: riempi(v, val) for k, v in x.items()}
    return x


def pasquetta(anno):
    """Lunedi' dell'Angelo (algoritmo di Meeus/Jones/Butcher per la Pasqua)."""
    a, b, c = anno % 19, anno // 100, anno % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mese = (h + l - 7 * m + 114) // 31
    giorno = (h + l - 7 * m + 114) % 31 + 1
    return D.date(anno, mese, giorno) + D.timedelta(days=1)


def festivo(giorno):
    """Feste nazionali (Andrea, 16/11/2026: il T-1 del webinar bandi era finito sull'8 dicembre)."""
    fisse = {(1, 1), (6, 1), (25, 4), (1, 5), (2, 6), (15, 8), (1, 11), (8, 12), (25, 12), (26, 12)}
    return (giorno.day, giorno.month) in fisse or giorno == pasquetta(giorno.year)


def giorno_lavorativo(chiave, quando):
    """Niente invii di sabato, domenica e feste nazionali (Andrea, 8/10 e 16/11/2026): l'invito T-14 slitta
    al giorno lavorativo dopo, i promemoria T-3 e T-1 al giorno lavorativo prima."""
    while quando.weekday() >= 5 or festivo(quando.date()):
        quando += D.timedelta(days=1) if chiave == "T14" else -D.timedelta(days=1)
    return quando


NUMERI = {2: "due", 3: "tre", 4: "quattro", 5: "cinque", 6: "sei", 7: "sette"}
GIORNI_SETT = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
        "settembre", "ottobre", "novembre", "dicembre"]


def adatta(chiave, x, quando, inizio):
    """Quando il promemoria slitta (weekend o festa), «fra tre giorni» e «domani» non sono piu' veri
    (16/11/2026: il T-3 del 4/12 diceva «mancano 3 giorni» a un webinar del 9/12). Si riscrive la
    distanza vera: «mancano 5 giorni», «fra cinque giorni»; al posto di «domani» il giorno dell'evento."""
    veri = (inizio.date() - quando.date()).days
    if chiave == "T14" or veri == {"T3": 3, "T1": 1}[chiave]:
        return x
    if isinstance(x, list):
        return [adatta(chiave, y, quando, inizio) for y in x]
    if isinstance(x, dict):
        return {k: adatta(chiave, v, quando, inizio) for k, v in x.items()}
    if not isinstance(x, str):
        return x
    if chiave == "T3":
        x = re.sub(r"\b([Mm]ancano) 3 giorni", lambda m: "%s %d giorni" % (m.group(1), veri), x)
        return re.sub(r"\b([Ff])ra tre giorni", lambda m: "%sra %s giorni" % (m.group(1), NUMERI.get(veri, str(veri))), x)
    gs = GIORNI_SETT[inizio.weekday()]
    x = re.sub(r"\bDomani\b", gs.capitalize(), x)
    return re.sub(r"\bdomani\b", "%s %d %s" % (gs, inizio.day, MESI[inizio.month - 1]), x)


def crea_email(ev, chiave, quando, liste):
    mod = api("/marketing/v3/emails/%s" % modelli(ev)[chiave][0])
    val, inizio = valori(ev)
    nome = "[DEM v6] %s · %s · %s" % (chiave, (ev["properties"].get("name") or "")[:80], ev["id"])
    corpo = {
        "name": nome,
        "subject": adatta(chiave, riempi(mod["subject"], val), quando, inizio),
        "content": adatta(chiave, riempi(mod["content"], val), quando, inizio),
        "from": mod["from"],
        "subscriptionDetails": mod["subscriptionDetails"],
        "subcategory": "batch",
        "businessUnitId": mod.get("businessUnitId"),
        "language": mod.get("language") or "it",
        # Andrea 18-21/10/2026: tutti ricevono tutto -> filtro graymail spento, 6454 sempre dentro, fuori solo 5979 e 6460
        "to": {"contactIlsLists": {"include": sorted(set(liste) | {CONSENSO_MAI_RAGGIUNTI}), "exclude": [OPPOSIZIONI, CONSENSO_NO]},
               "limitSendFrequency": False, "suppressGraymail": False},
        "webversion": {"enabled": False},
        "publishDate": quando.astimezone(D.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    e = api("/marketing/v3/emails", corpo, "POST")
    api("/marketing/v3/emails/%s/publish" % e["id"], {}, "POST")   # programmata a publishDate
    return e["id"]


def eventi():
    filtri = [{"propertyName": "dem_strategy", "operator": "EQ", "value": "LIVE"},
              {"propertyName": "annullato", "operator": "NEQ", "value": "true"},
              {"propertyName": "start_datetime", "operator": "GTE", "value": str(int(time.time() * 1000))}]
    if PROVA:
        filtri = [{"propertyName": "hs_object_id", "operator": "EQ", "value": PROVA}]
    else:
        filtri.append({"propertyName": "dem_v6_attivo", "operator": "EQ", "value": "true"})
    r = api("/crm/v3/objects/%s/search" % EV, {"filterGroups": [{"filters": filtri}], "limit": 100,
            "properties": ["name", "brand", "start_datetime", "dem_target_list_ids", "dem_landing_url", "registration_page",
                           "venue", "meeting_link", "featured_image", "page_body_content", "dem_v6_email_ids"]}, "POST")
    return r.get("results") or []


def main():
    adesso = D.datetime.now(ROMA)
    for ev in eventi():
        p = ev["properties"]
        liste = [LISTA_PROVA] if PROVA else [s.strip() for s in (p.get("dem_target_list_ids") or "").split(",") if s.strip()]
        fatte = dict(x.split(":", 1) for x in (p.get("dem_v6_email_ids") or "").split(",") if ":" in x)
        _, inizio = valori(ev)
        nuove = {}
        for chiave, (_, giorni) in modelli(ev).items():
            if chiave in fatte:
                continue
            quando = giorno_lavorativo(chiave, (inizio - D.timedelta(days=giorni)).replace(hour=ORA, minute=0, second=0, microsecond=0))
            if chiave == "T1" and giorno_lavorativo("T3", (inizio - D.timedelta(days=3)).replace(hour=ORA, minute=0, second=0, microsecond=0)).date() == quando.date():
                fatte[chiave] = "saltato"                    # il venerdi del T-3 e' lo stesso giorno: un solo promemoria
                continue
            if chiave == "T14" and (p.get("brand") or "") == "Italia Scuola":
                # ItaliaScuola (Andrea, 15/10/2026): niente attesa dei 14 giorni, l'invito parte subito (rispettando il weekend)
                quando = giorno_lavorativo("T14", adesso + D.timedelta(minutes=10))
            if PROVA:
                quando = adesso + D.timedelta(minutes=10 + 5 * len(nuove))
            if quando <= adesso + D.timedelta(minutes=5):
                fatte[chiave] = "saltato"                    # momento gia' passato: niente invio
                continue
            nuove[chiave] = crea_email(ev, chiave, quando, liste)
            print("  %s %s: %s programmata %s su liste %s" % (ev["id"], (p.get("name") or "")[:50], chiave,
                                                             quando.strftime("%d/%m %H:%M"), ",".join(liste)))
        fatte.update(nuove)
        if not PROVA and (nuove or fatte != dict(x.split(":", 1) for x in (p.get("dem_v6_email_ids") or "").split(",") if ":" in x)):
            api("/crm/v3/objects/%s/%s" % (EV, ev["id"]), {"properties": {
                "dem_v6_email_ids": ",".join("%s:%s" % kv for kv in fatte.items())}}, "PATCH")
    print(D.datetime.now().isoformat(timespec="seconds"), "inviti_lista: fatto")


if __name__ == "__main__":
    main()
