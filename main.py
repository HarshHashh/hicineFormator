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



def zip_size(text):
    if not text:
        return None
    return text.replace(" ", "").upper()

def seasons_zip(raw_text: str):
    seasons = {}

    # Split by Season X :
    parts = re.split(r"\bSeason\s+(\d+)\s*:\s*", raw_text)

    for i in range(1, len(parts), 2):
        season_number = int(parts[i])
        block = parts[i + 1]

        streams = []

        # Find every URL and some text after it
        url_pattern = re.compile(
            r"(https://[^\s,]+)\s*,?\s*([^:\n]+)",
            re.I
        )

        for match in url_pattern.finditer(block):
            url = match.group(1)
            tail = match.group(2)

            # quality
            q_match = re.search(r"(480p|720p|1080p|2160p)", tail, re.I)
            quality = q_match.group(1) if q_match else None

            
            streams.append({
                "quality": quality,
                "url": url
            })

        seasons[f"season_{season_number}"] = streams

    return seasons




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
    data = []
    if not links_text:
        return streams
    link = [links_text.split(",")]
    
    for i in link[0]:
        if 'Link' not in i and len(i) > 10:
            if '\n' in i:
                streams.append(i.split("\n")[1])
            else:
                streams.append(i)

  
    for i in range(0,len(streams), 2):
        if len(streams) == i:
            break
        url = streams[i]
        title = streams[i+1]
        data.append({
            'title' : title,
            'url' : url
        })
        
        
    return data
   


# Season parse
def normalize_size(raw_size):
    if not raw_size:
        return None
    return raw_size.replace(" ", "")

def format_season(raw_text: str):
    result = {
        "title": "",
        "episodes": []
    }

    # ---------- 1. Split title ----------
    title_match = re.split(r"\bEpisode\s+1\s*:\s*", raw_text, maxsplit=1)
    result["title"] = title_match[0].strip()

    episode_text = "Episode 1 : " + title_match[1]

    # ---------- 2. Split episodes ----------
    episode_parts = re.split(r"\bEpisode\s+(\d+)\s*:\s*", episode_text)

    for i in range(1, len(episode_parts), 2):
        ep_number = int(episode_parts[i])
        ep_block = episode_parts[i + 1]

        streams = []

        # ---------- 3. Unified stream regex ----------
        stream_pattern = re.compile(
            r"""
            (?:
                (?P<q1>480p|720p|1080p|2160p)\s*:\s*
                (?P<u1>https://[^\s,]+)
                (?:\s*,\s*(?P<s1>[\d.]+\s*(?:MB|GB)))?
            )
            |
            (?:
                (?P<u2>https://[^\s,]+)
                \s*,\s*(?P<s2>[\d.]+\s*(?:MB|GB))
                \s*,\s*(?P<q2>480p|720p|1080p|2160p)
            )
            """,
            re.I | re.VERBOSE
        )

        for m in stream_pattern.finditer(ep_block):
            quality = m.group("q1") or m.group("q2")
            url = m.group("u1") or m.group("u2")
            size = normalize_size(m.group("s1") or m.group("s2"))

            streams.append({
                "quality": quality,
                "size": size,
                "url": url
            })

        result["episodes"].append({
            "episode": ep_number,
            "streams": streams
        })

    return result



def extract_all_seasons(data):
    seasons = {}
    idx = 1

    while True:
        key = f"season_{idx}"
        if key not in data or data[key] is None:
            break

        seasons[key] = format_season    (data[key])
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
        "zip": seasons_zip(data["season_zip"]),
        "created_at": data["date"],
        "updated_at": data["modified_date"],
        "generated_at": datetime.utcnow().isoformat()
    }


# ---------- API ROUTES ----------
@app.get("/hehe/{type}/{_id}")
def gett(type: str, _id: str):
    url = f"https://api.hicine.info/api/{type}/{_id}"

    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()

        if "movie" in type.lower():
            return data

        if "series" in type.lower() or "anime" in type.lower():
            return data
    
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))



@app.get("/type/{type}/{_id}")
def get_by_type(type: str, _id: str):
    url = f"https://api.hicine.info/api/{type}/{_id}"

    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()

        if "movie" in type.lower():
            return format_movie(data)

        if "series" in type.lower() or "anime" in type.lower():
            return format_series(data)


        raise HTTPException(
            status_code=400,
            detail="Invalid type. Use 'movies' or 'series'."
        )

    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=str(e))


