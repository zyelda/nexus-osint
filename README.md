# Berkas

Workspace investigasi sumber publik. Satu intake menerima banyak entity sekaligus, memecahnya menjadi tipe yang dikenali, menjalankan tool yang relevan, lalu menyusun graph koneksi dan panel temuan yang bisa diaudit.

Berkas tidak menjual kesimpulan. Setiap temuan membawa sumber, bobot bukti, tingkat keyakinan, dan peringatan batasan data.

Dibuat oleh [Zulmatoriq (zyelda)](https://github.com/zyelda).

[![CI](https://github.com/zyelda/nexus-osint/actions/workflows/ci.yml/badge.svg)](https://github.com/zyelda/nexus-osint/actions/workflows/ci.yml)

- Frontend: <https://nexus-osint-lyart.vercel.app>
- Repositori: <https://github.com/zyelda/nexus-osint>

Nama repositori masih memakai nama lama. Nama produk dan identifier internal sudah memakai Berkas.

## Daftar isi

- [Apa itu Berkas](#apa-itu-berkas)
- [Yang tidak dilakukan](#yang-tidak-dilakukan)
- [Kemampuan](#kemampuan)
- [Arsitektur](#arsitektur)
- [Kebutuhan](#kebutuhan)
- [Menjalankan lokal](#menjalankan-lokal)
- [Mode pengembangan](#mode-pengembangan)
- [Environment variable](#environment-variable)
- [Cara pakai](#cara-pakai)
- [Membaca hasil](#membaca-hasil)
- [Ringkasan dan redaksi](#ringkasan-dan-redaksi)
- [Tool yang tersedia](#tool-yang-tersedia)
- [Format file](#format-file)
- [API](#api)
- [Ekspor](#ekspor)
- [Test](#test)
- [Docker](#docker)
- [Deploy Vercel](#deploy-vercel)
- [Deploy backend](#deploy-backend)
- [Backup dan restore](#backup-dan-restore)
- [Troubleshooting](#troubleshooting)
- [Migrasi nama](#migrasi-nama)
- [Struktur repositori](#struktur-repositori)
- [Kredit](#kredit)

## Apa itu Berkas

Berkas adalah aplikasi web untuk memetakan jejak publik dari satu atau beberapa entity. Alur utamanya:

1. Intake memecah teks menjadi entity bertipe.
2. Tool berjalan sesuai tipe entity dan ketersediaan key.
3. Hasil tool masuk ke graph sebagai node, edge, dan evidence.
4. Panel temuan menghitung keyakinan, menampilkan clue, peringatan, dan pivot berikutnya.
5. Ringkasan tiga lapis dan ekspor disusun dari data kasus yang sama.

Cocok untuk verifikasi vendor, pemetaan jejak publik organisasi, pemeriksaan metadata dokumen, dan penyusunan laporan internal yang bisa disitasi.

## Yang tidak dilakukan

Berkas hanya memakai sumber publik dan API resmi. Yang sengaja tidak dilakukan:

- Lookup pemilik nomor telepon, NIK, atau NPWP.
- Face recognition dan people-search scraper.
- Scraping halaman di balik login.
- Pemindaian port default. Data port hanya dibaca dari indeks Shodan bila key tersedia.
- Dark web.

`nik_parse` dan `npwp_parse` hanya memvalidasi format dan memecah kode wilayah atau tanggal. Keduanya tidak melakukan lookup pemilik.

Gunakan hanya untuk tujuan yang sah dan dengan kewenangan yang jelas. Isi tujuan dan dasar kewenangan saat membuat kasus.

## Kemampuan

- **Intake multi-entity.** Nama, email, telepon, username, domain, URL, IP, NIK, NPWP, NIM, alamat Bitcoin, dan MAC dalam satu submit.
- **Upload bukti.** Gambar, PDF, DOCX, XLSX, CSV, JSON, dan teks. Metadata, EXIF GPS, dan entity di dalam dokumen masuk ke graph.
- **Graph real-time.** Cytoscape dengan layout fcose. Node dan edge bertambah saat tool selesai, lewat Server-Sent Events.
- **Pivot.** Setiap node menawarkan tool yang cocok untuk tipenya. Hasil tool bisa menjadi entity baru dan memicu pivot berikutnya.
- **Panel temuan.** Skor keyakinan dengan alasan, kandidat identitas, clue berbobot, linimasa, peringatan, dan pivot yang disarankan.
- **Ringkasan tiga lapis.** Ringkasan satu menit untuk pembaca awam, naratif pendek, dan lampiran analis. Setiap poin membawa sitasi bukti. Tanpa provider AI, ringkasan disusun lokal.
- **Mode Awam dan Analis.** Mode Awam menyamarkan sebagian email, telepon, NIK, dan NPWP. Mode Analis menampilkan data penuh dan lampiran teknis.
- **Pencarian graph.** Cari entity berdasarkan nama, domain, atau username, lalu saring per tipe.
- **Cache lokal.** Hasil tool dan ringkasan disimpan di SQLite dengan TTL. Batch tool dibatasi agar satu klik tidak membanjiri antrean.
- **Ekspor.** JSON, CSV (zip), PDF dengan ringkasan awam, dan GraphML.
- **Dokumentasi dalam aplikasi.** Halaman panduan membahas alur, skor, tool, API, deploy, dan batas penggunaan.
- **Tema terang dan gelap**, responsif sampai lebar ponsel, fokus keyboard terlihat.

## Arsitektur

```text
berkas/
  api.py              REST + SSE, auth token, upload, export
  app.py              application factory, CORS, security header, SPA fallback
  config.py           Settings dari environment
  db.py               SQLAlchemy model: Case, Entity, Edge, Evidence, ToolRun, AuditLog
  entities.py         parser entity, normalisasi, rencana tool per tipe
  security.py         SSRF guard, safe_request, sanitasi nama file
  tools/              25 tool, registry, ekstraksi file
  services/
    cases.py          CRUD kasus dan upsert graph
    graph.py          ingest hasil tool, skor keyakinan, findings
    orchestrator.py   perencanaan job, worker thread, event bus
    cache.py          cache hasil tool dan ringkasan di SQLite
    ai.py             provider Groq atau OpenAI-compatible, retry dan backoff
    summary.py        ringkasan tiga lapis, redaksi PII, validasi sitasi
    reports.py        ekspor JSON, CSV, PDF, GraphML
frontend/             React 18 + TypeScript + Vite + Cytoscape
scripts/backup.py     arsip zip database dan folder unggahan
tests/                pytest
vercel.json           build frontend statis untuk Vercel
```

Penyimpanan default SQLite lewat SQLAlchemy. Worker berjalan sebagai thread di proses yang sama dan mengirim event ke klien melalui SSE.

## Kebutuhan

- Python 3.11 atau lebih baru.
- Node 18 atau lebih baru.
- SQLite (bawaan Python) atau PostgreSQL untuk beberapa penulis bersamaan.
- API key opsional: Groq, OpenAI, VirusTotal, Shodan, AbuseIPDB, Have I Been Pwned.

## Menjalankan lokal

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux atau macOS
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Build frontend sekali, lalu jalankan server:

```bash
cd frontend
npm install
npm run build
cd ..

python app.py
```

Buka <http://127.0.0.1:5000>. Flask menyajikan `frontend/dist` dan API dari origin yang sama, jadi tidak ada masalah CORS.

## Mode pengembangan

Dua terminal:

```bash
# terminal 1
python app.py

# terminal 2
cd frontend
npm run dev
```

Vite berjalan di <http://127.0.0.1:5173> dan mem-proxy `/api` ke <http://127.0.0.1:5000>.

Perintah frontend:

```bash
npm run build     # tsc --noEmit && vite build
npm run preview   # cek hasil build
```

## Environment variable

Salin `.env.example` menjadi `.env`. Jangan commit file `.env`.

| Variabel | Default | Keterangan |
| --- | --- | --- |
| `FLASK_ENV` | `development` | Set `production` untuk deployment. |
| `FLASK_DEBUG` | `false` | Jangan aktifkan di produksi. |
| `FLASK_SECRET_KEY` | kosong | Wajib di produksi. |
| `DATABASE_URL` | `sqlite:///berkas.db` | URL SQLAlchemy. |
| `UPLOAD_FOLDER` | `./uploads` | Folder bukti per kasus. |
| `MAX_CONTENT_LENGTH` | `16777216` | Batas ukuran request (16 MB). |
| `MAX_WORKERS` | `6` | Jumlah tool paralel per kasus. |
| `MAX_RUNS_PER_BATCH` | `12` | Batas tool yang dijalankan dalam satu batch. Sisanya ditunda. |
| `TOOL_CACHE_TTL` | `3600` | Umur cache hasil tool dalam detik. `0` mematikan cache. |
| `SUMMARY_CACHE_TTL` | `86400` | Umur cache ringkasan dalam detik. `0` mematikan cache. |
| `PUBLIC_REDACTION` | `true` | Samarkan sebagian PII pada ringkasan mode Awam. |
| `BERKAS_API_TOKEN` | kosong | Bila diisi, API butuh header `X-Berkas-Token` atau `?token=`. |
| `BERKAS_CORS_ORIGINS` | kosong | Origin frontend yang diizinkan, dipisahkan koma. Wajib untuk frontend Vercel. |
| `AI_PROVIDER` | `auto` | `auto`, `groq`, `openai`, `openai_compatible`, atau `none`. |
| `AI_MODEL` | kosong | Override model. Default Groq `openai/gpt-oss-20b`. |
| `AI_BASE_URL` | kosong | Endpoint HTTPS untuk provider OpenAI-compatible. |
| `AI_TIMEOUT_S` | `30` | Timeout satu permintaan AI. |
| `GROQ_API_KEY` | kosong | Ringkasan AI lewat Groq. Tanpa key, dipakai ringkasan lokal. |
| `OPENAI_API_KEY` | kosong | Ringkasan AI lewat OpenAI atau provider compatible. |
| `VT_API_KEY` | kosong | VirusTotal untuk `url_reputation`. |
| `SHODAN_API_KEY` | kosong | Shodan untuk `ip_shodan`. |
| `ABUSEIPDB_API_KEY` | kosong | AbuseIPDB untuk `ip_reputation`. |
| `HIBP_API_KEY` | kosong | Have I Been Pwned untuk `email_breach`. |

Frontend memakai `VITE_API_BASE` saat build. Kosongkan bila frontend dan backend satu origin. Untuk Vercel, isi dengan origin backend, misalnya `https://api.contoh.com`.

## Cara pakai

1. **Isi entity.** Tempel satu atau beberapa nilai, satu per baris. Format `label: nilai` juga dikenali, misalnya `email: budi@example.com`. Chip di bawah kolom menunjukkan tipe dan confidence hasil parser.
2. **Unggah bukti bila ada.** Seret file ke area unggah atau klik area tersebut. Maksimal 16 MB per file dan 8 file per unggahan.
3. **Isi detail kasus.** Judul, tujuan, dan dasar kewenangan bersifat opsional tetapi membantu audit.
4. **Buka berkas kasus.** Tool otomatis berjalan bila centang autorun aktif. Bila antrean melebihi batas batch, sisa job ditunda dan bisa dijalankan lagi dari panel kiri.
5. **Baca graph dan panel temuan.** Klik node untuk detail dan pivot. Panel kanan menyusun kandidat identitas, clue, peringatan, dan langkah berikutnya.
6. **Susun ringkasan.** Pilih mode Awam atau Analis, lalu baca poin dan sitasinya. Tombol mata mengatur tampilan PII.
7. **Ekspor bila perlu.** JSON, CSV, PDF, atau GraphML. Periksa kembali data sebelum dibagikan.

Pintasan: `Ctrl` atau `Cmd` + `Enter` membuka kasus dari kolom intake.

## Membaca hasil

Skor keyakinan dihitung dari bukti yang terkumpul, bukan dari satu tool.

| Band | Skor | Arti praktis |
| --- | --- | --- |
| High | 80 sampai 100 | Beberapa sumber independen saling menguatkan. Tetap periksa sitasi sebelum dipakai sebagai bukti formal. |
| Probable | 60 sampai 79 | Pola kuat, tetapi masih ada celah atau sumber yang belum dikonfirmasi. |
| Possible | 30 sampai 59 | Petunjuk awal. Perlakukan sebagai hipotesis yang perlu pivot tambahan. |
| Low | 0 sampai 29 | Bukti tipis atau bertentangan. Jangan jadikan dasar keputusan. |

Yang perlu diperiksa:

- **Bobot bukti.** Clue dengan bobot tinggi berasal dari sumber yang lebih langsung.
- **Peringatan.** Peringatan menyebut keterbatasan nyata, misalnya key yang belum diset atau sumber tunggal.
- **Konflik.** Bila dua sumber menyebut hal berbeda, keduanya dipertahankan.
- **Waktu.** Linimasa membantu melihat urutan kejadian, bukan membuktikan kausalitas.

## Ringkasan dan redaksi

Panel temuan punya dua mode:

- **Awam.** Menyamarkan sebagian email, telepon, NIK, dan NPWP. Data diredaksi sebelum dikirim ke provider AI dan dicek lagi pada output.
- **Analis.** Menampilkan data penuh dan lampiran teknis.

Ringkasan disusun dari data kasus, bukan dari pengetahuan umum model. Setiap poin membawa ID sitasi yang bisa dicocokkan dengan daftar bukti. Bila provider AI tidak tersedia atau gagal, ringkasan disusun lokal.

Redaksi mengurangi paparan, bukan menghapus kewajiban hukum.

## Tool yang tersedia

| ID | Label | Input | Key |
| --- | --- | --- | --- |
| domain_rdap | RDAP domain | domain | - |
| domain_dns | DNS records | domain | - |
| domain_ssl | TLS certificate | domain | - |
| domain_http | HTTP fingerprint | domain | - |
| domain_crtsh | Certificate transparency | domain | - |
| domain_wayback | Wayback snapshots | domain | - |
| ip_geo | IP geolocation | ip | - |
| ip_reputation | IP reputation | ip | ABUSEIPDB_API_KEY |
| ip_shodan | Shodan host | ip | SHODAN_API_KEY |
| email_intel | Email intelligence | email | - |
| email_breach | Breach check | email | HIBP_API_KEY |
| phone_intel | Phone intelligence | phone | - |
| nik_parse | NIK parser | nik | - |
| npwp_parse | NPWP parser | npwp | - |
| username_enum | Username enumeration | username | - |
| person_search | Person search | person, email, username | - |
| pddikti | PDDikti | person, nim | - |
| paste_search | Paste sites | email, username, domain | - |
| github_user | GitHub profile | username, email | - |
| public_profiles | Public profiles | username | - |
| crypto_btc | Bitcoin address | btc | - |
| mac_vendor | MAC vendor | mac | - |
| youtube_intel | YouTube metadata | url | - |
| shortlink_expand | Expand shortlink | url | - |
| url_reputation | URL reputation | url | VT_API_KEY |

Tool tanpa key tetap berjalan. Tool dengan key yang belum diset mengembalikan status `missing_key` dan muncul sebagai peringatan, bukan hasil palsu.

## Format file

Format yang dibaca: PNG, JPG, WEBP, GIF, PDF, DOCX, XLSX, CSV, JSON, TXT, MD, dan LOG.

- Maksimal 16 MB per file.
- Maksimal 8 file per unggahan.
- File disimpan per kasus di folder unggahan backend.
- Menghapus kasus juga menghapus folder unggahannya.

Metadata EXIF dan properti dokumen bisa mengandung lokasi atau identitas. Periksa sebelum membagikan hasil ekspor.

## API

Semua endpoint di bawah `/api/v1`. Bila `BERKAS_API_TOKEN` diisi, kirim header `X-Berkas-Token` atau parameter `?token=`. Header lama `X-Nexus-Token` masih diterima untuk kompatibilitas. Endpoint `/health` tetap terbuka.

| Method | Path | Fungsi |
| --- | --- | --- |
| GET | `/health` | Status, versi, jumlah tool, auth, dan statistik cache. |
| GET | `/keys/health` | Status key tanpa nilai rahasia, provider AI, TTL cache, batas batch. |
| GET | `/tools` | Daftar tool, input, dan status key. |
| POST | `/intake/parse` | Pecah teks menjadi entity dan rencana tool. |
| GET | `/cases` | Daftar kasus. |
| POST | `/cases` | Buat kasus dari `text` dan/atau `entities`. |
| GET | `/cases/<id>` | Detail kasus. |
| DELETE | `/cases/<id>` | Hapus kasus, graph, dan folder unggahan. |
| POST | `/cases/<id>/entities` | Tambah satu entity. |
| POST | `/cases/<id>/runs` | Jalankan tool yang belum selesai. |
| POST | `/cases/<id>/pivot` | Jalankan satu tool untuk satu entity. |
| POST | `/cases/<id>/files` | Unggah sampai 8 file. |
| GET | `/cases/<id>/graph` | Node, edge, findings, dan run. |
| GET | `/cases/<id>/findings` | Panel temuan. |
| GET | `/cases/<id>/summary?audience=public` | Ringkasan tiga lapis. `audience` `public` atau `analyst`, `refresh=1` memaksa susun ulang. |
| GET | `/cases/<id>/events` | SSE: `run.started`, `run.finished`, `graph.updated`, `findings.updated`, `runs.completed`. |
| GET | `/cases/<id>/export?format=` | `json`, `csv`, `pdf`, atau `graphml`. |

Contoh:

```bash
curl -s http://127.0.0.1:5000/api/v1/health

curl -s -X POST http://127.0.0.1:5000/api/v1/cases \
  -H "Content-Type: application/json" \
  -H "X-Berkas-Token: token-kamu" \
  -d '{"text":"email: budi@example.com\nusername: budi_s","autorun":true}'
```

## Ekspor

| Format | Isi |
| --- | --- |
| JSON | Kasus, findings, ringkasan awam, dan metadata ekspor. |
| CSV | Zip berisi entity, edge, evidence, run, dan findings. |
| PDF | Ringkasan awam dan tabel temuan. |
| GraphML | Graph untuk aplikasi graph eksternal. |

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest tests -q
```

Test mencakup parser entity, auth token, pembuatan kasus, pivot yang tidak valid, upload CSV, pembersihan folder saat kasus dihapus, keempat format ekspor, guard SSRF termasuk `domain_ssl` dan resolusi host, cache tool dan ringkasan, redaksi PII, validasi sitasi AI, serta endpoint ringkasan dan status kunci.

Frontend:

```bash
cd frontend
npm run build
```

## Docker

```bash
cp .env.example .env
# isi FLASK_SECRET_KEY dan token atau key yang dipakai
docker compose up --build
```

Compose menyimpan database dan unggahan di volume `berkas-data`, memakai Gunicorn di dalam container, dan memeriksa `/api/v1/health` sebagai health check.

Build manual:

```bash
docker build -t berkas .

docker run --rm -p 5000:5000 \
  -e FLASK_ENV=production \
  -e FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')" \
  -e BERKAS_API_TOKEN="token-panjang-acak" \
  -v berkas-data:/data \
  berkas
```

## Deploy Vercel

Vercel hanya menjalankan frontend. Backend Flask membutuhkan proses yang hidup, SQLite yang persisten, worker thread, dan koneksi SSE. Tiga hal itu tidak tersedia di serverless Vercel.

Artinya deployment Vercel yang berfungsi terdiri dari dua bagian:

1. **Frontend statis di Vercel.** `vercel.json` menjalankan `npm ci` dan `npm run build` di folder `frontend`, lalu menyajikan `frontend/dist`.
2. **Backend di host persisten.** Docker, VPS, Render, Fly, atau layanan lain yang mendukung proses panjang dan volume.

Langkah:

1. Deploy backend lebih dulu dan pastikan `https://api.contoh.com/api/v1/health` merespons.
2. Set environment backend:
   - `FLASK_ENV=production`
   - `FLASK_SECRET_KEY` acak
   - `BERKAS_API_TOKEN` bila API perlu dilindungi
   - `BERKAS_CORS_ORIGINS=https://nama-proyek.vercel.app`
   - `DATABASE_URL` dan `UPLOAD_FOLDER` ke volume persisten
3. Set environment Vercel:
   - `VITE_API_BASE=https://api.contoh.com`
4. Deploy ulang frontend. Vercel membaca `VITE_API_BASE` saat build.
5. Buka halaman, cek status backend, lalu jalankan satu kasus percobaan.

Tanpa `VITE_API_BASE`, halaman dan dokumentasi tetap terbuka, tetapi intake menampilkan pesan bahwa backend belum terhubung.

Catatan:

- Origin di `BERKAS_CORS_ORIGINS` harus sama persis, tanpa garis miring di akhir.
- SSE lewat reverse proxy perlu buffering dimatikan. Untuk Nginx, set `proxy_buffering off` pada lokasi `/api/`.
- Jangan menaruh database SQLite di filesystem serverless. Data akan hilang antar request.

## Deploy backend

Contoh dengan Gunicorn di container Linux:

```bash
export FLASK_ENV=production
export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export BERKAS_API_TOKEN="token-panjang-acak"
export BERKAS_CORS_ORIGINS="https://nama-proyek.vercel.app"
gunicorn --workers 2 --threads 8 --timeout 120 --bind 0.0.0.0:5000 "berkas.app:create_app()"
```

Catatan skala:

- Worker thread dan event bus bersifat in-process. Satu instance melayani satu kumpulan kasus.
- Untuk beberapa instance, ganti `berkas/services/orchestrator.py` dengan antrean eksternal (Redis + RQ atau Celery) dan ganti SQLite dengan PostgreSQL.
- Set `DATABASE_URL` ke PostgreSQL bila beberapa proses menulis bersamaan.
- Simpan `UPLOAD_FOLDER` di volume persisten.
- Batasi akses dengan `BERKAS_API_TOKEN` bila instance terbuka ke internet.

## Backup dan restore

```bash
python scripts/backup.py --output backups
```

Skrip memakai API backup SQLite agar salinan konsisten, lalu membungkus database dan folder unggahan ke satu file zip. Jalankan saat server sepi atau hentikan container lebih dulu bila volume sedang sibuk.

Restore:

1. Hentikan backend.
2. Ekstrak zip.
3. Letakkan `berkas.db` sesuai `DATABASE_URL` dan folder `uploads` sesuai `UPLOAD_FOLDER`.
4. Jalankan backend dan cek satu kasus.

## Troubleshooting

**Ringkasan AI gagal dengan HTTP 404.**
Model default Groq adalah `openai/gpt-oss-20b`. Bila model berubah atau dihentikan, set `AI_MODEL` ke model yang tersedia di akunmu. Tanpa key atau saat provider gagal, ringkasan lokal tetap dipakai.

**Tool menampilkan `missing_key`.**
Isi key yang disebut pada tool tersebut di `.env`, lalu restart backend. Status key bisa dicek dari tombol kunci di header.

**SSE terus menyambung ulang.**
Reverse proxy mungkin membuffer response. Matikan buffering untuk `/api/`, atau jalankan backend langsung tanpa proxy saat pengujian.

**Intake di Vercel bilang backend belum terhubung.**
Set `VITE_API_BASE` di environment Vercel, lalu deploy ulang. Pastikan origin frontend ada di `BERKAS_CORS_ORIGINS` backend.

**401 unauthorized.**
Isi token yang sama dengan `BERKAS_API_TOKEN` lewat tombol kunci di header. Token disimpan di `localStorage` browser.

**SQLite locked.**
Jalankan satu instance saja, atau pindah ke PostgreSQL dengan `DATABASE_URL`.

**Port 5000 sudah dipakai.**
Hentikan proses lain atau jalankan Flask di port berbeda, lalu sesuaikan proxy Vite.

## Migrasi nama

Versi sebelumnya memakai nama Nexus. Perubahan yang dilakukan:

- Paket Python `nexus/` menjadi `berkas/`.
- Environment `NEXUS_API_TOKEN` menjadi `BERKAS_API_TOKEN`. Nama lama masih dibaca bila nama baru kosong.
- Header `X-Nexus-Token` menjadi `X-Berkas-Token`. Header lama masih diterima.
- Database default `nexus_osint.db` menjadi `berkas.db`. Bila `berkas.db` belum ada dan file lama masih ada, file lama diganti nama otomatis saat backend mulai.
- Volume Docker `nexus-data` menjadi `berkas-data`.
- Key `localStorage` `nexus.token` dan `nexus.theme` menjadi `berkas.token` dan `berkas.theme`. Token perlu diisi ulang sekali.

Database versi 1 (`scan_history`, `api_keys`, `scan_logs`) tidak dipakai lagi. File `nexus_osint.legacy.db` dipertahankan sebagai arsip dan diabaikan aplikasi.

## Struktur repositori

```text
.
├── app.py
├── berkas/
├── frontend/
├── scripts/backup.py
├── tests/
├── .github/workflows/ci.yml
├── Dockerfile
├── docker-compose.yml
├── vercel.json
├── .env.example
└── README.md
```

## Kredit

Dibuat oleh **Zulmatoriq (zyelda)**.

- GitHub: <https://github.com/zyelda>
- Repositori: <https://github.com/zyelda/nexus-osint>

Repositori ini belum menyertakan file lisensi. Hubungi pembuat sebelum memakai ulang di luar konteks yang diizinkan.
