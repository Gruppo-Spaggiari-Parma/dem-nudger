/*
 * Bootstrap DEM v5 - costruisce la coda di invio di un evento.
 *
 * Perche' vive qui e non piu' dentro HubSpot. Fino al 15 set 2026 il lavoro lo
 * faceva un'azione di codice dentro il workflow "[DEM v5] Bootstrap multi-lista
 * - CONTINUATION", con un segreto suo (HAPI_KEY). Da allora quell'azione muore
 * prima di scrivere anche una sola riga: gli eventi restano in "ready", con
 * total=0 e nessun log, e nessuno se ne accorge, perche' un lavoro che non parte
 * non lascia tracce. Il 22 set erano fermi sette eventi.
 *
 * Qui il token e' lo stesso del nudger, che si sa funzionante perche' lo si vede
 * lavorare a ogni giro.
 *
 * E' idempotente: dem_v5_dedup_key = `${eventoId}_${contattoId}` e' unico, quindi
 * rilanciarlo non crea doppioni. Lavora a fette da CHUNK contatti e riprende dal
 * cursore, cosi' sta dentro il tempo massimo del job.
 *
 * coda.json rallenta di proposito eventi che punterebbero alla stessa lista nello
 * stesso momento: {"<id evento>": "AAAA-MM-GG"} = non prima di quel giorno.
 */
const fs = require('fs');
const PAT = process.env.HUBSPOT_PAT;
const BASE = 'https://api.hubapi.com';
const EV = '2-143900361', TR = '2-203372440';
const H = { Authorization: `Bearer ${PAT}`, 'Content-Type': 'application/json' };
// Quanto lavora un evento per giro. 2.000 era la misura dell'azione HubSpot,
// legata al suo tempo massimo; qui il tetto e' il timeout del job, molto piu'
// largo. Alzarlo conta perche' il collo di bottiglia e' la frequenza con cui
// GitHub esegue davvero il cron (a */5 capita che passino 10-15 minuti).
const CHUNK = 6000, PAGE = 250;
const sleep = ms => new Promise(r => setTimeout(r, ms));

const coda = (() => {
  try { return JSON.parse(fs.readFileSync(__dirname + '/coda.json', 'utf8')); } catch (e) { return {}; }
})();

async function call(url, opts, label, tries = 5) {
  for (let i = 1; i <= tries; i++) {
    let r;
    try { r = await fetch(url, opts); } catch (e) { if (i === tries) throw e; await sleep(1000 * i); continue; }
    if (r.status === 429 || r.status >= 500) {
      if (i === tries) throw new Error(`${label} ${r.status}`);
      await sleep(Math.min(1000 * 2 ** i, 12000));
      continue;
    }
    return r;
  }
}

async function json(url, opts, label) {
  const r = await call(url, opts, label);
  if (!r.ok) throw new Error(`${label} ${r.status} ${(await r.text()).slice(0, 180)}`);
  return r.json();
}

const patchEvento = (id, props) =>
  json(`${BASE}/crm/v3/objects/${EV}/${id}`,
    { method: 'PATCH', headers: H, body: JSON.stringify({ properties: props }) }, `patch ${id}`);

async function daFare() {
  const d = await json(`${BASE}/crm/v3/objects/${EV}/search`, {
    method: 'POST', headers: H, body: JSON.stringify({
      filterGroups: [{ filters: [
        { propertyName: 'dem_v5_bootstrap_status', operator: 'IN', values: ['ready', 'in_progress'] },
        { propertyName: 'annullato', operator: 'NEQ', value: 'true' },
        { propertyName: 'dem_strategy', operator: 'EQ', value: 'LIVE' }] }],
      properties: ['name', 'start_datetime', 'dem_target_list_ids', 'dem_landing_url', 'registration_page',
        'venue', 'meeting_link', 'featured_image', 'page_body_content',
        'dem_v5_bootstrap_status', 'dem_v5_bootstrap_cursor', 'dem_v5_bootstrap_total',
        'dem_v5_bootstrap_cursor_token'],
      limit: 100 })
  }, 'search-eventi');
  const oggi = new Date().toISOString().slice(0, 10);
  // Prima gli eventi piu' vicini: se un giro non basta per tutti, a restare
  // indietro dev'essere quello che ha ancora settimane davanti.
  return (d.results || [])
    .filter(e => !coda[e.id] || coda[e.id] <= oggi)
    .sort((a, b) => Date.parse(a.properties.start_datetime) - Date.parse(b.properties.start_datetime));
}

async function membri(lid, cur) {
  let u = `${BASE}/crm/v3/lists/${lid}/memberships?limit=${PAGE}`;
  if (cur) u += '&after=' + encodeURIComponent(cur);
  const d = await json(u, { headers: H }, `membri ${lid}`);
  return { vids: (d.results || []).map(m => m.recordId), next: d.paging?.next?.after || '', total: d.total || 0 };
}

async function esistenti(keys) {
  const s = new Set();
  for (let i = 0; i < keys.length; i += 100) {
    const d = await json(`${BASE}/crm/v3/objects/${TR}/search`, { method: 'POST', headers: H, body: JSON.stringify({
      filterGroups: [{ filters: [{ propertyName: 'dem_v5_dedup_key', operator: 'IN', values: keys.slice(i, i + 100) }] }],
      properties: ['dem_v5_dedup_key'], limit: 100 }) }, 'search-dedup');
    (d.results || []).forEach(x => s.add(x.properties.dem_v5_dedup_key));
    await sleep(260);
  }
  return s;
}

async function crea(inputs) {
  let creati = 0, saltati = 0;
  for (let i = 0; i < inputs.length; i += 100) {
    const pezzo = inputs.slice(i, i + 100);
    const r = await call(`${BASE}/crm/v3/objects/${TR}/batch/create`,
      { method: 'POST', headers: H, body: JSON.stringify({ inputs: pezzo }) }, 'batch-create');
    if (r.status === 201 || r.status === 207) {
      const d = await r.json(); creati += (d.results || []).length; saltati += (d.numErrors || 0);
    } else if (r.status === 409) {
      saltati += pezzo.length;
    } else {
      // un dedup_key gia' preso fa fallire tutto il blocco: si ripiega uno a uno
      // per non perdere i contatti nuovi che ci stavano insieme
      for (const inp of pezzo) {
        const r2 = await call(`${BASE}/crm/v3/objects/${TR}`,
          { method: 'POST', headers: H, body: JSON.stringify(inp) }, 'create-uno');
        if (r2.status === 201) creati++;
        else {
          const t = await r2.text();
          if (r2.status === 409 || /dedup_key/i.test(t)) saltati++;
          else throw new Error(`create ${r2.status} ${t.slice(0, 140)}`);
        }
        await sleep(120);
      }
    }
    await sleep(300);
  }
  return { creati, saltati };
}

async function lavora(e) {
  const id = e.id, q = e.properties;
  const liste = (q.dem_target_list_ids || '').split(',').map(s => s.trim()).filter(Boolean);
  if (!liste.length || !q.start_datetime) {
    await patchEvento(id, { dem_v5_bootstrap_status: 'error',
      dem_v5_bootstrap_log: `[${new Date().toISOString()}] manca la lista o la data di inizio` });
    return;
  }
  const ms = /^\d+$/.test(String(q.start_datetime).trim()) ? Number(q.start_datetime) : Date.parse(q.start_datetime);
  const giorni = (ms - Date.now()) / 86400000;
  const iniziale = giorni <= 14 ? 'send_immediate' : 'pending';
  const d = new Date(ms);
  const fmt = o => new Intl.DateTimeFormat('it-IT', Object.assign({ timeZone: 'Europe/Rome' }, o)).format(d);
  const landing = q.dem_landing_url || q.registration_page || '';

  // il totale serve solo a far vedere a che punto siamo
  let totale = parseInt(q.dem_v5_bootstrap_total, 10) || 0;
  if (!totale) {
    for (const l of liste) { const p = await membri(l, ''); totale += p.total; }
    await patchEvento(id, { dem_v5_bootstrap_total: totale, dem_v5_bootstrap_status: 'in_progress',
      dem_v5_bootstrap_log: `[${new Date().toISOString()}] INIT totale=${totale} liste=${liste.join('|')}` });
  }

  let [idx, cur] = (q.dem_v5_bootstrap_cursor_token || '0|').split('|');
  idx = parseInt(idx, 10) || 0; cur = cur || '';
  let fatti = parseInt(q.dem_v5_bootstrap_cursor, 10) || 0;
  let letti = 0, creati = 0, saltati = 0;

  while (idx < liste.length && letti < CHUNK) {
    const p = await membri(liste[idx], cur);
    cur = p.next; letti += p.vids.length;
    if (p.vids.length) {
      const chiavi = p.vids.map(v => `${id}_${v}`);
      const gia = await esistenti(chiavi);
      saltati += gia.size;
      const nuovi = p.vids.filter(v => !gia.has(`${id}_${v}`));
      if (nuovi.length) {
        const r = await crea(nuovi.map(v => ({
          properties: {
            dem_v5_evento_id: String(id), dem_v5_evento_nome: q.name || '', dem_v5_landing_url: landing,
            dem_v5_start_datetime: q.start_datetime, dem_v5_source: 'bootstrap', dem_v5_status: iniziale,
            dem_v5_evento_data_display: fmt({ weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }),
            dem_v5_evento_orario_display: fmt({ hour: '2-digit', minute: '2-digit', hour12: false }),
            dem_v5_evento_venue: q.venue || '', dem_v5_evento_meeting_link: q.meeting_link || '',
            dem_v5_evento_featured_image: q.featured_image || '', dem_v5_evento_page_body: q.page_body_content || '',
            dem_v5_dedup_key: `${id}_${v}`
          },
          associations: [{ to: { id: String(v) },
            types: [{ associationCategory: 'USER_DEFINED', associationTypeId: 508 }] }]
        })));
        creati += r.creati; saltati += r.saltati;
      }
    }
    if (!cur) { idx += 1; cur = ''; }
    await sleep(200);
  }

  const finito = idx >= liste.length;
  fatti += letti;
  await patchEvento(id, {
    dem_v5_bootstrap_cursor: fatti,
    dem_v5_bootstrap_cursor_token: finito ? '' : `${idx}|${cur}`,
    dem_v5_bootstrap_status: finito ? 'complete' : 'in_progress',
    dem_v5_bootstrap_log: `[${new Date().toISOString()}] fetta letti=${letti} totale=${fatti}/${totale} creati=${creati} saltati=${saltati} stato_iniziale=${iniziale}`.slice(0, 2900)
  });
  console.log(`  ${id} ${q.name}: letti ${letti} (${fatti}/${totale}) creati ${creati} saltati ${saltati} -> ${finito ? 'complete' : 'continua'}`);
}

(async () => {
  if (!PAT) { console.error('HUBSPOT_PAT mancante'); process.exit(1); }
  const ev = await daFare();
  if (!ev.length) { console.log(new Date().toISOString(), 'bootstrap: niente da costruire'); return; }
  console.log(new Date().toISOString(), `bootstrap: ${ev.length} eventi da costruire`);
  for (const e of ev) {
    try { await lavora(e); } catch (err) { console.error(`  !! ${e.id}: ${err.message}`); }
  }
})();
