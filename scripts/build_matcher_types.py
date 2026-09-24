#!/usr/bin/env python3
"""docs/matcher/type_results_v1.md（正本） → web/matcher/types.js を生成する。

タイプ文の二重管理（Markdown とサイトの JS）を避けるためのビルド。
文書を直して本スクリプトを実行し、生成された types.js をデプロイする。

    python3 scripts/build_matcher_types.py          # 生成
    python3 scripts/build_matcher_types.py --check  # 生成せず差分だけ確認（CI 的な用途）

書式（type_results_v1.md）:
    ## <key> <タイプ名>
    - 軸: 導く・整える・寄り添う
    - 一行: 先に光を置いて、そばにいる
    - 理論: <名前> | <説明> | <note の記事キー（無ければ空）>
    ### どんな風景か / 大事にしていること / 強み / つまずきやすいところ /
    ### 気持ちが楽になるかもしれない見方（- 箇条書き） / 明日、ひとつだけ試すなら / ちがう風景の人と育てるとき
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/matcher/type_results_v1.md"
DST = ROOT / "web/matcher/types.js"
ORDER = ["lighthouse", "field", "bonfire", "trail", "engawa", "bookshelf", "stream", "meadow"]
SECTIONS = {
    "どんな風景か": "intro",
    "大事にしていること": "value",
    "強み": "strength",
    "つまずきやすいところ": "stumble",
    "気持ちが楽になるかもしれない見方": "ease",      # 箇条書き → 配列
    "明日、ひとつだけ試すなら": "tomorrow",
    "ちがう風景の人と育てるとき": "withOthers",
}
NOTE_URL = "https://note.com/hidamari_sodachi/n/"


def strip_md(s: str) -> str:
    """サイト側は装飾を持たないので ** ** を外す（意味は文で担保している）。"""
    return re.sub(r"\*\*(.+?)\*\*", r"\1", s).strip()


def parse() -> tuple[str, dict]:
    text = SRC.read_text(encoding="utf-8")
    m = re.search(r"<!-- disclaimer -->\n(.+?)\n", text)
    if not m:
        sys.exit("エラー: <!-- disclaimer --> が見つかりません")
    disclaimer = m.group(1).strip()

    types: dict[str, dict] = {}
    # "## key 名前" で分割（前書きの ## は key が ORDER に無いので弾かれる）
    for block in re.split(r"\n## ", text)[1:]:
        head, _, body = block.partition("\n")
        parts = head.split()
        if len(parts) < 2 or parts[0] not in ORDER:
            continue
        key, name = parts[0], parts[1]
        # label = 表示名（「灯台タイプ」）。name は内部向けの短い名前。
        t: dict = {"key": key, "name": name, "label": f"{name}タイプ", "theories": []}

        for line in body.split("\n"):
            if line.startswith("- 軸: "):
                t["axes"] = line[5:].strip()
            elif line.startswith("- 一行: "):
                t["lead"] = line[6:].strip()
            elif line.startswith("- 理論: "):
                cols = [c.strip() for c in line[6:].split("|")]
                t["theories"].append({
                    "t": cols[0],
                    "d": cols[1] if len(cols) > 1 else "",
                    "url": NOTE_URL + cols[2] if len(cols) > 2 and cols[2] else None,
                })

        for jp, field in SECTIONS.items():
            m = re.search(rf"^### {re.escape(jp)}\n(.+?)(?=\n### |\n---|\Z)", body, re.S | re.M)
            if not m:
                sys.exit(f"エラー: {key} に「### {jp}」がありません")
            chunk = m.group(1).strip()
            if field == "ease":
                items = [strip_md(l[2:]) for l in chunk.split("\n") if l.startswith("- ")]
                if not items:
                    sys.exit(f"エラー: {key} の「{jp}」が箇条書きになっていません")
                t[field] = items
            else:
                t[field] = strip_md(" ".join(l.strip() for l in chunk.split("\n") if l.strip()))

        missing = [k for k in ("axes", "lead") if k not in t]
        if missing:
            sys.exit(f"エラー: {key} に {missing} がありません")
        if not t["theories"]:
            sys.exit(f"エラー: {key} に「- 理論:」がありません")
        types[key] = t

    missing = [k for k in ORDER if k not in types]
    if missing:
        sys.exit(f"エラー: タイプが足りません: {missing}")
    return disclaimer, types


def render(disclaimer: str, types: dict) -> str:
    body = ",\n".join(
        f"  {k}: " + json.dumps(types[k], ensure_ascii=False, indent=2).replace("\n", "\n  ")
        for k in ORDER
    )
    return f"""// 自動生成ファイル — 直接編集しないこと。
// 正本: docs/matcher/type_results_v1.md
// 生成: python3 scripts/build_matcher_types.py
export const DISCLAIMER = {json.dumps(disclaimer, ensure_ascii=False)};

export const TYPES = {{
{body}
}};

// 3軸の極性 → タイプ（+ = 導く / 整える / 寄り添う）
export const TYPE_MAP = {{
  "+++": "lighthouse", "++-": "field", "+-+": "bonfire", "+--": "trail",
  "-++": "engawa", "-+-": "bookshelf", "--+": "stream", "---": "meadow",
}};

export const TYPE_ORDER = {json.dumps(ORDER, ensure_ascii=False)};
"""


def main() -> None:
    disclaimer, types = parse()
    out = render(disclaimer, types)
    if "--check" in sys.argv:
        cur = DST.read_text(encoding="utf-8") if DST.exists() else ""
        print("差分なし" if cur == out else "⚠ 差分あり（build_matcher_types.py を実行してください）")
        sys.exit(0 if cur == out else 1)
    DST.write_text(out, encoding="utf-8")
    print(f"[OK] {DST.relative_to(ROOT)} を生成（{len(types)}タイプ）")
    for k in ORDER:
        t = types[k]
        print(f"  {k:10s} {t['name']:4s} 楽になる見方{len(t['ease'])}件 理論{len(t['theories'])}件")


if __name__ == "__main__":
    main()
