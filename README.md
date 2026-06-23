# 용인 장난감도서관 대여가능 알리미

용인시육아종합지원센터 장난감도서관(보정점·상현점·상상의숲점)의 **대여가능 장난감**을
하루 2번(오전 9시·오후 3시) 자동 수집하여,

- 전체 목록을 정리한 **웹페이지**(GitHub Pages)를 갱신하고
- **iMessage**로 요약 + 링크를 부부에게 발송

하는 파이프라인.

## 구성

| 파일 | 역할 |
|---|---|
| `scrape.py` | 3개 지점 대여가능 전체 수집, 직전 대비 **신규** 델타 계산, 상세(풀네임/등록일) 보강·캐시 |
| `build_report.py` | `data/latest.json` → `docs/index.html` (모바일 웹페이지, 검색·필터·신규강조) |
| `notify.py` | 요약 메시지 작성 후 iMessage 발송 (`send_imessage.applescript` 사용) |
| `run.sh` | 파이프라인: 수집 → 리포트 → GitHub Pages push → iMessage |
| `install.sh` | launchd 스케줄(09:00/15:00) 등록 |
| `common.py` | 설정 로드·HTTP·시간 유틸 |
| `config.json` | 수신자·옵션 (개인정보 포함, **git 제외**) |

## 데이터 흐름

```
yicare.or.kr  ──scrape──▶ data/latest.json ──build──▶ docs/index.html ──push──▶ GitHub Pages
                              │                                                      │
                              └────────────────── notify ──▶ iMessage(요약+링크) ◀──┘
```

- 수집 기준: 각 지점 `대여가능(st=1)` 필터, 전체 페이지 순회.
- **신규**: 직전 실행에 없던(=새로 대여가능해진) 상품. 최초 실행은 기준선만 저장.
- 상세 보강: 신규 항목은 매번, 그 외 미캐시 항목은 회당 한도(`config.enrich.max_per_run`) 내에서
  점진적으로 풀네임을 채움(캐시 누적).

## 설정 (`config.json`)

`config.example.json`을 복사해 만든다. **수신자 번호를 채워야 발송됨.**

```jsonc
"notify": {
  "channel": "imessage",
  "recipients": ["+821012345678", "+821087654321"]  // 나, 아내
}
```

## 설치

```bash
cp config.example.json config.json   # 수신자 번호 입력
./install.sh                          # launchd 등록 (09:00, 15:00)
launchctl start com.libtoy.report     # 즉시 1회 실행 테스트
```

### iMessage 권한 (중요)

첫 발송 시 macOS가 **Messages 제어 권한**(자동화)을 물어보면 허용해야 한다.
- 사전 준비: `Messages.app` 실행 + iMessage 로그인 상태.
- 권한 거부/실패 시: 시스템 설정 → 개인정보 보호 및 보안 → 자동화 →
  터미널(또는 osascript)에 **메시지** 허용.

### 스케줄 동작/제약

- launchd `StartCalendarInterval` 사용. Mac이 해당 시각에 **켜져 있어야** 실행됨
  (잠자기였다면 깨어날 때 1회 보정 실행).
- 이 프로젝트는 외장 SSD(`/Volumes/DEV_SSD/prj/lib-toy`)에 설치됨 →
  **해당 시각에 SSD가 연결돼 있어야** 동작. 미연결 시 그 회차는 누락.

## 수동 실행

```bash
python3 scrape.py            # 수집만
python3 build_report.py      # 리포트 HTML만
python3 notify.py --dry-run  # 메시지 미리보기(발송 안 함)
./run.sh                     # 전체 파이프라인 1회
```

## 산출물 / 로그

- 웹페이지: `docs/index.html` → GitHub Pages URL (`config.report.pages_url`)
- 상태/캐시: `data/state.json`, `data/name_cache.json`, `data/history/`
- 로그: `logs/run_*.log`, `logs/launchd.{out,err}.log`

데이터 출처: 용인시육아종합지원센터 yicare.or.kr (개인 가족용 자동 알림).
