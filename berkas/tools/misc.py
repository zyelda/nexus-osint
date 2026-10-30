from __future__ import annotations

import re
from urllib.parse import quote

from berkas.security import SafeHttpError, safe_get
from berkas.tools.base import ToolResult, fail, not_found, ok, partial


def crypto_btc(value: str, ctx: dict) -> ToolResult:
    url = f"https://blockchain.info/rawaddr/{quote(value)}?limit=20"
    try:
        response = safe_get(url, timeout=15)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status != 200:
        return fail("upstream_error", f"Blockchain.info mengembalikan status {response.status}.")
    try:
        payload = response.json()
    except ValueError:
        return fail("invalid_response", "Blockchain.info tidak mengembalikan JSON.")
    data = {
        "address": value,
        "balance_btc": payload.get("final_balance", 0) / 100000000,
        "total_received_btc": payload.get("total_received", 0) / 100000000,
        "transactions": payload.get("n_tx", 0),
        "last_seen": "active" if payload.get("n_tx", 0) else "unused",
        "explorer": f"https://www.blockchain.com/explorer/addresses/btc/{value}",
    }
    return ok(data)


def mac_vendor(value: str, ctx: dict) -> ToolResult:
    try:
        response = safe_get(f"https://api.macvendors.com/{quote(value)}", timeout=8)
    except SafeHttpError as exc:
        return fail(exc.code, exc.message)
    if response.status == 404:
        return not_found({"mac": value, "vendor": "Unknown"})
    if response.status != 200:
        return fail("upstream_error", f"MAC Vendors mengembalikan status {response.status}.")
    return ok({"mac": value.upper(), "vendor": response.text.strip()[:200]})


def youtube_intel(value: str, ctx: dict) -> ToolResult:
    match = re.search(r"(?:v=|/)([0-9A-Za-z_-]{11})", value)
    if not match:
        return fail("invalid_input", "URL YouTube tidak valid.")
    video_id = match.group(1)
    data = {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}"}
    warnings = []
    try:
        response = safe_get(
            f"https://www.youtube.com/oembed?url={quote('https://www.youtube.com/watch?v=' + video_id)}&format=json",
            timeout=10,
        )
        if response.status == 200:
            payload = response.json()
            data.update(
                {
                    "title": payload.get("title", ""),
                    "channel": payload.get("author_name", ""),
                    "channel_url": payload.get("author_url", ""),
                    "thumbnail": payload.get("thumbnail_url", ""),
                }
            )
        else:
            warnings.append(f"oEmbed mengembalikan status {response.status}.")
    except Exception as exc:
        warnings.append(f"Metadata YouTube gagal: {exc}")
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript = YouTubeTranscriptApi().fetch(video_id, languages=["id", "en"])
        rows = transcript.to_raw_data()
        text = " ".join(str(row.get("text", "")) for row in rows)
        data["transcript_preview"] = text[:800]
        data["transcript_segments"] = len(rows)
    except Exception as exc:
        warnings.append(f"Transkrip tidak tersedia: {exc}")
    if not data.get("title") and not data.get("transcript_preview"):
        return partial(data, warnings=warnings)
    return ok(data, warnings=warnings)

