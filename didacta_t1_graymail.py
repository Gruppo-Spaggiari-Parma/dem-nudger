# -*- coding: utf-8 -*-
"""Invio una tantum di T1 ai contatti che HubSpot aveva soppresso come graymail l'11/10 (lista 6244). 12/10/2026."""
import datetime as D, io, json, os, re, sys, time
import didacta_campagna as C

LISTA = "6244"
QUANDO = D.datetime(2026, 10, 12, 14, 0, tzinfo=C.ROMA)
t = next(x for x in C.TOCCHI if x[0] == "T1")
prog = C.programma()
corpo, _ = C.corpo_email(t, prog)
html = corpo["content"]["widgets"]["module_17787858993112"]["body"]["html"]
testo = re.sub(r"<[^>]+>", " ", html)
print("parole a rischio nel testo:", set(re.findall(r"domenica|ieri|oggi|domani|luned[iì]", testo, re.I)))
corpo["name"] = "[DIDACTA LANCIANO] T1 - ai soppressi graymail (12/10)"
corpo["to"] = {"contactIlsLists": {"include": [LISTA], "exclude": C.ESCLUDI + C.lista_esclusi()}, "limitSendFrequency": False, "suppressGraymail": False}
corpo["publishDate"] = QUANDO.astimezone(D.timezone.utc).isoformat().replace("+00:00", "Z")
if "--prova" in sys.argv:
    print(corpo["to"], corpo["publishDate"]); sys.exit()
e = C.api("POST", "/marketing/v3/emails", corpo)
eid = e["id"]; print("creata", eid, e["state"], e.get("publishDate"))
m = C.api("GET", "/marketing/v3/emails/%s" % eid)
atteso = QUANDO.astimezone(D.timezone.utc)
pd = D.datetime.fromisoformat(m["publishDate"].replace("Z", "+00:00"))
assert m["state"] == "DRAFT" and pd == atteso, (m["state"], m["publishDate"])
C.api("POST", "/marketing/v3/emails/%s/publish" % eid, {})
time.sleep(3)
m = C.api("GET", "/marketing/v3/emails/%s" % eid)
print("dopo publish:", m["state"], m["publishDate"])
assert m["state"] == "SCHEDULED"
io.open(os.path.join(C.QUI, "didacta_t1_graymail_id.txt"), "w").write(eid)
