"""日本語の改行を「1行だけ読んで意味が通る」位置で入れるユーティリティ。

オーナー指示（2026-09-27）: 単語・文節の途中で折り返さない。画像・note・SNS すべてに適用する。
切る位置の優先順は 句点 → 読点 → 助詞の後ろ → 括弧の外側。
"""
from __future__ import annotations

import re

# 助詞・接続の切れ目（この直後で切ると読みやすい）
PARTICLES = ("ので", "けど", "から", "より", "ため", "のに", "ては", "ても", "でも",
             "には", "とは", "では", "へは", "って", "は", "が", "を", "に", "で",
             "と", "も", "や", "ね", "し")
# 行頭に置いてはいけない文字（禁則）
NO_HEAD = "、。）」』】,.!?！？ー・"


def _break_points(s: str) -> list[int]:
    """切ってよい位置（その位置の直前までで1行にできる index）を優先度つきで返す。"""
    pts: list[tuple[int, int]] = []          # (優先度, 位置) 優先度は小さいほど良い
    for m in re.finditer(r"[。！？]", s):
        pts.append((0, m.end()))
    for m in re.finditer(r"[、，]", s):
        pts.append((1, m.end()))
    for m in re.finditer(r"[／/]", s):          # 対比の区切りは読点と同格
        pts.append((1, m.end()))
    for p in PARTICLES:
        for m in re.finditer(re.escape(p), s):
            end = m.end()
            if end < len(s) and s[end] not in NO_HEAD:
                pts.append((2 + (0 if len(p) > 1 else 1), end))
    for m in re.finditer(r"[）」』】]", s):
        pts.append((4, m.end()))
    return [pos for _, pos in sorted(set(pts))]


def wrap(text: str, width: int = 20) -> str:
    """1行 width 字を目安に、意味の切れ目で改行する。

    既に入っている改行は尊重する（原稿側の意図を壊さない）。
    """
    out: list[str] = []
    for line in text.split("\n"):
        line = line.rstrip()
        if len(line) <= width:
            out.append(line)
            continue
        rest = line
        while len(rest) > width:
            cands = [p for p in _break_points(rest) if 0 < p <= width]
            if not cands:
                # 目安内に切れ目が無ければ、少しはみ出してでも最初の切れ目で切る
                after = [p for p in _break_points(rest) if p > width]
                cut = after[0] if after else width
            else:
                cut = max(cands)      # 目安内でいちばん後ろ＝行を長く使う
                # 残りが極端に短いと「いい」だけの行になって読みづらい。
                # その場合は1つ手前の切れ目に下げる。
                if len(rest) - cut < 5:
                    earlier = [p for p in cands if len(rest) - p >= 5]
                    if earlier:
                        cut = max(earlier)
            out.append(rest[:cut].rstrip())
            rest = rest[cut:].lstrip()
        if rest:
            out.append(rest)
    return "\n".join(out)


def check(text: str, width: int = 20) -> list[str]:
    """width を超える行を返す（目視チェック用）。"""
    return [l for l in text.split("\n") if len(l) > width]
