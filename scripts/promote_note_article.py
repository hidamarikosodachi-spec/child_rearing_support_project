#!/usr/bin/env python3
"""note 記事を公開したら、Instagram 用の告知素材を作る（オーナー指示 2026-10-01）。

やること:
  1. ストーリー画像（1080x1920・記事タイトル入り）を生成
  2. スマホから保存できるよう、サイトの `/ig/stories/<slug>.png` に置く
  3. ストーリーに貼るリンク（note の公開URL）と、投稿手順を表示

なぜストーリーが主役か:
  - Instagram は**フィード投稿の本文にリンクを置けない**。踏めるのはストーリーのリンクスタンプだけ
  - そのリンクスタンプは **API では貼れない**ため、ストーリー投稿だけはオーナーの手作業（1分）
  - 一方、**宣伝色の強い単独投稿はリーチが落ちる**（Threads 実測で通常の1/10）。
    フィードに出すなら「記事の中身をカルーセル化」して、告知は最後に一言だけにする

    .venv/bin/python scripts/promote_note_article.py docs/note/articles/14_series12_stream.md
    .venv/bin/python scripts/promote_note_article.py --all-recent 3
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "docs/note/articles"
STORIES = ROOT / "assets/stories"
WEB_STORIES = ROOT / "web/ig/stories"
SITE = "https://hidamari-kosodachi.com"


def meta_of(path: Path) -> dict:
    fm = path.read_text(encoding="utf-8").split("---", 2)[1]
    out = {}
    for line in fm.splitlines():
        if ":" in line and not line.startswith(" "):
            k, v = line.split(":", 1)
            out[k.strip()] = v.split("#")[0].strip().strip('"')
    return out


def build(path: Path) -> dict | None:
    m = meta_of(path)
    if m.get("status") != "published":
        click.echo(f"  skip（未公開）: {path.name}")
        return None
    slug = m["slug"]
    out = STORIES / f"{slug}.png"
    r = subprocess.run(
        [str(ROOT / ".venv/bin/python"), str(ROOT / "scripts/instagram_story.py"),
         "--article", str(path), "--out", str(out),
         "--cta", "note で公開しました"],
        capture_output=True, text=True)
    if r.returncode != 0:
        click.echo(f"  [FAIL] 画像生成: {r.stderr[-200:]}")
        return None
    WEB_STORIES.mkdir(parents=True, exist_ok=True)
    shutil.copy(out, WEB_STORIES / f"{slug}.png")
    return {"slug": slug, "title": m.get("title", "").strip('"'),
            "url": m.get("published_url", ""), "image": f"{SITE}/ig/stories/{slug}.png"}


@click.command(help="公開済みの note 記事から Instagram ストーリー用の素材を作る。")
@click.argument("article", type=click.Path(exists=True, path_type=Path), required=False)
@click.option("--all-recent", type=int, default=0, help="直近N本の公開記事をまとめて処理")
def main(article: Path | None, all_recent: int) -> None:
    targets: list[Path] = []
    if article:
        targets = [article]
    elif all_recent:
        pub = [p for p in ARTICLES.glob("*.md") if meta_of(p).get("status") == "published"]
        pub.sort(key=lambda p: meta_of(p).get("published", ""), reverse=True)
        targets = pub[:all_recent]
    else:
        raise click.ClickException("記事を指定するか --all-recent N を付けてください")

    made = [x for x in (build(p) for p in targets) if x]
    if not made:
        return
    click.echo(f"\n=== Instagram ストーリー素材 {len(made)}件 ===")
    for x in made:
        click.echo(f"\n■ {x['title']}")
        click.echo(f"  画像（スマホで長押し保存）: {x['image']}")
        click.echo(f"  リンクスタンプに貼るURL  : {x['url']}")
    click.echo("""
--- 投稿手順（1件あたり1分）---
1. 上の画像URLをスマホで開いて保存
2. Instagram → ストーリーズ → その画像を選ぶ
3. スタンプ → リンク → 上の note のURLを貼る
4. シェア
※ 画像をサイトに置いたので、公開するには web をデプロイする:
   cd web && npx wrangler pages deploy . --project-name hidamari-kosodachi --commit-dirty=true
""")


if __name__ == "__main__":
    main()
