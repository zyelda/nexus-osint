from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from berkas.security import safe_get
from berkas.tools.base import ToolResult, edge, entity, evidence, ok, partial

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

SITES = [
    {"name": "GitHub", "url": "https://github.com/{u}", "error": "Not Found", "category": "code"},
    {"name": "GitLab", "url": "https://gitlab.com/{u}", "error": "Page Not Found", "category": "code"},
    {"name": "Reddit", "url": "https://www.reddit.com/user/{u}", "error": "nobody on Reddit goes by that name", "category": "social"},
    {"name": "Bluesky", "url": "https://bsky.app/profile/{u}.bsky.social", "error": "Profile not found", "category": "social"},
    {"name": "Keybase", "url": "https://keybase.io/{u}", "error": "Not found", "category": "identity"},
    {"name": "Telegram", "url": "https://t.me/{u}", "error": "tgme_page_title", "category": "messaging", "invert": True},
    {"name": "YouTube", "url": "https://www.youtube.com/@{u}", "error": "404 Not Found", "category": "video"},
    {"name": "TikTok", "url": "https://www.tiktok.com/@{u}", "error": "Couldn't find this account", "category": "video"},
    {"name": "Instagram", "url": "https://www.instagram.com/{u}/", "error": "Sorry, this page isn't available", "category": "social", "limited": True},
    {"name": "X", "url": "https://x.com/{u}", "error": "This account doesn", "category": "social", "limited": True},
    {"name": "Pinterest", "url": "https://www.pinterest.com/{u}/", "error": "User not found", "category": "social"},
    {"name": "Medium", "url": "https://medium.com/@{u}", "error": "404", "category": "writing"},
    {"name": "Dev.to", "url": "https://dev.to/{u}", "error": "404", "category": "writing"},
    {"name": "Hacker News", "url": "https://news.ycombinator.com/user?id={u}", "error": "No such user", "category": "community"},
    {"name": "Stack Overflow", "url": "https://stackoverflow.com/users/{u}", "error": "Page not found", "category": "community"},
    {"name": "Kaggle", "url": "https://www.kaggle.com/{u}", "error": "404", "category": "data"},
    {"name": "Docker Hub", "url": "https://hub.docker.com/u/{u}", "error": "404", "category": "code"},
    {"name": "npm", "url": "https://www.npmjs.com/~{u}", "error": "404", "category": "code"},
    {"name": "PyPI", "url": "https://pypi.org/user/{u}", "error": "404", "category": "code"},
    {"name": "Behance", "url": "https://www.behance.net/{u}", "error": "404", "category": "design"},
    {"name": "Dribbble", "url": "https://dribbble.com/{u}", "error": "404", "category": "design"},
    {"name": "SoundCloud", "url": "https://soundcloud.com/{u}", "error": "not found", "category": "audio"},
    {"name": "Spotify", "url": "https://open.spotify.com/user/{u}", "error": "Page not found", "category": "audio"},
    {"name": "Steam", "url": "https://steamcommunity.com/id/{u}", "error": "could not be found", "category": "gaming"},
    {"name": "Twitch", "url": "https://www.twitch.tv/{u}", "error": "content_unavailable", "category": "video"},
    {"name": "Chess.com", "url": "https://www.chess.com/member/{u}", "error": "404", "category": "gaming"},
    {"name": "Letterboxd", "url": "https://letterboxd.com/{u}/", "error": "404", "category": "social"},
    {"name": "Strava", "url": "https://www.strava.com/athletes/{u}", "error": "404", "category": "fitness"},
    {"name": "Linktree", "url": "https://linktr.ee/{u}", "error": "404", "category": "identity"},
    {"name": "Keybase", "url": "https://keybase.io/{u}", "error": "Not found", "category": "identity"},
]


def _check(site: dict, username: str) -> dict:
    url = site["url"].format(u=quote(username))
    try:
        response = safe_get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
            timeout=8,
            max_redirects=3,
        )
    except Exception as exc:
        return {"site": site["name"], "url": url, "status": "unknown", "category": site["category"], "note": str(exc)[:120]}
    body = response.text[:200000]
    lower = body.lower()
    error = site.get("error", "").lower()
    status_code = response.status
    if status_code in {401, 403, 429}:
        status = "blocked"
    elif status_code == 404:
        status = "not_found"
    elif status_code >= 500:
        status = "unknown"
    elif site.get("invert"):
        status = "found" if error and error in lower else "not_found"
    elif error and error in lower:
        status = "not_found"
    elif status_code == 200:
        status = "found"
    else:
        status = "unknown"
    return {
        "site": site["name"],
        "url": url,
        "status": status,
        "category": site["category"],
        "http_status": status_code,
        "limited": bool(site.get("limited")),
    }


def username_enum(value: str, ctx: dict) -> ToolResult:
    username = value.strip().lstrip("@")
    if not username:
        return partial({"username": value}, warnings=["Username kosong."])
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()
    unique_sites = []
    for site in SITES:
        key = (site["name"], site["url"])
        if key in seen:
            continue
        seen.add(key)
        unique_sites.append(site)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_check, site, username): site for site in unique_sites}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                site = futures[future]
                results.append({"site": site["name"], "url": site["url"].format(u=username), "status": "unknown", "note": str(exc)[:120]})
    results.sort(key=lambda item: (item["status"] != "found", item["site"]))
    entities = []
    edges = []
    ev = []
    for result in results:
        if result["status"] != "found":
            continue
        account = entity(
            "account",
            f"{result['site']}: {username}",
            f"{result['site'].lower()}:{username.lower()}",
            0.75,
            source="username_enum",
            site=result["site"],
            url=result["url"],
            category=result.get("category", ""),
            http_status=result.get("http_status"),
        )
        entities.append(account)
        edges.append(edge("input", account.key, "has_account", 0.8))
        ev.append(
            evidence(
                "profile",
                3.0,
                result["url"],
                f"Akun ditemukan di {result['site']}",
                entity_key=account.key,
            )
        )
    found = sum(1 for item in results if item["status"] == "found")
    blocked = sum(1 for item in results if item["status"] == "blocked")
    data = {
        "username": username,
        "results": results,
        "found": found,
        "checked": len(results),
        "blocked": blocked,
    }
    warnings = []
    if blocked:
        warnings.append(f"{blocked} situs memblokir pemeriksaan otomatis. Status tersebut bukan berarti akun tidak ada.")
    if found == 0:
        warnings.append("Tidak ada akun yang terverifikasi. Hasil bisa berbeda karena rate limit atau login wall.")
    return ok(data, entities=entities, edges=edges, evidence=ev, warnings=warnings)
