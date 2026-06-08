const PAT = process.env.HUBSPOT_PAT;
const BASE = "https://api.hubapi.com";
const EV = "2-143900361";
const H = { Authorization: `Bearer ${PAT}`, "Content-Type": "application/json" };
const sleep = (ms) => new Promise(r => setTimeout(r, ms));
async function main() {
  if (!PAT) { console.error("HUBSPOT_PAT mancante"); process.exit(1); }
  const body = { filterGroups:[{ filters:[
    { propertyName:"dem_v5_bootstrap_status", operator:"IN", values:["ready","in_progress"] },
    { propertyName:"annullato", operator:"NEQ", value:"true" } ]}],
    properties:["name","dem_v5_bootstrap_status","dem_v5_bootstrap_cursor","dem_v5_bootstrap_total"], limit:100 };
  const r = await fetch(`${BASE}/crm/v3/objects/${EV}/search`, { method:"POST", headers:H, body:JSON.stringify(body) });
  if (!r.ok) { console.error("search fail", r.status, await r.text()); process.exit(1); }
  const data = await r.json();
  if (!data.total) { console.log(new Date().toISOString(), "nessun evento in volo"); return; }
  for (const e of data.results) {
    const id = e.id, p = e.properties || {};
    await fetch(`${BASE}/crm/v3/objects/${EV}/${id}`, { method:"PATCH", headers:H, body:JSON.stringify({ properties:{ dem_v5_bootstrap_status:"idle" } }) });
    await sleep(4000);
    await fetch(`${BASE}/crm/v3/objects/${EV}/${id}`, { method:"PATCH", headers:H, body:JSON.stringify({ properties:{ dem_v5_bootstrap_status:"ready" } }) });
    console.log(new Date().toISOString(), `nudge ${id} (${p.name}) cursor=${p.dem_v5_bootstrap_cursor}/${p.dem_v5_bootstrap_total}`);
  }
}
main().catch(e => { console.error(e); process.exit(1); });
