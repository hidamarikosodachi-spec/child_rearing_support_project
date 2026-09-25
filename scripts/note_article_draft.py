#!/usr/bin/env python3
"""記事 md → note の下書き（本文HTML貼付＋見出し画像）。公開はしない。

`post_note.py`（メール/パスワードでログインし Markdown を生テキストで打鍵）の後継。
`.auth/note_state.json`（`capture_note_session.py` で取得）で認証し、記事本文を HTML に変換して
ProseMirror に paste するので、見出し・太字・箇条書き・リンクが崩れない。

    LD_LIBRARY_PATH=$HOME/.local/opt/libs/extracted/usr/lib/x86_64-linux-gnu \
      .venv/bin/python scripts/note_article_draft.py docs/note/articles/12_series10_lighthouse.md
    # 既存下書きの本文を差し替えるとき（タイトル・見出し画像はそのまま）
    ... scripts/note_article_draft.py <article.md> --key n14b031f094b9
    # 変換結果だけ確認（ブラウザを開かない）
    ... scripts/note_article_draft.py <article.md> --html

公開（タグ入力→「投稿する」）は `note_article_publish.py` 側で行う。

注意:
  - User-Agent を Mac Chrome にしないと editor.note.com → note.com の API が CORS で落ちる（実測）。
  - 本文は「## 記事本文（ここから下を note へ）」直後の `# タイトル` をタイトル欄へ、
    「> **出典」ブロックの手前（=「おわりに」まで）で切る（公開済 06/07 と同じ体裁）。
  - タグは front-matter の `note_tags:`（無ければ `tags:`）の先頭9個。
  - 新マシンでは Chromium の共有ライブラリがユーザー領域にあるため LD_LIBRARY_PATH が必要（.bashrc 参照）。
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUTH = ROOT / ".auth/note_state.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
EDITOR = "div.ProseMirror[contenteditable='true']"
BODY_MARKER = "## 記事本文（ここから下を note へ）"
BODY_END = "\n---\n\n> **出典"


def inline(s: str) -> str:
    s = html.escape(s, quote=False).replace("&lt;&lt;BR&gt;&gt;", "<br>")
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r'(?<!href=")(?<!>)(https?://[^\s<]+)(?![^<]*</a>)', r'<a href="\1">\1</a>', s)
    return s


def md_to_html(md: str) -> str:
    out: list[str] = []
    para: list[str] = []
    mode: str | None = None

    def flush() -> None:
        nonlocal para, mode
        if para:
            if mode == "ul":
                out.append("<ul>" + "".join(f"<li>{inline(x)}</li>" for x in para) + "</ul>")
            elif mode == "ol":
                out.append("<ol>" + "".join(f"<li>{inline(x)}</li>" for x in para) + "</ol>")
            elif mode == "bq":
                out.append("<blockquote><p>" + "<br>".join(inline(x) for x in para) + "</p></blockquote>")
            else:
                out.append("<p>" + "<br>".join(inline(x) for x in para) + "</p>")
        para, mode = [], None

    for line in md.split("\n"):
        if not line.strip():
            flush()
        elif line.startswith("### "):
            flush(); out.append(f"<h3>{inline(line[4:])}</h3>")
        elif line.startswith("## "):
            flush(); out.append(f"<h2>{inline(line[3:])}</h2>")
        elif line.strip() == "---":
            flush(); out.append("<hr>")
        elif line.strip() == ">" or line.startswith("> "):
            if mode != "bq":
                flush(); mode = "bq"
            para.append(line[2:] if line.startswith("> ") else "")
        elif re.match(r"^\d+\. ", line):
            if mode != "ol":
                flush(); mode = "ol"
            para.append(re.sub(r"^\d+\. ", "", line))
        elif line.startswith("- "):
            if mode != "ul":
                flush(); mode = "ul"
            para.append(line[2:])
        elif line.startswith("  ") and mode in ("ul", "ol") and para:
            para[-1] += "<<BR>>" + line.strip()   # format_note_linebreaks の字下げ継続行
        else:
            if mode != "p":
                flush(); mode = "p"
            para.append(line)
    flush()
    return "\n".join(out)


def load(article: Path) -> tuple[str, str, list[str], Path | None]:
    raw = article.read_text(encoding="utf-8")
    fm = raw.split("---", 2)[1]
    body = raw.split(BODY_MARKER, 1)[1]
    m = re.search(r"^# (.+)$", body, re.M)
    if not m:
        sys.exit("本文先頭の `# タイトル` が見つかりません")
    title = m.group(1).strip()
    body = body[m.end():].split("\n## ドラフトメモ")[0].split(BODY_END)[0].rstrip()

    tm = re.search(r"^note_tags: \[(.+)\]$", fm, re.M) or re.search(r"^tags: \[(.+)\]$", fm, re.M)
    tags = [t.strip() for t in tm.group(1).split(",")][:9] if tm else []
    sm = re.search(r"^slug: (.+)$", fm, re.M)
    thumb = ROOT / "assets/thumbnails" / f"{sm.group(1).strip()}.png" if sm else None
    return title, md_to_html(body), tags, (thumb if thumb and thumb.exists() else None)


def main() -> None:
    ap = argparse.ArgumentParser(description="note に記事の下書きを作る（公開はしない）")
    ap.add_argument("article", type=Path)
    ap.add_argument("--key", help="既存 note の key（本文を差し替える）")
    ap.add_argument("--html", action="store_true", help="変換結果だけ表示してブラウザを開かない")
    ap.add_argument("--no-eyecatch", action="store_true")
    a = ap.parse_args()

    title, body_html, tags, thumb = load(a.article)
    print(f"title: {title}\nhtml: {len(body_html)} chars\ntags({len(tags)}): {tags}\nthumb: {thumb}")
    if a.html:
        print(body_html[:800])
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(storage_state=str(AUTH), viewport={"width": 1200, "height": 1000}, user_agent=UA)
        pg = ctx.new_page()
        try:
            url = f"https://editor.note.com/notes/{a.key}/edit/" if a.key else "https://note.com/notes/new"
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(5000)
            if "login" in pg.url:
                sys.exit("note セッション切れ → capture_note_session.py を再実行")

            if not a.key:
                sel = "textarea[placeholder*='タイトル'], [contenteditable='true'][placeholder*='タイトル']"
                pg.wait_for_selector(sel, timeout=20000)
                pg.locator(sel).first.click()
                pg.keyboard.type(title, delay=5)

            ed = pg.locator(EDITOR).first
            ed.click()
            pg.wait_for_timeout(300)
            if a.key:
                pg.keyboard.press("Control+A")
                pg.keyboard.press("Delete")
                pg.wait_for_timeout(500)
            pg.evaluate(
                """([sel, h]) => { const el = document.querySelector(sel); const dt = new DataTransfer();
                dt.setData('text/html', h); dt.setData('text/plain', h.replace(/<[^>]+>/g, ''));
                el.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""",
                [EDITOR, body_html],
            )
            pg.wait_for_timeout(2000)
            print(f"editor: h2={ed.locator('h2').count()} h3={ed.locator('h3').count()} "
                  f"li={ed.locator('li').count()} strong={ed.locator('strong').count()} a={ed.locator('a').count()}")

            pg.get_by_role("button", name="下書き保存").first.click()
            pg.wait_for_timeout(4000)
            key = a.key or next((s for s in pg.url.split("/") if s.startswith("n") and len(s) == 13), None)

            if not a.key and thumb and not a.no_eyecatch:
                pg.locator("button[data-id='ButtonIcon']").first.click()
                pg.wait_for_timeout(1500)
                with pg.expect_file_chooser(timeout=10000) as fc:
                    pg.get_by_role("button", name="画像をアップロード").first.click()
                fc.value.set_files(str(thumb))
                pg.wait_for_timeout(4000)
                pg.get_by_role("button", name="保存").first.click()
                pg.wait_for_timeout(5000)
                pg.get_by_role("button", name="下書き保存").first.click()
                pg.wait_for_timeout(4000)

            d = ctx.request.get(f"https://note.com/api/v3/notes/{key}").json()["data"]
            print(f"key: {key}  status: {d.get('status')}  body: {len(d.get('body') or '')}  "
                  f"eyecatch: {'あり' if d.get('eyecatch') else 'なし'}")
            print(f"編集URL: https://editor.note.com/notes/{key}/edit/")
        finally:
            ctx.storage_state(path=str(AUTH))
            b.close()


if __name__ == "__main__":
    main()
