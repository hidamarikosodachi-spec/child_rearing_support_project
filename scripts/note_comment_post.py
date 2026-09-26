"""note コメント＋スキ投稿（ガードレール付き・dry-run 既定）。

note コメント自動化（オーナー決裁 2026-06-17）の第3部品＝**書き込み**。保存済み
セッションを使い、個別生成された誠実コメントを投稿し、必要ならスキ（♥）も押す。

⚠️ 不可逆リスク（BAN＝全web資産喪失/ブランド毀損）の本丸。CEO は option3 を
非推奨と明言したが、オーナーがリスク承知で決裁・実行。よって**ガードレール必須**:
  - 個別生成（テンプレ禁止）       … 起案はドラフトJSONに人/Claudeが1件ずつ用意
  - レート制限                     … 自分の記事≤5/日・他者≤3/日（log で日次集計）
  - 投稿間隔ランダム               … 複数投稿時は数分のランダム待ち
  - storage_state 認証             … 毎回ログインしない
  - 全操作ログ + kill-switch       … .auth/note_comment_log.jsonl / .auth/STOP_COMMENTS
  - 段階展開                       … 自分返信で機構検証 → 他者へ拡張
  - dry-run 既定                   … --commit 無しは一切書き込まない（ブラウザも開かない）
  - 初回は --headed 推奨           … note の投稿UIはセレクター追従が要るため目視

入力: docs/drafts/note_comments/YYYY-MM-DD.json （配列）
  各要素: {url, author, title, comment, like(bool), approved(bool), reply_to(任意=返信先コメント本文の一部)}
  ※ approved:true のものだけ投稿対象（オーナー最終承認ゲート）。

使い方:
    python3 scripts/note_comment_post.py --date 2026-06-17            # dry-run（既定）
    python3 scripts/note_comment_post.py --date 2026-06-17 --commit --headed   # 実投稿（目視）
    touch .auth/STOP_COMMENTS    # 緊急停止（kill-switch）
"""
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".auth" / "note_state.json"
LOG_PATH = PROJECT_ROOT / ".auth" / "note_comment_log.jsonl"
STOP_FILE = PROJECT_ROOT / ".auth" / "STOP_COMMENTS"
DRAFTS_DIR = PROJECT_ROOT / "docs" / "drafts" / "note_comments"
MY_URLNAME = "hidamari_sodachi"

OWN_DAILY_MAX = 5      # 自分の記事への返信 上限/日
OTHER_DAILY_MAX = 3    # 他者記事への接触コメント 上限/日
MIN_GAP_SEC = 90       # 複数投稿の最小間隔（ランダム下限）
MAX_GAP_SEC = 210      # 同 上限

COMMENT_TEXTAREA = "textarea[placeholder*='コメント']"


def _require_session() -> None:
    if not AUTH_PATH.exists():
        raise click.ClickException(
            f"ログインセッションがありません: {AUTH_PATH}\n"
            "先に `python3 scripts/capture_note_session.py` を実行してください。"
        )


def _today() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")


def _is_own(url: str) -> bool:
    return f"note.com/{MY_URLNAME}/" in url


def _load_drafts(date: str) -> list[dict[str, Any]]:
    path = DRAFTS_DIR / f"{date}.json"
    if not path.exists():
        raise click.ClickException(f"ドラフトがありません: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _today_counts() -> dict[str, int]:
    """log から本日分の投稿数を own/other 別に集計。"""
    counts = {"own": 0, "other": 0}
    if not LOG_PATH.exists():
        return counts
    today = _today()
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        # verified が False/未設定の古い記録は数えない（未投稿なのに枠を食うため）
        if (rec.get("date") == today and rec.get("action") == "comment"
                and rec.get("ok") and rec.get("verified")):
            counts["own" if rec.get("own") else "other"] += 1
    return counts


def _log(rec: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": datetime.now(timezone.utc).astimezone().isoformat(), "date": _today(), **rec}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


SELF_URLNAME = "hidamari_sodachi"


def _comment_text(node: Any) -> str:
    """note のコメントはリッチテキストの木。{type:'text', value:...} を再帰で拾う。"""
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("value", ""))
        return "".join(_comment_text(c) for c in (node.get("children") or []))
    return ""


def _verify_posted(ctx, url: str, comment: str) -> bool:
    """投稿が実際に反映されたかを API で確認する。

    送信ボタンを押せても POST が失敗していることがあり（2026-09-26 に実際に発生し、
    2件が「成功」と記録されたまま未投稿だった）、クリックの成否を成功とみなしてはいけない。
    """
    key = url.rstrip("/").split("/")[-1]
    head = comment.strip().split("\n")[0][:12]
    try:
        r = ctx.request.get(
            f"https://note.com/api/v3/notes/{key}/note_comments?per_page=20&order=newest"
        )
        for c in r.json().get("data", []):
            if (c.get("user") or {}).get("urlname") != SELF_URLNAME:
                continue
            if head and head in _comment_text(c.get("comment")):
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _post_one(page, entry: dict[str, Any], own: bool, ctx=None) -> dict[str, Any]:
    """1記事にコメント（＋スキ）を実際に投稿する。--commit 時のみ呼ぶ。"""
    url, comment = entry["url"], entry["comment"]
    page.goto(url, wait_until="networkidle", timeout=45000)
    for _ in range(8):  # コメント欄を描画させる
        page.mouse.wheel(0, 2200)
        page.wait_for_timeout(900)

    # reply_to があれば「特定コメントへのスレッド返信」（自分の記事での返信用・2026-09-13）。
    # 該当コメント本文の一部（reply_to）でコメントブロックを特定 → その「返信」ボタン →
    # ブロック内に開く textarea / 送信ボタンを使う（ルート投稿欄とは別物）。
    scope = page
    reply_to = (entry.get("reply_to") or "").strip()
    if reply_to:
        block = page.get_by_text(reply_to, exact=False).first.locator(
            "xpath=ancestor::div[contains(@class,'min-w-0')][1]"
        )
        block.wait_for(state="visible", timeout=20000)
        block.locator("button[aria-label='返信']").first.click()
        page.wait_for_timeout(1500)
        scope = block

    ta = scope.locator(COMMENT_TEXTAREA).last if reply_to else page.locator(COMMENT_TEXTAREA).first
    ta.wait_for(state="visible", timeout=20000)
    ta.scroll_into_view_if_needed()
    page.wait_for_timeout(500)
    ta.click()
    ta.fill(comment)  # fill は改行（\n）を保持し、Enter誤送信もしない
    page.wait_for_timeout(1500)

    # 送信ボタン（入力後に出現・テキスト無しの aria-label='送信' アイコンボタン）。
    # note UI 変更時は要追従＝初回 --headed 推奨。
    # 送信ボタンは aria-label='送信' のアイコンボタンだけを対象にする。
    # 以前は :has-text('投稿する') を OR で並べていたため、DOM 上で先に現れる
    # note ヘッダーの「投稿」ボタンを .first が掴み、コメントが送信されていなかった（2026-09-26）。
    submit = scope.locator("button[aria-label='送信']").first
    submit.wait_for(state="visible", timeout=10000)
    submit.click()
    page.wait_for_timeout(3500)

    # 反映確認（クリックできた＝投稿できた、ではない）。1度だけ再送を試す。
    verified = _verify_posted(ctx, url, comment) if ctx is not None else None
    if verified is False:
        click.echo("   [warn] 反映を確認できず。1度だけ再送します。")
        ta = page.locator(COMMENT_TEXTAREA).first
        ta.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        ta.click()
        ta.fill(comment)
        page.wait_for_timeout(1500)
        page.locator("button[aria-label='送信']").first.click()
        page.wait_for_timeout(4000)
        verified = _verify_posted(ctx, url, comment)
    if verified is False:
        raise RuntimeError("コメントが反映されませんでした（送信は押せたが未反映）")

    liked = False
    if entry.get("like"):
        try:
            like_btn = page.locator("button[aria-label='スキ']").first
            like_btn.click()
            page.wait_for_timeout(1500)
            liked = True
        except Exception as exc:  # noqa: BLE001
            click.echo(f"   [warn] スキ失敗: {exc}", err=True)

    return {"url": url, "own": own, "liked": liked}


@click.command(help="note にコメント＋スキを投稿する（ガードレール付き・--commit 無しは dry-run）。")
@click.option("--date", required=True, help="ドラフト日付（YYYY-MM-DD）")
@click.option("--commit", is_flag=True, help="付けると実投稿。無しは dry-run（ブラウザも開かない）。")
@click.option("--headed", is_flag=True, help="ブラウザ表示モード（初回の目視確認に推奨）。")
def main(date: str, commit: bool, headed: bool) -> None:
    _require_session()

    if STOP_FILE.exists():
        raise click.ClickException(f"kill-switch 作動中: {STOP_FILE} を消すまで投稿しません。")

    drafts = _load_drafts(date)
    approved = [d for d in drafts if d.get("approved")]
    counts = _today_counts()

    click.echo(f"=== note コメント投稿 {'[実投稿]' if commit else '[DRY-RUN]'} date={date} ===")
    click.echo(f"ドラフト {len(drafts)}件 / approved {len(approved)}件")
    click.echo(f"本日の投稿実績: 自分={counts['own']}/{OWN_DAILY_MAX}  他者={counts['other']}/{OTHER_DAILY_MAX}")

    if not approved:
        click.echo("\napproved:true のコメントがありません。")
        click.echo("→ docs/drafts/note_comments/ の該当ファイルで、投稿してよいものを approved:true に。")
        return

    # レート制限を見越したキュー作成
    queue: list[dict[str, Any]] = []
    sim = dict(counts)
    for d in approved:
        own = _is_own(d["url"])
        cap = OWN_DAILY_MAX if own else OTHER_DAILY_MAX
        key = "own" if own else "other"
        blocked = sim[key] >= cap
        queue.append({"entry": d, "own": own, "blocked": blocked})
        if not blocked:
            sim[key] += 1

    for i, q in enumerate(queue, 1):
        d, own = q["entry"], q["own"]
        tag = "自分の記事" if own else "他者記事"
        click.echo(f"\n[{i}/{len(queue)}] {tag}  @{d.get('author')}  like={d.get('like')}")
        click.echo(f"    {d['url']}")
        if q["blocked"]:
            click.echo(f"    ⛔ レート上限({tag})に達しているため本日はスキップ")
            continue
        # 整形プレビュー（改行・余白そのまま）
        click.echo("    --- コメント本文 ---")
        for line in d["comment"].split("\n"):
            click.echo(f"    | {line}")

    if not commit:
        click.echo("\n[DRY-RUN] 実際の投稿・スキはしていません。")
        click.echo("実行: 上記でよければ --commit --headed を付けて再実行（初回は目視推奨）。")
        return

    # --- 実投稿 ---
    from playwright.sync_api import sync_playwright

    to_post = [q for q in queue if not q["blocked"]]
    posted = 0
    with sync_playwright() as p:
        b = p.chromium.launch(headless=not headed)
        ctx = b.new_context(
            storage_state=str(AUTH_PATH),
            viewport={"width": 1280, "height": 1000},
            # UA を付けないと投稿 POST が通らない（送信ボタンは押せるのに未反映になる。2026-09-26 に判明）
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        for i, q in enumerate(to_post, 1):
            d, own = q["entry"], q["own"]
            if STOP_FILE.exists():
                click.echo("kill-switch 検出。中断します。")
                break
            click.echo(f"\n[{i}/{len(to_post)}] 投稿中 @{d.get('author')} ...")
            try:
                r = _post_one(page, d, own, ctx=ctx)
                _log({"action": "comment", "ok": True, "verified": True, **r})
                posted += 1
                click.echo(f"   [OK] コメント投稿{'＋スキ' if r['liked'] else ''}")
            except Exception as exc:  # noqa: BLE001
                _log({"action": "comment", "ok": False, "url": d["url"], "own": own, "error": str(exc)})
                click.echo(f"   [FAIL] {exc}", err=True)
            # 次があればランダム待ち（bot閾値下を走る）
            if i < len(to_post):
                gap = random.uniform(MIN_GAP_SEC, MAX_GAP_SEC)
                click.echo(f"   …次まで {int(gap)} 秒待機")
                time.sleep(gap)
        b.close()

    click.echo(f"\n完了: {posted}/{len(to_post)} 件投稿")


if __name__ == "__main__":
    main()
