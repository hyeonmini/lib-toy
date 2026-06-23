#!/bin/bash
# launchd 스케줄 설치: 매일 09:00, 15:00 에 run.sh 실행.
# 스크립트 위치를 기준으로 plist를 생성하므로 어디에 두든 동작.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.libtoy.report"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
# launchd 자신이 여는 stdout/stderr는 항상 접근 가능한 내장 디스크에 둔다
# (외장 볼륨이면 launchd가 파일을 못 열어 EX_CONFIG로 실패).
LOGDIR="$HOME/Library/Logs/libtoy"

mkdir -p "$HOME/Library/LaunchAgents" "$DIR/logs" "$LOGDIR"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${DIR}/run.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${DIR}</string>
    <key>StartCalendarInterval</key>
    <array>
        <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
        <dict><key>Hour</key><integer>15</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>StandardOutPath</key>
    <string>${LOGDIR}/launchd.out.log</string>
    <key>StandardErrorPath</key>
    <string>${LOGDIR}/launchd.err.log</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
EOF

echo "plist 생성: $PLIST"

# 재설치 대비 기존 잡 제거 후 로드
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load -w "$PLIST"

echo "launchd 등록 완료. 등록된 잡 확인:"
launchctl list | grep "$LABEL" || echo "(목록에서 못 찾음 — 위 오류 확인)"
echo
echo "매일 09:00, 15:00 에 실행됩니다."
echo "지금 즉시 테스트: launchctl start ${LABEL}"
echo "해제: launchctl unload ${PLIST} && rm ${PLIST}"
