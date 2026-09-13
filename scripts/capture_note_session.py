"""note ログインセッション取得（storage_state・一度だけ手動実行）。

note は公式 API が無くブラウザ自動化で操作する。毎回の資格情報ログインは
bot 検知・アカウントロックの誘発要因になるため、**一度だけ手動でログインして
セッション（cookie / localStorage）を storage_state として保存**し、以降の
コメント読み取り/投稿ツールはこれを使い回す（＝自動ログインしない）。

使い方（自分の WSL ターミナルから実行推奨。WSLg で headed ブラウザが出る）:
    python3 scripts/capture_note_session.py
    → 開いたブラウザで note にログイン（2段階認証も最後まで）
    → ログインが終わったら、このターミナルに戻って Enter を押す
      → .auth/note_state.json に保存（cookie 内容も診断表示する）

判定方針（重要）: 旧版は「URL が /login でない＝ログイン済み」で判定していたが、
note はログイン後も URL が変わらない場合があり誤検知していた。本版は
**Enter による手動確定**を主とし、URL には一切依存しない。Enter が使えない
実行環境（stdin 無し）では cookie 検知での自動保存にフォールバックする。
"""
from __future__ import annotations

import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTH_PATH = PROJECT_ROOT / ".auth" / "note_state.json"
START_URL = "https://note.com/login"
POLL_DEADLINE_SEC = 600


def _note_cookies(context):
    return [c for c in context.cookies() if "note.com" in c.get("domain", "")]


def _looks_logged_in(context):
    """note の API が認証を通すか実際に叩いて判定する。

    cookie 名だけの判定は不可（未ログインでも `_note_session_v5` 等の httpOnly
    cookie が置かれるため、2026-09-13 に誤検知→未ログイン state 保存の事故あり）。
    """
    try:
        r = context.request.get("https://note.com/api/v1/stats/pv?filter=all&page=1&sort=pv", timeout=15000)
        body = r.json()
    except Exception:  # noqa: BLE001  ネットワーク断・JSON でない等
        return False
    return r.ok and "data" in body and body.get("error", {}).get("code") != "auth"


def _save(context) -> None:
    context.storage_state(path=str(AUTH_PATH))
    cookies = _note_cookies(context)
    names = ", ".join(sorted(c.get("name", "?") for c in cookies)) or "(なし)"
    print(f"[OK] セッションを保存しました: {AUTH_PATH}", flush=True)
    print(f"     note.com cookie {len(cookies)} 件: {names}", flush=True)
    print(f"     認証 cookie 検知: {_looks_logged_in(context)}", flush=True)
    if not _looks_logged_in(context):
        print("     [注意] 認証 cookie が見当たりません。ログイン未完なら再実行してください。", flush=True)
    print("※ 機密。.gitignore 済み・コミット/共有しないこと。", flush=True)


def main() -> None:
    from playwright.sync_api import sync_playwright

    AUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        # Google ログイン（note は Google 連携）は自動操作ブラウザを弾くので、
        # 自動化の目印（navigator.webdriver / --enable-automation）を外して起動する。
        browser = p.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
            locale="ja-JP",
        )
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
        page = context.new_page()
        page.goto(START_URL)

        print("=" * 64, flush=True)
        print("開いたブラウザで note にログインしてください（2段階認証も最後まで）。", flush=True)
        print("ログインが終わったら、このターミナルに戻って Enter を押すと保存します。", flush=True)
        print("=" * 64, flush=True)

        try:
            input()  # 主: Enter で確定（ターミナル実行）
        except (EOFError, KeyboardInterrupt):
            # 副: stdin が無い実行環境 → cookie 検知で自動保存
            print("(stdin なし → cookie 検知の自動待機にフォールバック)", flush=True)
            waited = 0
            while waited < POLL_DEADLINE_SEC:
                time.sleep(5)
                waited += 5
                try:
                    cur, logged, ncook = page.url, _looks_logged_in(context), len(_note_cookies(context))
                except Exception as exc:  # noqa: BLE001  ブラウザを閉じられた等
                    print(f"[NG] ブラウザが閉じられました: {exc}", flush=True)
                    browser.close()
                    return
                print(f"  [{waited:>3}s] URL: {cur} / note.com cookie={ncook} / logged_in={logged}", flush=True)
                if logged:
                    time.sleep(3)  # cookie 確定待ち
                    _save(context)
                    break
            else:
                print(f"[NG] {POLL_DEADLINE_SEC}秒以内にログインを検知できませんでした。", flush=True)
            context.close()
            browser.close()
            return

        _save(context)
        context.close()
        browser.close()


if __name__ == "__main__":
    main()
