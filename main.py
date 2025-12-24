from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import re
from datetime import datetime

app = FastAPI(title="Hicine Normalizer API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins (safe for public API)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- SIZE NORMALIZATION ----------

def normalize_size(size, quality):
    if not size or not quality:
        return size

    size = size.upper().replace(" ", "")
    quality = quality.lower()

    if quality == "1080p" and size.endswith("GB"):
        num = size[:-2]
        if num.isdigit() and len(num) >= 2:
            return f"{num[:-1]}.{num[-1]}GB"

    return size


# ---------- MOVIE PARSER ----------

def parse_movie_links(links_text):
    streams = []
    if not links_text:
        return streams

    lines = [l.strip() for l in links_text.split("\n") if l.strip()]

    for line in lines:
        url_match = re.search(r"https://[^\s,]+", line)
        if not url_match:
            continue

        url = url_match.group()

        quality_match = re.search(r"(480p|720p|1080p|2160p|4K)", line, re.I)
        quality = quality_match.group(1) if quality_match else "unknown"

        size_match = re.search(r"([\d.]+\s*(MB|GB))", line, re.I)
        raw_size = size_match.group(1) if size_match else None
        size = normalize_size(raw_size, quality)

        source_match = re.search(r"(BluRay|WEB[- ]DL|HDRip|DVDRip)", line, re.I)
        source = source_match.group(1) if source_match else None

        streams.append({
            "quality": quality,
            "size": size,
            "source": source,
            "url": url
        })

    return streams


# ---------- SERIES PARSER ----------

def parse_season(season_text):
    episodes = {}
    parts = re.split(r"Episode\s+(\d+)\s*:", season_text)

    for i in range(1, len(parts), 2):
        ep_number = int(parts[i])
        ep_block = parts[i + 1]

        streams = []
        matches = re.findall(
            r"(480p|720p|1080p|2160p)\s*:\s*(https://[^\s,]+)"
            r"|"
            r"(https://[^\s,]+)\s*,\s*([\d.]+\s*MB)",
            ep_block
        )

        for m in matches:
            quality = m[0] if m[0] else "unknown"
            url = m[1] if m[1] else m[2]
            raw_size = m[3] if len(m) > 3 else None
            size = normalize_size(raw_size, quality)

            streams.append({
                "quality": quality,
                "size": size,
                "url": url
            })

        episodes[f"episode_{ep_number}"] = {
            "episode": ep_number,
            "streams": streams
        }

    return episodes


def extract_all_seasons(data):
    seasons = {}
    idx = 1

    while True:
        key = f"season_{idx}"
        if key not in data or data[key] is None:
            break

        seasons[key] = parse_season(data[key])
        idx += 1

    return seasons


# ---------- FORMATTERS ----------

def format_movie(data):
    return {
        "_id": data["_id"],
        "record_id": data["record_id"],
        "title": data["title"],
        "url_slug": data["url_slug"],
        "featured_image": data.get("featured_image"),
        "poster": data.get("poster"),
        "categories": data.get("categories"),
        "status": data["status"],
        "streams": parse_movie_links(data.get("links")),
        "created_at": data["date"],
        "updated_at": data["modified_date"],
        "generated_at": datetime.utcnow().isoformat()
    }


def format_series(data):
    return {
        "_id": data["_id"],
        "record_id": data["record_id"],
        "title": data["title"],
        "url_slug": data["url_slug"],
        "featured_image": data.get("featured_image"),
        "poster": data.get("poster"),
        "categories": data.get("categories"),
        "status": data["status"],
        "seasons": extract_all_seasons(data),
        "created_at": data["date"],
        "updated_at": data["modified_date"],
        "generated_at": datetime.utcnow().isoformat()
    }


# ---------- API ROUTES ----------

@app.get("/movies/{movie_id}")
def get_movie(movie_id: str):
    url = f"https://api.hicine.info/api/movies/{movie_id}"

    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        return format_movie(res.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/series/{series_id}")
def get_series(series_id: str):
    url = f"https://api.hicine.info/api/series/{series_id}"

    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        return format_series(res.json())
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
