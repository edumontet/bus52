// Relais Cloudflare Worker pour l'appli Bus 52.
// Il ajoute la clé API PRIM (gardée secrète côté Cloudflare) et autorise l'appli à appeler l'API depuis le navigateur.
// Secret à définir : PRIM_API_KEY   (wrangler secret put PRIM_API_KEY)
// Variable facultative : ALLOWED_ORIGIN (ex. https://edumontet.github.io) pour n'accepter que l'appli.

const PRIM = "https://prim.iledefrance-mobilites.fr/marketplace/";
const ALLOWED_PATHS = new Set(["stop-monitoring", "estimated-timetable"]);

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const allow = env.ALLOWED_ORIGIN ? (origin === env.ALLOWED_ORIGIN ? origin : "null") : "*";
    const cors = {
      "Access-Control-Allow-Origin": allow,
      "Access-Control-Allow-Methods": "GET, OPTIONS",
      "Access-Control-Allow-Headers": "Accept",
      "Access-Control-Max-Age": "86400",
      "Vary": "Origin"
    };
    if (request.method === "OPTIONS") return new Response(null, { headers: cors });
    if (request.method !== "GET") return new Response("Méthode non autorisée", { status: 405, headers: cors });

    const url = new URL(request.url);
    const path = url.pathname.replace(/^\/+|\/+$/g, "");
    if (!ALLOWED_PATHS.has(path)) return new Response("Bus 52 : relais OK", { status: path ? 404 : 200, headers: cors });
    if (!env.PRIM_API_KEY) return new Response("Clé PRIM_API_KEY manquante", { status: 500, headers: cors });

    // Petit cache de 15 s : plusieurs téléphones = une seule requête PRIM (économise le quota)
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), { method: "GET" });
    let res = await cache.match(cacheKey);
    if (!res) {
      const upstream = await fetch(PRIM + path + url.search, {
        headers: { apikey: env.PRIM_API_KEY, Accept: "application/json" }
      });
      res = new Response(upstream.body, upstream);
      res.headers.set("Cache-Control", "public, max-age=15");
      if (upstream.ok) ctx.waitUntil(cache.put(cacheKey, res.clone()));
    }
    const out = new Response(res.body, res);
    for (const [k, v] of Object.entries(cors)) out.headers.set(k, v);
    return out;
  }
};
