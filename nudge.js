const PAT = process.env.HUBSPOT_PAT;
const BASE = "https://api.hubapi.com";
const EV = "2-143900361";
const TR = "2-203372440";
const H = { Authorization: `Bearer ${PAT}`, "Content-Type": "application/json" };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// stati "attivi" da annullare (tutto tranne cancelled/error/send_cancel)
const ACTIVE_STATES = ["pending", "send_immediate", "invito_sent", "pending_t3", "t3_sent", "pending_t1", "t1_sent"];

// fetch con retry/backoff su 429 (limite "al secondo" della Search API) e 5xx.
async function hfetch(url, opts, label, tries = 6) {
  for (let i = 1; i <= tries; i++) {
    let r;
    try {
      r = await fetch(url, opts);
    } catch (e) {
      if (i === tries) throw e;
      await sleep(1000 * i);
      continue;
    }
    if (r.status === 429 || r.status >= 500) {
      const ra = Number(r.headers.get("retry-after"));
      const wait = ra > 0 ? ra * 1000 : Math.min(1000 * 2 ** i, 16000);
      const txt = await r.text().catch(() => "");
      if (i === tries) {
        console.error(`${label} fail definitivo ${r.status} ${txt.slice(0, 200)}`);
        throw new Error(`${label} ${r.status}`);
      }
      console.log(`${label}: ${r.status} (${txt.slice(0, 80)}) -> retry ${i}/${tries} tra ${wait}ms`);
      await sleep(wait);
      continue;
    }
    return r;
  }
}

// === NUDGE BOOTSTRAP (invariato) ===
async function bootstrapNudge() {
  const body = {
    filterGroups: [{ filters: [
      { propertyName: "dem_v5_bootstrap_status", operator: "IN", values: ["ready", "in_progress"] },
      { propertyName: "annullato", operator: "NEQ", value: "true" }
    ]}],
    properties: ["name", "dem_v5_bootstrap_status", "dem_v5_bootstrap_cursor", "dem_v5_bootstrap_total"],
    limit: 100
  };
  const r = await hfetch(`${BASE}/crm/v3/objects/${EV}/search`, { method: "POST", headers: H, body: JSON.stringify(body) }, "search-bootstrap");
  const data = await r.json();
  if (!data.total) { console.log(new Date().toISOString(), "nessun evento in volo"); return; }
  for (const e of data.results) {
    const id = e.id, p = e.properties || {};
    await hfetch(`${BASE}/crm/v3/objects/${EV}/${id}`, { method: "PATCH", headers: H, body: JSON.stringify({ properties: { dem_v5_bootstrap_status: "idle" } }) }, `patch-idle ${id}`);
    await sleep(4000);
    await hfetch(`${BASE}/crm/v3/objects/${EV}/${id}`, { method: "PATCH", headers: H, body: JSON.stringify({ properties: { dem_v5_bootstrap_status: "ready" } }) }, `patch-ready ${id}`);
    console.log(new Date().toISOString(), `nudge ${id} (${p.name}) cursor=${p.dem_v5_bootstrap_cursor}/${p.dem_v5_bootstrap_total}`);
    await sleep(1000);
  }
}

// === CANCEL SWEEP (nuovo): spunta "Annulla e avvisa" -> tracking a send_cancel ===
async function cancelSweep() {
  const body = {
    filterGroups: [{ filters: [
      { propertyName: "dem_annulla_e_avvisa", operator: "EQ", value: "true" },
      { propertyName: "annullato", operator: "NEQ", value: "true" }
    ]}],
    properties: ["name"],
    limit: 100
  };
  const r = await hfetch(`${BASE}/crm/v3/objects/${EV}/search`, { method: "POST", headers: H, body: JSON.stringify(body) }, "search-cancel");
  const data = await r.json();
  if (!data.total) { console.log(new Date().toISOString(), "nessun evento da annullare"); return; }
  for (const e of data.results) {
    const eid = e.id, name = (e.properties || {}).name;
    console.log(new Date().toISOString(), `ANNULLAMENTO evento ${eid} (${name})`);
    // paginazione tracking attivi dell'evento
    let after = null, ids = [], guard = 0;
    do {
      const sb = {
        filterGroups: [{ filters: [
          { propertyName: "dem_v5_evento_id", operator: "EQ", value: eid },
          { propertyName: "dem_v5_status", operator: "IN", values: ACTIVE_STATES }
        ]}],
        properties: ["dem_v5_status"], limit: 100
      };
      if (after) sb.after = after;
      const sr = await hfetch(`${BASE}/crm/v3/objects/${TR}/search`, { method: "POST", headers: H, body: JSON.stringify(sb) }, `search-tracking ${eid}`);
      const sd = await sr.json();
      (sd.results || []).forEach(t => ids.push(t.id));
      after = sd.paging && sd.paging.next ? sd.paging.next.after : null;
      await sleep(350); // rispetta il limite al secondo
    } while (after && ++guard < 500);
    console.log(`  tracking attivi trovati: ${ids.length}`);
    // batch update -> send_cancel
    let done = 0;
    for (let i = 0; i < ids.length; i += 100) {
      const chunk = ids.slice(i, i + 100);
      await hfetch(`${BASE}/crm/v3/objects/${TR}/batch/update`, { method: "POST", headers: H,
        body: JSON.stringify({ inputs: chunk.map(id => ({ id, properties: { dem_v5_status: "send_cancel" } })) }) }, `batch-cancel ${eid}`);
      done += chunk.length;
      await sleep(350);
    }
    console.log(`  -> ${done} tracking a send_cancel`);
    // marca evento annullato (stop nuovi bootstrap + non ri-processare)
    await hfetch(`${BASE}/crm/v3/objects/${EV}/${eid}`, { method: "PATCH", headers: H, body: JSON.stringify({ properties: { annullato: "true" } }) }, `patch-annullato ${eid}`);
    console.log(`  -> evento ${eid} marcato annullato`);
    await sleep(1000);
  }
}

async function main() {
  if (!PAT) { console.error("HUBSPOT_PAT mancante"); process.exit(1); }
  try { await bootstrapNudge(); } catch (e) { console.error("bootstrapNudge err:", e.message); }
  try { await cancelSweep(); } catch (e) { console.error("cancelSweep err:", e.message); }
}
main().catch(e => { console.error(e); process.exit(1); });
