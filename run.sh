#!/bin/bash
# 파이프라인: 스크래핑 → 리포트 생성 → GitHub Pages push → iMessage 발송
# launchd/cron에서 호출됨. 스크립트 위치를 기준으로 동작(설치 위치 무관).
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

# Homebrew 등 경로 보강 (launchd 최소 환경 대비)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
PYTHON="$(command -v python3)"
GIT="$(command -v git)"

mkdir -p logs
TS="$(date +%Y%m%d_%H%M%S)"
LOG="logs/run_${TS}.log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== 파이프라인 시작 ==="

# 1) 스크래핑 (+ 델타 + 상세보강)
if ! "$PYTHON" scrape.py >>"$LOG" 2>&1; then
  log "스크래핑 실패 — 중단"; exit 1
fi

# 2) 리포트 HTML 생성
if ! "$PYTHON" build_report.py >>"$LOG" 2>&1; then
  log "리포트 생성 실패 — 중단"; exit 1
fi

# 3) GitHub Pages 배포 (docs 변경분만)
if [ -d .git ]; then
  "$GIT" add docs >>"$LOG" 2>&1
  if ! "$GIT" diff --cached --quiet; then
    "$GIT" commit -m "report: ${TS}" >>"$LOG" 2>&1
    if "$GIT" push >>"$LOG" 2>&1; then
      log "GitHub Pages 배포 완료"
    else
      log "git push 실패 (네트워크/인증 확인) — 알림은 계속"
    fi
  else
    log "리포트 변경 없음 — push 생략"
  fi
else
  log "git 저장소 아님 — 배포 생략"
fi

# 4) iMessage 발송
if ! "$PYTHON" notify.py >>"$LOG" 2>&1; then
  log "알림 발송 일부 실패 (로그 확인)"
fi

log "=== 파이프라인 종료 ==="
# 오래된 로그 정리 (최근 60개 유지)
ls -1t logs/run_*.log 2>/dev/null | tail -n +61 | xargs rm -f 2>/dev/null
exit 0
