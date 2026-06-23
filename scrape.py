#!/usr/bin/env python3
"""용인 장난감도서관 대여가능 현황 스크래퍼.

각 지점(보정/상현/상상의숲)의 '대여가능' 장난감 전체를 수집하고,
직전 실행과 비교해 '신규 대여가능' 델타를 계산한다.
신규 항목과 일부 미캐시 항목은 상세 API로 풀네임/등록일을 보강하여 캐시한다.

산출물:
  data/latest.json      - 리포트/알림용 최종 스냅샷
  data/state.json       - 다음 실행 델타 계산용 직전 상태
  data/name_cache.json  - 상품 상세(풀네임 등) 캐시
  data/history/*.json   - 실행별 요약 이력
"""
import html
import os
import re
import sys

from common import (
    DATA_DIR, Http, ensure_dirs, human_kst, load_config, load_json,
    now_kst, save_json,
)

ITEM_RE = re.compile(
    r"getProduct\('(?P<no>\d+)',\s*'(?P<branch>\d+)'\).*?"
    r"<img[^>]*src='(?P<img>[^']+)'.*?/>\s*<br/>\s*"
    r"(?P<name>.*?)\s*<br>.*?"
    r"<td>(?P<area>.*?)</td>\s*<td>(?P<age>.*?)</td>\s*<td>(?P<count>\d+)</td>",
    re.S,
)


def abs_url(base, src):
    src = src.strip()
    if src.startswith("http"):
        return src
    return base + "/" + src.lstrip("./")


def clean(text):
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def parse_page(html_text, base):
    items = []
    for chunk in html_text.split('class="pd_item"')[1:]:
        m = ITEM_RE.search(chunk)
        if not m:
            continue
        name = clean(m.group("name"))
        items.append({
            "no": m.group("no"),
            "img": abs_url(base, m.group("img")),
            "name_short": name,
            "name": name,            # 캐시에 풀네임 있으면 나중에 덮어씀
            "area": clean(m.group("area")),
            "age": clean(m.group("age")),
            "count": int(m.group("count")),
        })
    return items


def scrape_branch(http, cfg, branch):
    site = cfg["site"]
    base = site["base"]
    url = base + "/main/main.php"
    branch_url = (
        f"{base}/main/main.php?categoryid={site['categoryid']}"
        f"&menuid={branch['menuid']}&groupid={site['groupid']}"
    )
    all_items = []
    seen = set()
    page = 1
    while True:
        data = {
            "no": "", "sch_st": "1", "page": str(page),
            "categoryid": site["categoryid"], "menuid": branch["menuid"],
            "groupid": site["groupid"], "part": "0", "age": "0",
            "st": "1", "delivery_yn": "0", "product_name": "",
        }
        page_items = parse_page(http.post(url, data), base)
        if not page_items:
            break
        new_on_page = 0
        for it in page_items:
            if it["no"] in seen:          # 범위초과 시 1페이지 반복 방지
                continue
            seen.add(it["no"])
            all_items.append(it)
            new_on_page += 1
        if new_on_page == 0:
            break
        page += 1
        if page > 200:                    # 안전장치
            break
    return branch_url, all_items


def enrich(http, cfg, branch, items, cache):
    """신규/미캐시 항목 상세 보강. 신규는 항상, 그 외는 한도 내에서."""
    site = cfg["site"]
    detail_url = site["base"] + "/logic/ajax_getProduct.php"
    enrich_cfg = cfg.get("enrich", {})
    cap = enrich_cfg.get("max_per_run", 200)
    delay = enrich_cfg.get("delay_ms", 120) / 1000.0
    fetched = 0

    def fetch_detail(no):
        d = http.post_json(detail_url, {
            "product_no": no, "data_branch_no": branch["branch_no"],
        }, delay=delay)
        if not d or d.get("json_flag") != "Y":
            return None
        return {
            "name": clean(str(d.get("product_name") or "")),
            "company": clean(str(d.get("product_company") or "")),
            "organ": clean(str(d.get("product_organ") or "")),
            "padate": str(d.get("product_padate") or ""),
            "total": d.get("allTotal"),
            "catename": clean(str(d.get("str_catename2") or "")),
        }

    # 1) 신규 항목은 무조건 보강 (개수 적음)
    for it in items:
        ck = f"{branch['key']}:{it['no']}"
        if it.get("is_new") and ck not in cache:
            det = fetch_detail(it["no"])
            if det:
                cache[ck] = det
                fetched += 1
    # 2) 나머지 미캐시 항목은 한도 내에서 점진적 보강
    for it in items:
        if fetched >= cap:
            break
        ck = f"{branch['key']}:{it['no']}"
        if ck not in cache:
            det = fetch_detail(it["no"])
            if det:
                cache[ck] = det
                fetched += 1
    # 3) 캐시된 풀네임/메타 병합
    for it in items:
        ck = f"{branch['key']}:{it['no']}"
        det = cache.get(ck)
        if det:
            if det.get("name"):
                it["name"] = det["name"]
            it["company"] = det.get("company", "")
            it["padate"] = det.get("padate", "")
            it["organ"] = det.get("organ", "")
            if det.get("catename"):
                it["area"] = it["area"] or det["catename"]
    return fetched


def main():
    ensure_dirs()
    cfg = load_config()
    http = Http(cfg)

    state = load_json(os.path.join(DATA_DIR, "state.json"), {})
    cache = load_json(os.path.join(DATA_DIR, "name_cache.json"), {})
    prev_branches = state.get("branches", {})
    is_baseline = not prev_branches

    now = now_kst()
    out_branches = []
    total_all = 0
    new_all = 0
    new_state = {"branches": {}}

    for branch in sorted(cfg["branches"], key=lambda b: b.get("priority", 99)):
        print(f"[scrape] {branch['name']} 수집 중...", flush=True)
        branch_url, items = scrape_branch(http, cfg, branch)
        prev_avail = set(prev_branches.get(branch["key"], {}).get("available", {}))

        for it in items:
            it["is_new"] = (not is_baseline) and (it["no"] not in prev_avail)

        fetched = enrich(http, cfg, branch, items, cache)
        new_items = [it for it in items if it.get("is_new")]
        # 신규 먼저, 그다음 수량 많은 순 → 이름순
        items.sort(key=lambda it: (not it.get("is_new"), -it["count"], it["name"]))

        print(f"  → {len(items)}개 대여가능, 신규 {len(new_items)}개, 상세보강 {fetched}건",
              flush=True)

        out_branches.append({
            "key": branch["key"], "name": branch["name"],
            "menuid": branch["menuid"], "branch_no": branch["branch_no"],
            "url": branch_url, "total": len(items), "new_count": len(new_items),
            "items": items,
        })
        new_state["branches"][branch["key"]] = {
            "available": {it["no"]: it["count"] for it in items}
        }
        total_all += len(items)
        new_all += len(new_items)

    latest = {
        "generated_at": now.isoformat(),
        "generated_at_human": human_kst(now),
        "is_baseline": is_baseline,
        "totals": {"total": total_all, "new": new_all},
        "branches": out_branches,
    }
    save_json(os.path.join(DATA_DIR, "latest.json"), latest)
    new_state["last_run"] = now.isoformat()
    save_json(os.path.join(DATA_DIR, "state.json"), new_state)
    save_json(os.path.join(DATA_DIR, "name_cache.json"), cache)
    save_json(
        os.path.join(DATA_DIR, "history", now.strftime("%Y%m%d_%H%M") + ".json"),
        {"generated_at": now.isoformat(), "totals": latest["totals"],
         "branches": [{"key": b["key"], "total": b["total"], "new": b["new_count"]}
                      for b in out_branches]},
    )

    msg = "최초 기준선 저장 (신규 표시는 다음 실행부터)" if is_baseline \
        else f"신규 대여가능 {new_all}개"
    print(f"[scrape] 완료: 총 {total_all}개 대여가능, {msg}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
