from __future__ import annotations

from urllib.parse import quote

from berkas.security import SafeHttpError, safe_get
from berkas.tools.base import ToolResult, edge, entity, evidence, ok, partial

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None


def person_search(value: str, ctx: dict) -> ToolResult:
    results: list[dict] = []
    warnings: list[str] = []
    if DDGS is not None:
        try:
            with DDGS() as client:
                for item in client.text(value, region="id-id", safesearch="off", max_results=12):
                    title = item.get("title", "").strip()
                    href = item.get("href", "").strip()
                    if not title or not href:
                        continue
                    results.append(
                        {
                            "title": title,
                            "url": href,
                            "snippet": (item.get("body", "") or "")[:300],
                            "source": "duckduckgo",
                        }
                    )
        except Exception as exc:
            warnings.append(f"Pencarian DuckDuckGo gagal: {exc}")
    else:
        warnings.append("Library pencarian tidak tersedia.")

    links = {
        "google": f"https://www.google.com/search?q={quote('\"' + value + '\"')}",
        "news": f"https://www.google.com/search?q={quote(value)}&tbm=nws",
        "images": f"https://www.google.com/search?q={quote(value)}&tbm=isch",
        "linkedin": f"https://www.google.com/search?q={quote('site:linkedin.com/in \"' + value + '\"')}",
        "documents": f"https://www.google.com/search?q={quote(value + ' filetype:pdf')}",
    }
    entities = []
    edges = []
    ev = []
    for item in results[:8]:
        url_entity = entity("url", item["url"], item["url"], 0.65, source="search", title=item["title"])
        entities.append(url_entity)
        edges.append(edge("input", url_entity.key, "mentioned_in", 0.55))
        ev.append(evidence("search_result", 1.5, item["url"], item["title"], entity_key=url_entity.key))
    data = {"query": value, "results": results, "links": links, "count": len(results)}
    if not results:
        return partial(data, warnings=warnings + ["Tidak ada hasil pencarian langsung. Gunakan link manual."], entities=entities, edges=edges, evidence=ev)
    return ok(data, entities=entities, edges=edges, evidence=ev, warnings=warnings)


def pddikti(value: str, ctx: dict) -> ToolResult:
    url = f"https://api-frontend.kemdikbud.go.id/hit_mhs/{quote(value)}"
    try:
        response = safe_get(
            url,
            timeout=12,
            headers={"Referer": "https://pddikti.kemdikbud.go.id/", "Accept": "application/json"},
        )
    except SafeHttpError as exc:
        return partial(
            {
                "query": value,
                "status": "blocked",
                "message": exc.message,
                "manual_link": f"https://www.google.com/search?q={quote('site:pddikti.kemdikbud.go.id ' + value)}",
            },
            warnings=["PDDikti tidak bisa diakses dari server ini. Gunakan link manual."],
        )
    if response.status != 200:
        return partial(
            {
                "query": value,
                "status": "blocked",
                "http_status": response.status,
                "manual_link": f"https://www.google.com/search?q={quote('site:pddikti.kemdikbud.go.id ' + value)}",
            },
            warnings=[f"PDDikti mengembalikan status {response.status}."],
        )
    try:
        payload = response.json()
    except ValueError:
        return partial({"query": value, "status": "invalid_response"}, warnings=["PDDikti tidak mengembalikan JSON."])
    raw = payload.get("mahasiswa", [])
    data = {"query": value, "results": raw[:20], "count": len(raw), "source": url}
    if not raw:
        return partial(data, warnings=["Tidak ada hasil PDDikti."])
    return ok(data, evidence=[evidence("academic", 2.0, url, f"{len(raw)} hasil PDDikti", entity_key=f"person:{value.lower()}")])


def paste_search(value: str, ctx: dict) -> ToolResult:
    links = {
        "psbdmp": f"https://psbdmp.ws/search/{quote(value)}",
        "gist": f"https://gist.github.com/search?q={quote(value)}",
        "google_pastebin": f"https://www.google.com/search?q={quote('site:pastebin.com \"' + value + '\"')}",
        "google_pastes": f"https://www.google.com/search?q={quote('\"' + value + '\" (pastebin OR ghostbin OR rentry)')}",
    }
    data = {"query": value, "links": links, "status": "manual_review"}
    try:
        response = safe_get(f"https://psbdmp.ws/api/v3/search/{quote(value)}", timeout=8)
        if response.status == 200:
            try:
                payload = response.json()
                data["psbdmp"] = payload
                data["status"] = "ok"
            except ValueError:
                data["psbdmp"] = {"raw": response.text[:500]}
        else:
            data["psbdmp"] = {"status": response.status}
    except SafeHttpError as exc:
        data["psbdmp"] = {"error": exc.message}
    return partial(
        data,
        warnings=["Paste site search membutuhkan review manual. Link disediakan untuk verifikasi."],
    )


def generate_dorks(value: str, entity_type: str) -> dict:
    safe = quote(value)
    if entity_type in {"domain", "url"}:
        domain = value.replace("https://", "").replace("http://", "").split("/")[0]
        return {
            "Subdomain": f"https://www.google.com/search?q={quote('site:*.' + domain + ' -www')}",
            "Dokumen": f"https://www.google.com/search?q={quote('site:' + domain + ' filetype:pdf OR filetype:docx OR filetype:xlsx')}",
            "Index of": f"https://www.google.com/search?q={quote('site:' + domain + ' intitle:\"index of\"')}",
            "Login panel": f"https://www.google.com/search?q={quote('site:' + domain + ' inurl:login OR inurl:admin')}",
            "Pastebin": f"https://www.google.com/search?q={quote('site:pastebin.com \"' + domain + '\"')}",
            "GitHub": f"https://github.com/search?q={safe}&type=code",
            "crt.sh": f"https://crt.sh/?q=%25.{safe}",
            "Wayback": f"https://web.archive.org/web/*/{safe}",
        }
    return {
        "Semua web": f"https://www.google.com/search?q={quote('\"' + value + '\"')}",
        "Sosial media": f"https://www.google.com/search?q={quote('site:facebook.com OR site:instagram.com OR site:linkedin.com OR site:tiktok.com \"' + value + '\"')}",
        "Forum": f"https://www.google.com/search?q={quote('site:reddit.com OR site:kaskus.co.id \"' + value + '\"')}",
        "Dokumen": f"https://www.google.com/search?q={quote('filetype:pdf OR filetype:docx intext:\"' + value + '\"')}",
        "Pastebin": f"https://www.google.com/search?q={quote('site:pastebin.com OR site:rentry.co \"' + value + '\"')}",
        "GitHub": f"https://github.com/search?q={safe}&type=users",
    }
