#!/usr/bin/env python3
"""**接触した相手からの返信**を確認する（read-only）。

抜けていた視点（オーナー指摘 2026-10-07）:
  `note_comments_read.py` は**自分の記事**に付いたコメントしか見ていなかった。
  誠実接触は他人の記事にコメントする活動なので、**そこに付いた相手の返信**を
  見ていないと、関係づくりが一方通行で終わる。

    .venv/bin/python scripts/note_outreach_replies.py           # 返信が来ているものだけ
    .venv/bin/python scripts/note_outreach_replies.py --all     # 接触した全記事
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

import click

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / ".auth" / "note_comment_log.jsonl"
ME = "hidamari_sodachi"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _text(node) -> str:
    """note のコメント本文（リッチテキストの入れ子）を平文にする。

    本文は `comment` キー配下の入れ子（root → element → text）。
    `children` を直接見ても取れない（2026-10-07 に空文字で気づいた）。
    """
    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("value", "")
        if "comment" in node and isinstance(node["comment"], dict):
            return _text(node["comment"])
        return "".join(_text(c) for c in (node.get("children") or []))
    if isinstance(node, list):
        return "".join(_text(c) for c in node)
    return ""


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def _comments(key: str) -> list[dict]:
    return _get(f"https://note.com/api/v3/notes/{key}/note_comments"
                "?per_page=50&page=1&order=newest")["data"]


def _replies(note_key: str, comment_key: str) -> list[dict]:
    """あるコメントへの返信（スレッド）。`parent_key` を付けると取れる。

    返信は親コメントの中に入っていないので、これを呼ばないと本文が読めない
    （2026-10-07・オーナー指摘で判明）。
    """
    return _get(f"https://note.com/api/v3/notes/{note_key}/note_comments"
                f"?page=1&per_page=20&order=oldest&parent_key={comment_key}")["data"]


@click.command(help="接触した記事で、相手から返信が来ているものを一覧する。")
@click.option("--all", "show_all", is_flag=True, help="返信が無いものも表示")
def main(show_all: bool) -> None:
    seen, targets = set(), []
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(line)
            except Exception:  # noqa: BLE001
                continue
            if r.get("action") == "comment" and r.get("ok") and r.get("url") and r["url"] not in seen:
                seen.add(r["url"])
                targets.append((r["ts"][:10], r["url"]))

    need = 0
    for ts, url in targets:
        m = re.search(r"/n/(n[0-9a-zA-Z]+)", url)
        if not m or f"/{ME}/" in url:
            continue
        try:
            cs = _comments(m.group(1))
        except Exception as e:  # noqa: BLE001
            click.echo(f"  [取得失敗] {url} {e}")
            continue
        cs.sort(key=lambda c: c.get("created_at", ""))
        mine = [c for c in cs if (c.get("user") or {}).get("urlname") == ME]
        if not mine:
            click.echo(f"⚠️ 自分のコメントが見当たらない: {url}")
            continue
        my = mine[-1]
        # note は「作者が返信したか」「作者がスキしたか」をコメントごとに持っている。
        replied = bool(my.get("is_creator_replied"))
        to_me = [c for c in cs
                 if (c.get("to_user") or {}).get("urlname") == ME
                 and (c.get("user") or {}).get("urlname") != ME]
        liked = bool(my.get("is_creator_liked"))
        if replied or to_me:
            # スレッドの最後の発言が自分なら返信済み。相手で終わっていれば要返信
            # （2026-10-15: 自分の返信を表示していなかったため、返したかどうか判別できなかった）
            thread = []
            if replied:
                try:
                    thread = _replies(m.group(1), my.get("key", ""))
                except Exception as e:  # noqa: BLE001
                    click.echo(f"   （返信の取得に失敗: {e}）")
            last = sorted(thread + to_me, key=lambda c: c.get("created_at", ""))
            done = bool(last) and (last[-1].get("user") or {}).get("urlname") == ME
            # 相手の最後の発言が短いお礼だけなら、会話は閉じている（2026-10-17・返し続けると不自然）
            tail = _text(last[-1]) if last and not done else ""
            closing = bool(tail) and len(tail) <= 60 and any(w in tail for w in ("ありがとう", "嬉しい", "うれしい"))
            if (done or closing) and not show_all:
                continue
            need += 0 if (done or closing) else 1
            mark = "✅ 返信済" if done else ("💬 締めのお礼（返信不要）" if closing else "🔴 要返信")
            click.echo(f"\n{mark}（{ts} 接触） {url}")
            click.echo(f"   自分: {_text(my)[:70]}")
            for c in (to_me or []):
                u = (c.get("user") or {}).get("urlname")
                click.echo(f"   @{u}: {_text(c)[:140]}")
            for rep in thread:
                u = (rep.get("user") or {}).get("urlname")
                click.echo(f"   ↩ @{u}{'（自分）' if u == ME else ''}: {_text(rep)[:160]} [key={rep.get('key')}]")
        elif show_all:
            mark = "♥作者がスキ" if liked else "—"
            click.echo(f"・返信なし {mark}（{ts}） {url}")
    click.echo(f"\n接触 {len(targets)}件 / 要返信 {need}件（返信済みは --all で表示）")


if __name__ == "__main__":
    main()
