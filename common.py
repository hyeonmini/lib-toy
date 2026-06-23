"""공통 유틸: 설정 로드, HTTP(요청 throttle/재시도), 경로, 시간."""
import json
import os
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
LOG_DIR = os.path.join(ROOT, "logs")

KST = timezone(timedelta(hours=9))

_WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]


def now_kst():
    return datetime.now(KST)


def human_kst(dt=None):
    dt = dt or now_kst()
    ampm = "오전" if dt.hour < 12 else "오후"
    h12 = dt.hour % 12
    if h12 == 0:
        h12 = 12
    wd = _WEEKDAYS[dt.weekday()]
    return f"{dt.year}년 {dt.month}월 {dt.day}일 ({wd}) {ampm} {h12}:{dt.minute:02d}"


def load_config():
    path = os.path.join(ROOT, "config.json")
    if not os.path.exists(path):
        path = os.path.join(ROOT, "config.example.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def ensure_dirs():
    for d in (DATA_DIR, DOCS_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Http:
    def __init__(self, cfg):
        r = cfg.get("request", {})
        self.delay = r.get("delay_ms", 300) / 1000.0
        self.timeout = r.get("timeout_s", 20)
        self.retries = r.get("retries", 3)
        self.ua = r.get("user_agent", "Mozilla/5.0")
        self._last = 0.0

    def _throttle(self, delay):
        wait = delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

    def post(self, url, data, delay=None):
        body = urllib.parse.urlencode(data).encode("utf-8")
        last_err = None
        for attempt in range(self.retries):
            self._throttle(self.delay if delay is None else delay)
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "User-Agent": self.ua,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Accept": "*/*",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read().decode("utf-8", "replace")
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = e
                time.sleep(0.6 * (attempt + 1))
        raise RuntimeError(f"POST 실패 {url}: {last_err}")

    def post_json(self, url, data, delay=None):
        txt = self.post(url, data, delay=delay)
        try:
            return json.loads(txt)
        except json.JSONDecodeError:
            return None
