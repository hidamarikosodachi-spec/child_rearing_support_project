/**
 * GET /go/<noteキー>?s=ig — note 記事へ転送し、クリックを1行だけ記録する。
 *
 * 目的（オーナー指示 2026-10-18「Instagram は note 記事への最大限の導線に」）:
 *   note の統計では流入元が分からないため、Instagram（プロフィールのリンク → /note/）から
 *   何人が note へ移ったかを、ここで数える。
 * - 転送先は自分の note 記事だけ（キーの形を検証。任意URLへは飛ばさない＝オープンリダイレクトにしない）
 * - 個人情報は取らない（IP・Cookie なし）
 * - 記録に失敗しても転送は必ず行う（読者の体験を壊さない）
 */
const NOTE = "https://note.com/hidamari_sodachi/n/";

export async function onRequestGet({ params, request, env, waitUntil }) {
  const key = String(params.key || "");
  if (!/^n[0-9a-f]{12}$/.test(key)) {
    return Response.redirect("https://hidamari-kosodachi.com/note/", 302);
  }
  const url = new URL(request.url);
  const src = (url.searchParams.get("s") || "").replace(/[^a-z0-9_-]/gi, "").slice(0, 20) || null;
  const mobile = /Mobi|Android|iPhone/i.test(request.headers.get("User-Agent") || "") ? 1 : 0;
  try {
    waitUntil(env.DB.prepare("INSERT INTO clicks (note_key, src, ua_mobile) VALUES (?1, ?2, ?3)")
      .bind(key, src, mobile).run().catch(() => {}));
  } catch { /* 記録できなくても転送する */ }
  return Response.redirect(NOTE + key, 302);
}
