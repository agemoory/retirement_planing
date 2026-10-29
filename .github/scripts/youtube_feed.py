"""채널 RSS에서 최신 영상 목록을 받아 data/videos.json으로 저장한다."""
import json
import os
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

CHANNEL_ID = "UCj6xeOFJopNMWaW1J7c9bAw"
FEED = f"https://www.youtube.com/feeds/videos.xml?channel_id={CHANNEL_ID}"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015", "media": "http://search.yahoo.com/mrss/"}

req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 josung.kr feed updater"})
body = None
for attempt in range(1, 6):
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
        break
    except urllib.error.URLError as e:
        print(f"attempt {attempt}: {e}")
        time.sleep(10 * attempt)
if body is None:
    raise SystemExit("could not fetch the feed; keeping the previous list")
root = ET.fromstring(body)

videos = []
for e in root.findall("a:entry", NS):
    vid = e.findtext("yt:videoId", default="", namespaces=NS)
    if not vid:
        continue
    link = e.find("a:link", NS)
    href = link.get("href", "") if link is not None else ""
    videos.append({
        "id": vid,
        "title": e.findtext("a:title", default="", namespaces=NS),
        "published": e.findtext("a:published", default="", namespaces=NS),
        "short": "/shorts/" in href,
    })

if not videos:
    raise SystemExit("feed returned no videos; keeping the previous list")

os.makedirs("data", exist_ok=True)
with open("data/videos.json", "w", encoding="utf-8") as f:
    json.dump({"channel": CHANNEL_ID, "videos": videos}, f, ensure_ascii=False, indent=1)
print(f"saved {len(videos)} videos")
