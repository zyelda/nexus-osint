from __future__ import annotations

from berkas.tools import identity, misc, network, search, social, username
from berkas.tools.base import ToolRegistry, ToolSpec

registry = ToolRegistry()

registry.register(
    ToolSpec(
        id="domain_rdap",
        label="RDAP domain",
        description="Registrar, status, tanggal, dan kontak organisasi dari RDAP.",
        inputs=["domain"],
        outputs=["org"],
        run=network.domain_rdap,
        category="domain",
        legal_note="Data registrasi domain publik.",
    )
)
registry.register(
    ToolSpec(
        id="domain_dns",
        label="DNS records",
        description="A, AAAA, MX, NS, TXT, SOA, CAA, SPF, dan DMARC.",
        inputs=["domain"],
        outputs=["ip", "domain"],
        run=network.domain_dns,
        category="domain",
        legal_note="Query DNS publik.",
    )
)
registry.register(
    ToolSpec(
        id="domain_ssl",
        label="TLS certificate",
        description="Issuer, subject, SAN, dan masa berlaku sertifikat.",
        inputs=["domain"],
        outputs=[],
        run=network.domain_ssl,
        category="domain",
        legal_note="Membaca sertifikat publik pada port 443.",
    )
)
registry.register(
    ToolSpec(
        id="domain_http",
        label="HTTP fingerprint",
        description="Teknologi, security header, title, dan status halaman.",
        inputs=["domain"],
        outputs=[],
        run=network.domain_http,
        category="domain",
        legal_note="Hanya GET ke halaman publik.",
    )
)
registry.register(
    ToolSpec(
        id="domain_crtsh",
        label="Certificate transparency",
        description="Subdomain dari log sertifikat crt.sh.",
        inputs=["domain"],
        outputs=["domain"],
        run=network.domain_crtsh,
        category="domain",
        legal_note="Data transparansi sertifikat publik.",
    )
)
registry.register(
    ToolSpec(
        id="domain_wayback",
        label="Wayback snapshots",
        description="Riwayat snapshot domain di Internet Archive.",
        inputs=["domain"],
        outputs=[],
        run=network.domain_wayback,
        category="domain",
        legal_note="Data arsip publik.",
    )
)
registry.register(
    ToolSpec(
        id="ip_geo",
        label="IP geolocation",
        description="Geo, ISP, organisasi, dan koordinat dari ipwho.is lewat HTTPS.",
        inputs=["ip"],
        outputs=["org"],
        run=network.ip_geo,
        category="network",
        legal_note="Data geolokasi publik, bukan lokasi orang.",
    )
)
registry.register(
    ToolSpec(
        id="ip_reputation",
        label="IP reputation",
        description="Tor exit node dan AbuseIPDB jika key tersedia.",
        inputs=["ip"],
        outputs=[],
        run=network.ip_reputation,
        requires_key="ABUSEIPDB_API_KEY",
        category="network",
        legal_note="Reputasi IP dari sumber publik.",
    )
)
registry.register(
    ToolSpec(
        id="ip_shodan",
        label="Shodan host",
        description="Organisasi, hostname, dan port yang sudah dipindai Shodan.",
        inputs=["ip"],
        outputs=["org", "domain"],
        run=network.ip_shodan,
        requires_key="SHODAN_API_KEY",
        category="network",
        legal_note="Data pasif dari indeks Shodan, bukan pemindaian langsung.",
    )
)
registry.register(
    ToolSpec(
        id="email_intel",
        label="Email intelligence",
        description="MX, SPF, DMARC, provider, disposable, Gravatar, dan kandidat username.",
        inputs=["email"],
        outputs=["domain", "username", "url"],
        run=identity.email_intel,
        category="identity",
        legal_note="DNS dan Gravatar publik.",
    )
)
registry.register(
    ToolSpec(
        id="email_breach",
        label="Breach check",
        description="Cek email di Have I Been Pwned. Membutuhkan API key.",
        inputs=["email"],
        outputs=["breach"],
        run=identity.email_breach,
        requires_key="HIBP_API_KEY",
        category="breach",
        legal_note="Gunakan hanya dengan dasar hukum yang sah.",
    )
)
registry.register(
    ToolSpec(
        id="phone_intel",
        label="Phone intelligence",
        description="Format E.164, carrier, region, tipe, timezone, dan link messenger.",
        inputs=["phone"],
        outputs=[],
        run=identity.phone_intel,
        category="identity",
        legal_note="Tanpa lookup pemilik nomor.",
    )
)
registry.register(
    ToolSpec(
        id="nik_parse",
        label="NIK parser",
        description="Validasi format, tanggal lahir, gender, dan kode wilayah.",
        inputs=["nik"],
        outputs=[],
        run=identity.nik_parse,
        category="identity",
        legal_note="Validasi format saja, tanpa lookup Dukcapil.",
    )
)
registry.register(
    ToolSpec(
        id="npwp_parse",
        label="NPWP parser",
        description="Validasi format dan status pusat atau cabang.",
        inputs=["npwp"],
        outputs=[],
        run=identity.npwp_parse,
        category="identity",
        legal_note="Validasi format saja, tanpa lookup DJP.",
    )
)
registry.register(
    ToolSpec(
        id="username_enum",
        label="Username enumeration",
        description="Cek username di 30 platform dengan status found, not found, blocked, unknown.",
        inputs=["username"],
        outputs=["account"],
        run=username.username_enum,
        category="social",
        timeout_s=30,
        legal_note="Hanya halaman publik, tanpa login.",
    )
)
registry.register(
    ToolSpec(
        id="person_search",
        label="Person search",
        description="Pencarian web dan link manual untuk nama atau kata kunci.",
        inputs=["person", "email", "username"],
        outputs=["url"],
        run=search.person_search,
        category="search",
        legal_note="Hormati ToS mesin pencari.",
    )
)
registry.register(
    ToolSpec(
        id="pddikti",
        label="PDDikti",
        description="Pencarian data mahasiswa publik, dengan fallback link manual.",
        inputs=["person", "nim"],
        outputs=[],
        run=search.pddikti,
        category="academic",
        legal_note="Data publik, hati-hati PII.",
    )
)
registry.register(
    ToolSpec(
        id="paste_search",
        label="Paste sites",
        description="Cek psbdmp dan sediakan link Gist, Pastebin, dan search engine.",
        inputs=["email", "username", "domain"],
        outputs=[],
        run=search.paste_search,
        category="breach",
        legal_note="Review manual, data publik.",
    )
)
registry.register(
    ToolSpec(
        id="github_user",
        label="GitHub profile",
        description="Profil, nama, email publik, blog, organisasi, dan akun terkait.",
        inputs=["username", "email"],
        outputs=["person", "email", "domain", "org", "username"],
        run=social.github_user,
        category="social",
        timeout_s=25,
        legal_note="GitHub public API.",
    )
)
registry.register(
    ToolSpec(
        id="public_profiles",
        label="Public profiles",
        description="Reddit, Bluesky, Keybase, dan Telegram.",
        inputs=["username"],
        outputs=["account", "person"],
        run=social.public_profiles,
        category="social",
        legal_note="Hanya endpoint publik.",
    )
)
registry.register(
    ToolSpec(
        id="crypto_btc",
        label="Bitcoin address",
        description="Saldo, transaksi, dan status alamat Bitcoin.",
        inputs=["btc"],
        outputs=[],
        run=misc.crypto_btc,
        category="finance",
        legal_note="Data blockchain publik.",
    )
)
registry.register(
    ToolSpec(
        id="mac_vendor",
        label="MAC vendor",
        description="Vendor dari alamat MAC.",
        inputs=["mac"],
        outputs=[],
        run=misc.mac_vendor,
        category="network",
        legal_note="Data publik.",
    )
)
registry.register(
    ToolSpec(
        id="youtube_intel",
        label="YouTube metadata",
        description="Metadata video dan transkrip jika tersedia.",
        inputs=["url"],
        outputs=[],
        run=misc.youtube_intel,
        category="media",
        legal_note="Hanya konten publik.",
    )
)
registry.register(
    ToolSpec(
        id="shortlink_expand",
        label="Expand shortlink",
        description="Ikuti redirect dengan proteksi SSRF.",
        inputs=["url"],
        outputs=["url", "domain"],
        run=network.shortlink_expand,
        category="network",
        legal_note="Hanya redirect publik.",
    )
)
registry.register(
    ToolSpec(
        id="url_reputation",
        label="URL reputation",
        description="Reputasi URL dari VirusTotal. Membutuhkan API key.",
        inputs=["url"],
        outputs=[],
        run=network.url_reputation,
        requires_key="VT_API_KEY",
        category="reputation",
        legal_note="Gunakan hanya untuk URL yang relevan.",
    )
)
