#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""note記事本文を読みやすい改行に整形する（文字は変えず、改行のみ挿入）。

オーナー指示(2026-06-17): note公開時はモバイルで読みやすいよう改行を調整する。
そのスタイルを記事ファイル側にあらかじめ反映し、コピペで済むようにする。

スタイル:
  - 句点(。！？)ごとに改行。
  - 1文が長い場合は読点(、)でも分割し、1行を短く保つ（既定 25 字超で分割）。
  - 括弧「」（）『』の内側、および **太字** スパンの内側では改行しない
    （マーカーが行をまたいで壊れるのを防ぐ）。
対象範囲:
  「## 記事本文（ここから下を note へ）」〜「出典（軽い参照）」の手前まで。
  見出し(#)・空行・区切り(---)・front-matter・ドラフトメモは触らない。
  リード(> )と箇条書き(- )は接頭辞を保って分割（箇条書きの継続行は2字インデント）。

使い方:
  python3 scripts/format_note_linebreaks.py docs/note/articles/07_series06_montessori.md [...]
  ※ 元に戻すなら git checkout -- <file>。1行あたりの長さは LIMIT で調整。
"""
import sys

OPEN = "「（『"
CLOSE = "」）』"
ENDERS = "。！？!?"
LIMIT = 25   # この長さを超えていれば読点でも改行
HARD = 34    # これを超える行は、助詞の切れ目でさらに分ける（スマホで折り返させない）
# 「1行だけ読んで意味が通る」ようにするため、助詞の後ろを切れ目として使う
# （オーナー指示 2026-09-27・[[feedback-line-breaks]]）
PARTICLES = ("ので", "けど", "から", "より", "ため", "のに", "ては", "ても", "でも",
             "には", "とは", "では", "って", "は", "が", "を", "に", "で", "と", "も")
NO_HEAD = "、。）」』】,.!?！？ー・"


def break_text(s):
    lines, cur, depth, emph = [], "", 0, False
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch == "*" and i + 1 < n and s[i + 1] == "*":  # **太字** トグル
            cur += "**"
            emph = not emph
            i += 2
            continue
        cur += ch
        if ch in OPEN:
            depth += 1
        elif ch in CLOSE:
            depth = max(0, depth - 1)
        if depth == 0 and not emph:
            if ch in ENDERS:
                lines.append(cur)
                cur = ""
            elif ch == "、" and len(cur) >= LIMIT:
                lines.append(cur)
                cur = ""
        i += 1
    if cur:
        lines.append(cur)
    out = []
    for l in lines:
        out.extend(_split_long(l))
    return [l for l in out if l != ""]


def _split_long(line):
    """HARD 字を超える行を、助詞の切れ目で分ける。切れ目が無ければそのまま返す。

    スマホ幅では長い行が自動で折り返り、単語の途中で切れて読みづらくなるため。
    """
    if len(line) <= HARD or "](http" in line:   # リンク記法は途中で切らない
        return [line]

    def in_emph(pos, text):
        """pos が **太字** の内側かどうか（内側では切らない）。"""
        spans, start = [], 0
        while True:
            a = text.find("**", start)
            if a < 0:
                break
            b = text.find("**", a + 2)
            if b < 0:
                break
            spans.append((a, b + 2))
            start = b + 2
        return any(a < pos < b for a, b in spans)
    res, rest = [], line
    while len(rest) > HARD:
        cuts = []
        for p in PARTICLES:
            start = 0
            while True:
                i = rest.find(p, start)
                if i < 0 or i + len(p) > HARD:
                    break
                end = i + len(p)
                if (end < len(rest) and rest[end] not in NO_HEAD and end >= 8
                        and not in_emph(end, rest)):
                    cuts.append(end)
                start = i + 1
        if not cuts:
            break
        cut = max(cuts)
        if len(rest) - cut < 5:                # 「いい」だけの行を作らない
            earlier = [c for c in cuts if len(rest) - c >= 5]
            if not earlier:
                break
            cut = max(earlier)
        res.append(rest[:cut])
        rest = rest[cut:]
    if rest:
        res.append(rest)
    return res


def process_body_line(line):
    if line.strip() == "" or line.strip() == "---" or line.lstrip().startswith("#"):
        return [line]
    if line.startswith("> "):
        parts = break_text(line[2:])
        return ["> " + parts[0]] + ["> " + p for p in parts[1:]]
    if line.startswith("- "):
        parts = break_text(line[2:])
        return ["- " + parts[0]] + ["  " + p for p in parts[1:]]
    return break_text(line)


def main(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    out, in_body = [], False
    for line in lines:
        if line.strip() == "## 記事本文（ここから下を note へ）":
            in_body = True
            out.append(line)
            continue
        if in_body and "出典（軽い参照）" in line:
            in_body = False
        out.extend(process_body_line(line) if in_body else [line])
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print(f"{path}: {len(lines)} -> {len(out)} 行")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: python3 scripts/format_note_linebreaks.py <article.md> [...]")
    for p in sys.argv[1:]:
        main(p)
