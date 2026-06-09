const PAT = process.env.HUBSPOT_PAT;
const BASE = "https://api.hubapi.com";
const EV = "2-143900361";
const H = { Authorization: `Bearer ${PAT}`, "Content-Type": "application/json" };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

// fetch con retry/backoff su 429 (limite "al secondo" della Search API) e 5xx.
// Rispetta Retry-After se presente; backoff esponenziale altrimenti.
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

async function main() {
  if (!PAT) { console.error("HUBSPOT_PAT mancante"); process.exit(1); }
  const body = {
    filterGroups: [{ filters: [
      { propertyName: "dem_v5_bootstrap_status", operator: "IN", values: ["ready", "in_progress"] },
      { propertyName: "annullato", operator: "NEQ", value: "true" }
    ]}],
    properties: ["name", "dem_v5_bootstrap_status", "dem_v5_bootstrap_cursor", "dem_v5_bootstrap_total"],
    limit: 100
  };
  const r = await hfetch(`${BASE}/crm/v3/objects/${EV}/search`, { method: "POST", headers: H, body: JSON.stringify(body) }, "search");
  if (!r.ok) { console.error("search fail", r.status, await r.text()); process.exit(1); }
  const data = await r.json();
  if (!data.total) { console.log(new Date().toISOString(), "nessun evento in volo"); return; }
  for (const e of data.results) {
    const id = e.id, p = e.properties || {};
    await hfetch(`${BASE}/crm/v3/objects/${EV}/${id}`, { method: "PATCH", headers: H, body: JSON.stringify({ properties: { dem_v5_bootstrap_status: "idle" } }) }, `patch-idle ${id}`);
    await sleep(4000);
    await hfetch(`${BASE}/crm/v3/objects/${EV}/${id}`, { method: "PATCH", headers: H, body: JSON.stringify({ properties: { dem_v5_bootstrap_status: "ready" } }) }, `patch-ready ${id}`);
    console.log(new Date().toISOString(), `nudge ${id} (${p.name}) cursor=${p.dem_v5_bootstrap_cursor}/${p.dem_v5_bootstrap_total}`);
    await sleep(1000); // respiro tra eventi: non saturare il limite al secondo
  }
}
main().catch(e => { console.error(e); process.exit(1); });
