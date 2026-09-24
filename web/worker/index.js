/**
 * 診断の回答を D1 に1行だけ記録する Worker。
 * - 認証なし・個人情報なし。レート制限は Cloudflare 側の設定に任せ、ここでは軽い検証のみ。
 * - 保存に失敗しても、フロントは結果を表示する（体験を壊さない）。
 */
const TYPES = ["lighthouse", "field", "bonfire", "trail", "engawa", "bookshelf", "stream", "meadow"];
const cors = (origin) => ({
  "Access-Control-Allow-Origin": origin || "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
});

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");
    if (request.method === "OPTIONS") return new Response(null, { headers: cors(origin) });
    if (request.method !== "POST") return new Response("Not found", { status: 404 });

    let b;
    try { b = await request.json(); } catch { return json({ ok: false }, 400, origin); }

    // 最低限の検証（不正・巨大データを弾く）
    const type = TYPES.includes(b.type) ? b.type : null;
    const drop = Number.isInteger(b.drop_at) ? b.drop_at : null;
    if (!type && drop === null) return json({ ok: false }, 400, origin);
    const s = (x, n) => (typeof x === "string" ? x.slice(0, n) : null);
    const j = (x, n) => { try { return JSON.stringify(x).slice(0, n); } catch { return null; } };

    try {
      await env.DB.prepare(
        `INSERT INTO responses (v, type, near, axis_i, axis_s, axis_r, answers, age, siblings, worry, drop_at, ref, ua_mobile)
         VALUES (?1,?2,?3,?4,?5,?6,?7,?8,?9,?10,?11,?12,?13)`
      ).bind(
        1, type, j(b.near, 200),
        num(b.axes?.I), num(b.axes?.S), num(b.axes?.R),
        j(b.answers, 2000), j(b.age, 200), s(b.siblings, 20),
        s(b.worry, 200), drop, s(b.ref, 300), b.ua_mobile ? 1 : 0
      ).run();
    } catch (e) {
      return json({ ok: false }, 500, origin);
    }
    return json({ ok: true }, 200, origin);
  },
};
const num = (v) => (typeof v === "number" && isFinite(v) ? Math.round(v * 100) / 100 : null);
const json = (o, status, origin) =>
  new Response(JSON.stringify(o), { status, headers: { "Content-Type": "application/json", ...cors(origin) } });
