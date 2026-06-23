#!/usr/bin/env python3
"""data/latest.json → docs/index.html (모바일 우선, 자체 완결형 단일 페이지)."""
import json
import os
import sys

from common import DATA_DIR, DOCS_DIR, ensure_dirs, load_config, load_json

PAGE_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>__TITLE__</title>
<style>
  :root { --bg:#f5f6f8; --card:#fff; --line:#e6e8ec; --muted:#7a828c;
          --accent:#e8590c; --new:#fff4e6; --newline:#ffa94d; --ok:#2b8a3e; }
  * { box-sizing:border-box; -webkit-tap-highlight-color:transparent; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",
         "Malgun Gothic",sans-serif; background:var(--bg); color:#212529; }
  a { color:inherit; text-decoration:none; }
  header { position:sticky; top:0; z-index:20; background:#fff;
           border-bottom:1px solid var(--line); padding:12px 14px 0; }
  h1 { font-size:17px; margin:0 0 2px; }
  .sub { font-size:12px; color:var(--muted); margin-bottom:10px; }
  .tabs { display:flex; gap:6px; overflow-x:auto; padding-bottom:0; }
  .tab { flex:0 0 auto; padding:9px 12px; border:1px solid var(--line);
         border-bottom:none; border-radius:10px 10px 0 0; background:#fafbfc;
         font-size:13px; font-weight:600; color:var(--muted); cursor:pointer;
         white-space:nowrap; }
  .tab .cnt { font-weight:700; }
  .tab .nb { display:inline-block; min-width:16px; padding:0 5px; margin-left:4px;
             font-size:11px; line-height:16px; border-radius:8px;
             background:var(--accent); color:#fff; }
  .tab.active { background:#fff; color:var(--accent); border-color:var(--line);
                box-shadow:0 -2px 0 var(--accent) inset; }
  .controls { display:flex; gap:8px; padding:10px 14px; flex-wrap:wrap;
              background:#fff; border-bottom:1px solid var(--line);
              position:sticky; top:0; z-index:10; }
  .controls input, .controls select { font-size:14px; padding:9px 10px;
              border:1px solid var(--line); border-radius:9px; background:#fff; }
  .controls input[type=search] { flex:1 1 100%; }
  .controls select { flex:1 1 auto; }
  .chk { display:flex; align-items:center; gap:6px; font-size:13px;
         font-weight:600; color:var(--accent); padding:0 4px; }
  .meta { padding:8px 14px 0; font-size:12px; color:var(--muted); }
  .grid { display:grid; grid-template-columns:repeat(2,1fr); gap:10px;
          padding:10px 14px 40px; }
  @media(min-width:560px){ .grid{ grid-template-columns:repeat(3,1fr);} }
  @media(min-width:820px){ .grid{ grid-template-columns:repeat(4,1fr);} }
  @media(min-width:1080px){ .grid{ grid-template-columns:repeat(5,1fr);} }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px;
          overflow:hidden; display:flex; flex-direction:column; }
  .card.new { background:var(--new); border-color:var(--newline); }
  .thumb { width:100%; aspect-ratio:3/4; object-fit:cover; background:#eef0f3;
           display:block; }
  .body { padding:8px 9px 10px; display:flex; flex-direction:column; gap:5px; flex:1; }
  .name { font-size:13px; font-weight:600; line-height:1.3;
          display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical;
          overflow:hidden; }
  .tags { display:flex; flex-wrap:wrap; gap:4px; margin-top:auto; }
  .tag { font-size:11px; color:var(--muted); background:#f1f3f5;
         border-radius:6px; padding:2px 6px; }
  .qty { font-size:11px; font-weight:700; color:var(--ok);
         background:#ebfbee; border-radius:6px; padding:2px 6px; }
  .badge { font-size:10px; font-weight:700; color:#fff; background:var(--accent);
           border-radius:6px; padding:2px 6px; align-self:flex-start; }
  .empty { text-align:center; color:var(--muted); padding:60px 20px; }
  footer { text-align:center; font-size:11px; color:var(--muted); padding:20px; }
</style>
</head>
<body>
<header>
  <h1>__TITLE__</h1>
  <div class="sub" id="sub"></div>
  <div class="tabs" id="tabs"></div>
</header>
<div class="controls">
  <input type="search" id="q" placeholder="장난감 이름 검색…" autocomplete="off">
  <select id="area"><option value="">전체 분류</option></select>
  <select id="age"><option value="">전체 연령</option></select>
  <select id="sort">
    <option value="default">정렬: 신규·수량순</option>
    <option value="name">정렬: 이름순</option>
    <option value="qty">정렬: 수량 많은순</option>
  </select>
  <label class="chk"><input type="checkbox" id="newonly"> 신규만</label>
</div>
<div class="meta" id="count"></div>
<div class="grid" id="grid"></div>
<footer>용인시육아종합지원센터 장난감도서관 · 데이터 출처: yicare.or.kr<br>
자동 수집 리포트 · 대여가능(현장) 기준</footer>

<script>
const DATA = __DATA__;
let cur = DATA.branches[0].key;

const $ = s => document.querySelector(s);
const tabsEl = $('#tabs'), gridEl = $('#grid');

function branchByKey(k){ return DATA.branches.find(b=>b.key===k); }

function renderTabs(){
  tabsEl.innerHTML = '';
  DATA.branches.forEach(b=>{
    const t = document.createElement('div');
    t.className = 'tab' + (b.key===cur?' active':'');
    t.innerHTML = `${b.name} <span class="cnt">${b.total}</span>` +
      (b.new_count>0 ? `<span class="nb">+${b.new_count}</span>` : '');
    t.onclick = ()=>{ cur=b.key; renderTabs(); fillFilters(); render(); };
    tabsEl.appendChild(t);
  });
}

function fillFilters(){
  const b = branchByKey(cur);
  const areas=[...new Set(b.items.map(i=>i.area).filter(Boolean))].sort();
  const ages=[...new Set(b.items.map(i=>i.age).filter(Boolean))].sort();
  const a=$('#area'), g=$('#age');
  a.innerHTML='<option value="">전체 분류</option>'+areas.map(x=>`<option>${x}</option>`).join('');
  g.innerHTML='<option value="">전체 연령</option>'+ages.map(x=>`<option>${x}</option>`).join('');
}

function render(){
  const b = branchByKey(cur);
  const q=$('#q').value.trim().toLowerCase();
  const fa=$('#area').value, fg=$('#age').value;
  const newonly=$('#newonly').checked, sort=$('#sort').value;
  let items = b.items.filter(i=>
    (!q || i.name.toLowerCase().includes(q)) &&
    (!fa || i.area===fa) && (!fg || i.age===fg) &&
    (!newonly || i.is_new));
  if(sort==='name') items=[...items].sort((x,y)=>x.name.localeCompare(y.name,'ko'));
  else if(sort==='qty') items=[...items].sort((x,y)=>y.count-x.count);

  $('#count').textContent =
    `${b.name} · ${items.length}개 표시` +
    (b.new_count>0?` · 신규 ${b.items.filter(i=>i.is_new).length}개 ⭐`:'');

  if(!items.length){ gridEl.innerHTML='<div class="empty">조건에 맞는 장난감이 없어요.</div>'; return; }
  gridEl.innerHTML = items.map(i=>`
    <a class="card${i.is_new?' new':''}" href="${b.url}" target="_blank" rel="noopener">
      <img class="thumb" loading="lazy" src="${i.img}" alt="" onerror="this.style.visibility='hidden'">
      <div class="body">
        ${i.is_new?'<span class="badge">신규 ⭐</span>':''}
        <div class="name">${escapeHtml(i.name)}</div>
        <div class="tags">
          ${i.area?`<span class="tag">${i.area}</span>`:''}
          ${i.age?`<span class="tag">${i.age}</span>`:''}
          <span class="qty">대여가능 ${i.count}</span>
        </div>
      </div>
    </a>`).join('');
}

function escapeHtml(s){ return s.replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

$('#sub').textContent = `${DATA.generated_at_human} 기준 · 전체 ${DATA.totals.total}개 대여가능` +
  (DATA.totals.new>0?` · 신규 ${DATA.totals.new}개 ⭐`:'');
$('#q').addEventListener('input', render);
['area','age','sort','newonly'].forEach(id=> $('#'+id).addEventListener('change', render));
renderTabs(); fillFilters(); render();
</script>
</body>
</html>
"""


def build():
    ensure_dirs()
    cfg = load_config()
    latest = load_json(os.path.join(DATA_DIR, "latest.json"), None)
    if not latest:
        print("data/latest.json 없음 — 먼저 scrape.py 실행 필요", file=sys.stderr)
        return 1

    # 페이지에 필요한 필드만 추림 (용량 최소화)
    slim = {
        "generated_at_human": latest["generated_at_human"],
        "totals": latest["totals"],
        "branches": [{
            "key": b["key"], "name": b["name"], "url": b["url"],
            "total": b["total"], "new_count": b["new_count"],
            "items": [{
                "name": it["name"], "img": it["img"], "area": it["area"],
                "age": it["age"], "count": it["count"],
                "is_new": bool(it.get("is_new")),
            } for it in b["items"]],
        } for b in latest["branches"]],
    }
    title = cfg.get("report", {}).get("title", "장난감도서관 대여가능 현황")
    htmls = (PAGE_TEMPLATE
             .replace("__TITLE__", title)
             .replace("__DATA__", json.dumps(slim, ensure_ascii=False)))
    out = os.path.join(DOCS_DIR, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(htmls)
    print(f"[report] {out} 생성 ({len(htmls)//1024}KB, "
          f"총 {latest['totals']['total']}개 / 신규 {latest['totals']['new']}개)")
    return 0


if __name__ == "__main__":
    sys.exit(build())
