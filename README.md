# dem-nudger

Il motore che tiene in movimento le DEM degli eventi (HubSpot, portale 144406271).
Gira ogni 5 minuti e fa tre cose.

## 1. `nudge.js` — il colpetto

Alcuni workflow HubSpot lavorano solo quando una proprieta' cambia. Per farli
ripartire su un evento gia' in coda si scrive `dem_v5_bootstrap_status` a `idle`
e subito dopo di nuovo a `ready`: il cambiamento li risveglia.

Nello stesso passaggio raccoglie gli eventi con la spunta "Annulla e avvisa" e
porta le loro righe di `dem_tracking` a `send_cancel`, cosi' parte l'avviso di
annullamento a chi era iscritto.

## 2. `bootstrap.js` — la coda di invio

Prende gli eventi in `ready`/`in_progress`, legge le liste in
`dem_target_list_ids` e crea una riga `dem_tracking` per ogni contatto. Da li' in
poi sono i workflow HubSpot a mandare invito, T-3 e T-1.

Lo stato iniziale dipende da quanto manca all'evento: entro 14 giorni
`send_immediate` (parte subito), oltre `pending` (aspetta il suo T-14).

**Perche' sta qui e non dentro HubSpot.** Fino al 15 settembre 2026 lo faceva
un'azione di codice dentro il workflow *[DEM v5] Bootstrap multi-lista -
CONTINUATION*, con un segreto suo (`HAPI_KEY`). Da allora quell'azione muore
prima di scrivere una sola riga: gli eventi restano in `ready` con `total=0` e
nessun log. Il 22 settembre erano fermi sette eventi e nessuno se n'era accorto,
perche' **un lavoro che non parte non lascia tracce**.

Si puo' rilanciare quante volte si vuole: `dem_v5_dedup_key` e' unico, quindi non
nascono doppioni. Lavora a fette da 2.000 contatti e riprende dal cursore.

## 3. `coda.json` — quando un evento puo' partire

```json
{ "<id evento>": "AAAA-MM-GG" }
```

L'evento non viene costruito prima di quel giorno. Serve quando piu' eventi
puntano alla **stessa lista**: senza, la stessa persona riceve tre inviti nello
stesso minuto. Una riga si toglie quando l'evento e' partito.

## Attenzione

⚠️ **GitHub spegne la pianificazione da solo** se il repository resta senza
commit per sessanta giorni (`disabled_inactivity`), e non avvisa in modo visibile:
il 19 settembre 2026 il motore si e' fermato cosi'. Si riaccende con
`gh workflow enable dem-nudger.yml`. Un commit ogni tanto azzera il conto.

Segreto richiesto: `HUBSPOT_PAT` (Private App del portale 144406271).
