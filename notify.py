#!/usr/bin/env python3
"""data/latest.json → 요약 메시지 작성 후 iMessage 발송.

사용:
  python3 notify.py            # 실제 발송
  python3 notify.py --dry-run  # 발송 없이 메시지만 출력
"""
import os
import subprocess
import sys
from datetime import datetime

from common import DATA_DIR, ROOT, load_config, load_json

PLACEHOLDER_HINT = "여기에"


def short_when(iso):
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    ampm = "오전" if dt.hour < 12 else "오후"
    return f"{dt.month}/{dt.day} {ampm}"


def build_message(latest, cfg):
    url = cfg.get("report", {}).get("pages_url", "")
    when = short_when(latest.get("generated_at", ""))
    branches = latest["branches"]  # 우선순위 정렬 유지됨
    totals = latest["totals"]

    lines = [f"📚 용인 장난감도서관 대여가능 현황 ({when})"]
    parts = " / ".join(f"{b['name']} {b['total']}" for b in branches)
    lines.append(f"• {parts}")

    if latest.get("is_baseline"):
        lines.append("• 최초 기준선 저장 — 신규 표시는 다음 보고부터")
    elif totals["new"] > 0:
        nb = [f"{b['name']} {b['new_count']}" for b in branches if b["new_count"] > 0]
        lines.append(f"• 신규 대여가능 {totals['new']}개 ⭐ ({', '.join(nb)})")
    else:
        lines.append("• 신규 대여가능 없음")

    if url:
        lines.append(f"→ {url}")
    return "\n".join(lines)


def send_imessage(recipient, message):
    script = os.path.join(ROOT, "send_imessage.applescript")
    res = subprocess.run(
        ["osascript", script, recipient, message],
        capture_output=True, text=True, timeout=30,
    )
    return res.returncode == 0, (res.stderr or res.stdout).strip()


def main():
    dry = "--dry-run" in sys.argv
    cfg = load_config()
    latest = load_json(os.path.join(DATA_DIR, "latest.json"), None)
    if not latest:
        print("data/latest.json 없음 — 먼저 scrape.py 실행 필요", file=sys.stderr)
        return 1

    message = build_message(latest, cfg)
    print("--- 발송 메시지 ---")
    print(message)
    print("-------------------")

    notify = cfg.get("notify", {})
    recipients = [r for r in notify.get("recipients", []) if PLACEHOLDER_HINT not in r]

    if dry:
        print("[notify] --dry-run: 실제 발송 안 함")
        return 0
    if not recipients:
        print("[notify] 수신자 미설정(config.json notify.recipients) — 발송 생략",
              file=sys.stderr)
        return 0

    fail = 0
    for r in recipients:
        ok, err = send_imessage(r, message)
        if ok:
            print(f"[notify] 발송 성공: {r}")
        else:
            fail += 1
            print(f"[notify] 발송 실패: {r} — {err}", file=sys.stderr)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
