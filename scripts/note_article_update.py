#!/usr/bin/env python3
"""公開済み note 記事の**タイトルと本文を差し替える**（公開状態のまま更新）。

用途（2026-10-04 オーナー了承）:
  - タイトルから社内用語（「○○タイプの子育て」）を外す
  - 本文の冒頭に診断への導線を入れる
  どちらも公開後に変更できる。元に戻せるので、効かなければ戻す。

    LD_LIBRARY_PATH=... .venv/bin/python scripts/note_article_update.py <article.md> --key nXXXX
    ... --title-only     # 本文はさわらずタイトルだけ直す

注意:
  - 本文を差し替えると note 側の自動ハッシュタグが再生成されることがあるので、更新後に確認する。
  - User-Agent を Mac Chrome にしないと editor.note.com の API が通らない（note_article_draft.py と同じ）。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from note_article_draft import AUTH, EDITOR, UA, load  # noqa: E402


def main() -> None:  # noqa: C901
    ap = argparse.ArgumentParser(description="公開済み note 記事のタイトル・本文を更新する")
    ap.add_argument("article", type=Path)
    ap.add_argument("--key", required=True)
    ap.add_argument("--title-only", action="store_true")
    ap.add_argument("--publish", action="store_true",
                    help="下書きを公開する（オーナーの了承がある時だけ付ける）")
    a = ap.parse_args()

    title, body_html, _tags, _thumb = load(a.article)
    print(f"title: {title}")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(storage_state=str(AUTH), viewport={"width": 1280, "height": 1200}, user_agent=UA)
        pg = ctx.new_page()
        errors: list[str] = []
        pg.on("response", lambda r: errors.append(f"{r.status} {r.text()[:160]}")
              if r.request.method in ("PUT", "POST") and "text_notes" in r.url and r.status >= 400 else None)
        try:
            pg.goto(f"https://editor.note.com/notes/{a.key}/edit/", wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(6000)
            if "login" in pg.url:
                sys.exit("note セッション切れ → capture_note_session.py を再実行")

            sel = "textarea[placeholder*='タイトル'], [contenteditable='true'][placeholder*='タイトル']"
            t = pg.locator(sel).first
            t.click()
            pg.keyboard.press("Control+A")
            pg.keyboard.press("Delete")
            pg.wait_for_timeout(300)
            pg.keyboard.type(title, delay=5)
            pg.wait_for_timeout(500)

            if not a.title_only:
                ed = pg.locator(EDITOR).first
                ed.click()
                pg.keyboard.press("Control+A")
                pg.keyboard.press("Delete")
                pg.wait_for_timeout(500)
                pg.evaluate(
                    """([sel, h]) => { const el = document.querySelector(sel); const dt = new DataTransfer();
                    dt.setData('text/html', h); dt.setData('text/plain', h.replace(/<[^>]+>/g, ''));
                    el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""",
                    [EDITOR, body_html],
                )
                pg.wait_for_timeout(2500)

            # ⚠️ 下書きの記事にこの流れを使うと**公開されてしまう**（2026-10-04 に実際に起こした）。
            #    下書きのままにしたいときは「下書き保存」で止める。
            st = ctx.request.get(f"https://note.com/api/v3/notes/{a.key}").json()["data"].get("status")
            if st != "published" and not a.publish:
                print(f"この記事は {st} です。公開せず下書き保存で止めます（公開するなら --publish）。")
                pg.get_by_role("button", name="下書き保存").first.click()
                pg.wait_for_timeout(5000)
                d = ctx.request.get(f"https://note.com/api/v3/notes/{a.key}").json()["data"]
                print(f"status: {d.get('status')} | title: {d.get('name')}")
                return
            pg.get_by_role("button", name="公開に進む").first.click()
            pg.wait_for_timeout(4000)
            btn = pg.get_by_role("button", name=re.compile("更新する|投稿する")).first
            box = btn.bounding_box()
            pg.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            pg.wait_for_timeout(8000)

            d = ctx.request.get(f"https://note.com/api/v3/notes/{a.key}").json()["data"]
            print(f"status: {d.get('status')} | title: {d.get('name')}")
            print(f"hashtags: {[h.get('hashtag',{}).get('name') for h in (d.get('hashtag_notes') or [])]}")
            for e in errors:
                print("  [API エラー]", e)
        finally:
            ctx.storage_state(path=str(AUTH))
            b.close()


if __name__ == "__main__":
    main()
