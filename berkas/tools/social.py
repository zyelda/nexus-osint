from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from berkas.security import SafeHttpError, safe_get
from berkas.tools.base import ToolResult, edge, entity, evidence, fail, not_found, ok


def github_user(value: str, ctx: dict) -> ToolResult:
    username = value.strip().lstrip("@")
    url = f"https://api.github.com/users/{quote(username)}"
    try:
        response = safe_get(url, timeout=15, headers={"Accept": "application/vnd.github+json"})
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status == 404:
        return not_found({"username": username, "status": "GitHub user tidak ditemukan."})
    if response.status == 403:
        return fail("rate_limited", "GitHub API rate limit tercapai.")
    if response.status != 200:
        return fail("upstream_error", f"GitHub mengembalikan status {response.status}.")
    try:
        payload = response.json()
    except ValueError:
        return fail("invalid_response", "GitHub tidak mengembalikan JSON.")
    entities = []
    edges = []
    ev = []
    name = payload.get("name") or ""
    if name:
        person = entity("person", name, name.lower(), 0.75, source="github", github=username)
        entities.append(person)
        edges.append(edge("input", person.key, "profile_of", 0.8))
        ev.append(evidence("profile", 3.0, payload.get("html_url", url), f"Nama profil GitHub: {name}", entity_key=person.key))
    email = payload.get("email") or ""
    if email:
        email_entity = entity("email", email, email.lower(), 0.85, source="github")
        entities.append(email_entity)
        edges.append(edge("input", email_entity.key, "candidate_email", 0.75))
        ev.append(evidence("profile", 4.0, payload.get("html_url", url), f"Email publik GitHub: {email}", entity_key=email_entity.key))
    blog = payload.get("blog") or ""
    if blog:
        domain = re.sub(r"^https?://", "", blog).split("/")[0].lower()
        if domain and "." in domain:
            domain_entity = entity("domain", domain, domain, 0.7, source="github")
            entities.append(domain_entity)
            edges.append(edge("input", domain_entity.key, "uses_domain", 0.65))
    twitter = payload.get("twitter_username") or ""
    if twitter:
        twitter_entity = entity("username", twitter, twitter.lower(), 0.75, source="github", platform="x")
        entities.append(twitter_entity)
        edges.append(edge("input", twitter_entity.key, "same_username", 0.7))
    company = payload.get("company") or ""
    if company:
        org = entity("org", company.strip("@"), company.strip("@").lower(), 0.65, source="github")
        entities.append(org)
        edges.append(edge("input", org.key, "member_of", 0.6))
    data = {
        "username": username,
        "name": name,
        "bio": payload.get("bio", ""),
        "company": company,
        "location": payload.get("location", ""),
        "blog": blog,
        "email": email,
        "twitter": twitter,
        "public_repos": payload.get("public_repos", 0),
        "followers": payload.get("followers", 0),
        "created_at": payload.get("created_at", ""),
        "avatar_url": payload.get("avatar_url", ""),
        "html_url": payload.get("html_url", url),
    }
    return ok(data, entities=entities, edges=edges, evidence=ev)


def _reddit(username: str) -> dict | None:
    try:
        response = safe_get(f"https://www.reddit.com/user/{quote(username)}/about.json", timeout=8)
        if response.status != 200:
            return None
        payload = response.json().get("data", {})
        if not payload or payload.get("is_suspended"):
            return None
        return {
            "site": "Reddit",
            "url": f"https://www.reddit.com/user/{username}",
            "name": payload.get("name", username),
            "created": payload.get("created_utc"),
            "karma": payload.get("total_karma"),
            "icon": payload.get("icon_img", ""),
        }
    except Exception:
        return None


def _bluesky(username: str) -> dict | None:
    handle = username if "." in username else f"{username}.bsky.social"
    try:
        response = safe_get(
            f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={quote(handle)}",
            timeout=8,
        )
        if response.status != 200:
            return None
        payload = response.json()
        return {
            "site": "Bluesky",
            "url": f"https://bsky.app/profile/{handle}",
            "name": payload.get("displayName", handle),
            "handle": payload.get("handle", handle),
            "description": payload.get("description", ""),
        }
    except Exception:
        return None


def _keybase(username: str) -> dict | None:
    try:
        response = safe_get(f"https://keybase.io/_/api/1.0/user/lookup.json?username={quote(username)}", timeout=8)
        if response.status != 200:
            return None
        payload = response.json()
        them = payload.get("them")
        if not them:
            return None
        profile = them.get("profile", {}) if isinstance(them, dict) else {}
        return {
            "site": "Keybase",
            "url": f"https://keybase.io/{username}",
            "name": profile.get("full_name", username),
            "bio": profile.get("bio", ""),
            "location": profile.get("location", ""),
        }
    except Exception:
        return None


def _telegram(username: str) -> dict | None:
    try:
        response = safe_get(f"https://t.me/{quote(username)}", timeout=8)
        if response.status != 200 or "tgme_page_title" not in response.text:
            return None
        title = re.search(r'<meta property="og:title" content="([^"]+)"', response.text)
        description = re.search(r'<meta property="og:description" content="([^"]+)"', response.text)
        return {
            "site": "Telegram",
            "url": f"https://t.me/{username}",
            "name": title.group(1) if title else username,
            "description": description.group(1) if description else "",
        }
    except Exception:
        return None


def public_profiles(value: str, ctx: dict) -> ToolResult:
    username = value.strip().lstrip("@")
    checks = [_reddit, _bluesky, _keybase, _telegram]
    results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(check, username): check.__name__ for check in checks}
        for future in as_completed(futures):
            try:
                item = future.result()
                if item:
                    results.append(item)
            except Exception:
                continue
    entities = []
    edges = []
    ev = []
    for item in results:
        account = entity(
            "account",
            f"{item['site']}: {username}",
            f"{item['site'].lower()}:{username.lower()}",
            0.75,
            source="public_profiles",
            site=item["site"],
            url=item["url"],
            name=item.get("name", ""),
        )
        entities.append(account)
        edges.append(edge("input", account.key, "has_account", 0.8))
        ev.append(evidence("profile", 3.0, item["url"], f"Profil publik {item['site']}", entity_key=account.key))
        name = item.get("name", "")
        if name and name.lower() != username.lower():
            person = entity("person", name, name.lower(), 0.55, source=f"public_profiles:{item['site']}")
            entities.append(person)
            edges.append(edge(account.key, person.key, "display_name", 0.55))
    data = {"username": username, "profiles": results, "count": len(results)}
    if not results:
        return not_found(data, warnings=["Tidak ada profil publik yang bisa diverifikasi."])
    return ok(data, entities=entities, edges=edges, evidence=ev)
