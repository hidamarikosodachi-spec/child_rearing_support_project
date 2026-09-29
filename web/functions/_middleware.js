/**
 * 旧URL（*.pages.dev）から独自ドメインへ 301 リダイレクトする。
 *
 * note の告知記事・Threads の投稿・Instagram のプロフィールに
 * `hidamari-kosodachi.pages.dev` のURLを配ってしまっているため、
 * それらを死なせないために必要。SEO 上も評価を新ドメインへ集約できる。
 *
 * - 本番の pages.dev ホストだけを対象にする（プレビュー用の <hash>.pages.dev は素通し＝検証のため）
 * - POST（/api/response）はリダイレクトすると本文が失われるので GET/HEAD のみ
 */
const OLD_HOST = "hidamari-kosodachi.pages.dev";
const NEW_ORIGIN = "https://hidamari-kosodachi.com";

export async function onRequest(context) {
  const { request, next } = context;
  const url = new URL(request.url);
  if (url.hostname === OLD_HOST && (request.method === "GET" || request.method === "HEAD")) {
    return Response.redirect(NEW_ORIGIN + url.pathname + url.search, 301);
  }
  return next();
}
