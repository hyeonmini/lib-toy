#!/usr/bin/env python3
"""기존 latest.json의 모든 항목을 상세 API로 1회 보강(설명·제조사·구성·등록일·풀네임).

델타(is_new) 등 상태는 건드리지 않고 표시 데이터/캐시만 채운다.
캐시에 100건마다 저장하므로, 중간에 끊겨도 재실행하면 남은 것만 이어서 보강한다.
"""
import os
import sys

from common import DATA_DIR, Http, load_config, load_json, save_json
from scrape import fetch_detail, merge_detail


def main():
    cfg = load_config()
    http = Http(cfg)
    latest = load_json(os.path.join(DATA_DIR, "latest.json"), None)
    if not latest:
        print("latest.json 없음 — 먼저 스크래핑 필요", file=sys.stderr)
        return 1
    cache = load_json(os.path.join(DATA_DIR, "name_cache.json"), {})
    branch_by_key = {b["key"]: b for b in cfg["branches"]}
    delay = cfg.get("enrich", {}).get("delay_ms", 120) / 1000.0

    total = sum(len(b["items"]) for b in latest["branches"])
    done = fetched = failed = 0
    print(f"[backfill] 대상 {total}개 (캐시 {len(cache)}건 보유)", flush=True)

    for b in latest["branches"]:
        branch = branch_by_key.get(b["key"])
        if not branch:
            continue
        for it in b["items"]:
            done += 1
            ck = f"{b['key']}:{it['no']}"
            det = cache.get(ck)
            if det is None or "memo" not in det:
                det = fetch_detail(http, cfg, branch, it["no"], delay)
                if det:
                    cache[ck] = det
                    fetched += 1
                else:
                    failed += 1
            merge_detail(it, cache.get(ck))
            if done % 100 == 0:
                save_json(os.path.join(DATA_DIR, "name_cache.json"), cache)
                print(f"  {done}/{total} (신규보강 {fetched}, 실패 {failed})", flush=True)

    save_json(os.path.join(DATA_DIR, "latest.json"), latest)
    save_json(os.path.join(DATA_DIR, "name_cache.json"), cache)
    print(f"[backfill] 완료 {done}/{total} · 신규보강 {fetched} · 실패 {failed} "
          f"· 캐시 {len(cache)}건", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
