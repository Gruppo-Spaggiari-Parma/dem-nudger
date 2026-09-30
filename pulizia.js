/*
 * Spazzino dei DEM Tracking (Andrea, 30/9/2026).
 *
 * Il bootstrap crea un DEM Tracking per ogni destinatario di ogni evento, e nessuno li
 * toglieva: il 30 set erano 767.458 e hanno portato il portale al tetto dei 2.500.000
 * record custom (bloccando anche le altre integrazioni). Finito l'evento il tracking non
 * serve piu': invito e promemoria sono gia' partiti.
 *
 * Ogni giro archivia (cestino HubSpot, recuperabile per 90 giorni) fino a TETTO tracking
 * di eventi iniziati da piu' di GIORNI giorni. Leggero quando non c'e' niente da fare:
 * una sola ricerca.
 */
const PAT = process.env.HUBSPOT_PAT;
const BASE = 'https://api.hubapi.com';
const TR = '2-203372440';
const H = { Authorization: `Bearer ${PAT}`, 'Content-Type': 'application/json' };
const GIORNI = 3, TETTO = 5000;
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function call(url, opts, label, tries = 5) {
  for (let i = 1; i <= tries; i++) {
    let r;
    try { r = await fetch(url, opts); } catch (e) { if (i === tries) throw e; await sleep(1000 * i); continue; }
    if (r.status === 429 || r.status >= 500) { if (i === tries) throw new Error(`${label} ${r.status}`); await sleep(Math.min(1000 * 2 ** i, 12000)); continue; }
    return r;
  }
}

(async () => {
  if (!PAT) { console.error('HUBSPOT_PAT mancante'); process.exit(1); }
  const soglia = Date.now() - GIORNI * 86400000;
  const ids = [];
  let after;
  while (ids.length < TETTO) {
    const r = await call(`${BASE}/crm/v3/objects/${TR}/search`, { method: 'POST', headers: H, body: JSON.stringify({
      filterGroups: [{ filters: [{ propertyName: 'dem_v5_start_datetime', operator: 'LT', value: String(soglia) }] }],
      properties: ['dem_v5_evento_id'], limit: 100, ...(after ? { after } : {}) }) }, 'search-vecchi');
    if (!r.ok) throw new Error(`search ${r.status} ${(await r.text()).slice(0, 160)}`);
    const d = await r.json();
    (d.results || []).forEach(x => ids.push(x.id));
    after = d.paging?.next?.after;
    if (!after || Number(after) >= 10000) break;            // la ricerca non va oltre 10.000
    await sleep(250);
  }
  if (!ids.length) { console.log(new Date().toISOString(), 'pulizia: niente da togliere'); return; }
  let tolti = 0;
  for (let i = 0; i < ids.length; i += 100) {
    const r = await call(`${BASE}/crm/v3/objects/${TR}/batch/archive`, { method: 'POST', headers: H,
      body: JSON.stringify({ inputs: ids.slice(i, i + 100).map(id => ({ id })) }) }, 'archive');
    if (r.status === 204) tolti += Math.min(100, ids.length - i);
    else console.error(`  archive ${r.status} ${(await r.text()).slice(0, 140)}`);
    await sleep(300);
  }
  console.log(new Date().toISOString(), `pulizia: archiviati ${tolti} tracking di eventi iniziati da oltre ${GIORNI} giorni`);
})();
