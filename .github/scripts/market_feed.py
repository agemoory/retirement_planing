"""코스피·나스닥·원/달러 환율·미국 10년물 국채금리를 받아 data/market.json으로 저장한다.

- 출처: Yahoo Finance 차트 API (장중이면 최근 시세, 장 마감 후면 종가)
- 일부 항목을 못 받아도 나머지는 갱신하고, 못 받은 항목은 이전 값을 그대로 둔다.
"""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
OUT = "data/market.json"
ITEMS = [
    # id, 이름, 야후 심볼, 단위
    ("kospi", "코스피", "^KS11", "pt"),
    ("nasdaq", "나스닥", "^IXIC", "pt"),
    ("usdkrw", "원/달러", "KRW=X", "krw"),
    ("us10y", "미 10년물", "^TNX", "pct"),
]
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; josung.kr market updater)"}


def fetch(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range=5d&interval=1d"
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            res = data["chart"]["result"][0]
            meta = res["meta"]
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c is not None]
            price = meta.get("regularMarketPrice") or (closes[-1] if closes else None)
            if price is None or len(closes) < 2:
                raise ValueError("not enough data")
            # 마지막 봉이 오늘(진행 중이거나 마감된) 세션이면 그 전날 종가가 기준
            prev = closes[-2]
            t = meta.get("regularMarketTime")
            return {
                "price": round(float(price), 4),
                "prev": round(float(prev), 4),
                "time": datetime.fromtimestamp(t, KST).isoformat() if t else None,
            }
        except (urllib.error.URLError, KeyError, IndexError, TypeError, ValueError) as e:
            print(f"{symbol} attempt {attempt}: {e}")
            time.sleep(5 * attempt)
    return None


def fetch_fear_greed():
    """CNN 공포·탐욕 지수 (비공식 데이터 — 막히거나 형식이 바뀌면 None)."""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed",
        "Origin": "https://edition.cnn.com",
    })
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                fg = json.load(r)["fear_and_greed"]
            score, prev = float(fg["score"]), float(fg.get("previous_close", fg["score"]))
            ts = fg.get("timestamp")
            t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(KST).isoformat() if ts else None
            return {"id": "fg", "name": "공포·탐욕", "unit": "fg", "price": round(score, 1), "prev": round(prev, 1),
                    "change": round(score - prev, 1), "pct": 0, "rating": fg.get("rating", ""), "time": t,
                    "link": "https://edition.cnn.com/markets/fear-and-greed"}
        except (urllib.error.URLError, KeyError, TypeError, ValueError) as e:
            print(f"fear&greed attempt {attempt}: {e}")
            time.sleep(5 * attempt)
    return None


old = {}
if os.path.exists(OUT):
    try:
        with open(OUT, encoding="utf-8") as f:
            old = {i["id"]: i for i in json.load(f).get("items", [])}
    except (ValueError, OSError):
        old = {}

items, got = [], 0
for iid, name, sym, unit in ITEMS:
    q = fetch(sym)
    if q:
        got += 1
        change = q["price"] - q["prev"]
        items.append({
            "id": iid, "name": name, "unit": unit,
            "price": q["price"], "prev": q["prev"],
            "change": round(change, 4),
            "pct": round(change / q["prev"] * 100, 2) if q["prev"] else 0,
            "time": q["time"],
        })
    elif iid in old:
        items.append(old[iid])

fgq = fetch_fear_greed()
if fgq:
    items.append(fgq)
elif "fg" in old:
    items.append(old["fg"])

if got == 0:
    raise SystemExit("could not fetch any quote; keeping the previous file")

os.makedirs("data", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"updated": datetime.now(KST).isoformat(timespec="minutes"), "source": "Yahoo Finance, CNN", "items": items},
              f, ensure_ascii=False, indent=1)
print(f"saved {got}/{len(ITEMS)} quotes")
