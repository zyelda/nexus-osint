# Nexus OSINT

**Nexus OSINT** adalah aplikasi web berbasis Python yang dirancang untuk melakukan pengumpulan intelijen sumber terbuka (*Open Source Intelligence*) secara otomatis. Aplikasi ini mengintegrasikan berbagai modul pemindaian dengan kecerdasan buatan (AI) untuk menganalisis jejak digital, mulai dari forensik gambar, pelacakan jaringan, hingga profil sosial.

## Daftar Isi

* [Fitur Utama](https://www.google.com/search?q=%23-fitur-utama)
* [Arsitektur & Teknologi](https://www.google.com/search?q=%23-arsitektur--teknologi)
* [Struktur Proyek](https://www.google.com/search?q=%23-struktur-proyek)
* [Instalasi & Menjalankan Lokal](https://www.google.com/search?q=%23-instalasi--menjalankan-lokal)
* [Konfigurasi Environment](https://www.google.com/search?q=%23-konfigurasi-environment)
* [Panduan Modul](https://www.google.com/search?q=%23-panduan-modul)
* [Deployment (Vercel)](https://www.google.com/search?q=%23%EF%B8%8F-deployment-vercel)
* [Disclaimer](https://www.google.com/search?q=%23-disclaimer)

---

## Fitur Utama

Aplikasi ini memiliki kemampuan *multi-vector scanning* yang mencakup:

* **Network Intel:** Whois Lookup, DNS Records, dan Geolokasi IP.
* **Social Profiling:** Username Check di berbagai platform media sosial.
* **Image Forensics:** Analisis Metadata (EXIF), Ekstraksi GPS, dan Deteksi Perangkat (menggunakan Pillow).
* **AI Analyst:** Analisa risiko otomatis dan ringkasan eksekutif menggunakan Groq (Llama 3).
* **Aviation Intel:** Pelacakan pesawat real-time/historis (menggunakan FlightRadarAPI).
* **Video Intel:** Ekstraksi transkrip dan metadata video YouTube (menggunakan youtube-transcript-api).
* **Academic Intel:** Pencarian data mahasiswa PDDikti (menggunakan custom wrapper).
* **Doc Forensics:** Analisis metadata dokumen PDF/Word.

---

## Arsitektur & Teknologi

* **Backend:** Python 3.9+ (Flask Microframework)
* **Frontend:** HTML5, CSS3, JavaScript (Bootstrap 5)
* **AI Engine:** Groq API (Model: Llama-3-70b-versatile)
* **Image Processing:** Pillow (PIL) - *Lightweight replacement for OpenCV*
* **Hosting:** Vercel (Serverless Function)

---

## Struktur Proyek

```text
Nexus_OSINT/
├── modules/                  # Kumpulan Logika Scanner
│   ├── __init__.py
│   ├── ai_analyst.py         # Integrasi Groq AI
│   ├── aviation.py           # FlightRadar24 Wrapper
│   ├── image_forensics.py    # PIL EXIF & GPS Extractor
│   ├── network.py            # IP & Domain Scanner
│   ├── username.py           # Social Media Checker
│   ├── youtube_intel.py      # YouTube Transcript API
│   ├── pddikti.py            # PDDikti Scraper
│   └── ... (modul lainnya)
├── static/                   # File Aset (CSS, JS, Images)
├── templates/                # File HTML (Jinja2)
│   └── index.html
├── app.py                    # Main Entry Point (Flask App)
├── requirements.txt          # Daftar Dependensi
├── vercel.json               # Konfigurasi Serverless Vercel
├── .gitignore                # Daftar file yang diabaikan Git
└── README.md                 # Dokumentasi ini

```

---

## Instalasi & Menjalankan Lokal

Ikuti langkah ini untuk menjalankan aplikasi di komputer kamu:

### 1. Clone Repository

```bash
git clone https://github.com/username-kamu/nexus-osint.git
cd nexus-osint

```

### 2. Buat Virtual Environment (Disarankan)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate

```

### 3. Install Dependensi

```bash
pip install -r requirements.txt

```

### 4. Setup API Key

Buat file `.env` di root folder (opsional untuk lokal) atau set langsung di terminal:

```bash
# Windows Powershell
$env:GROQ_API_KEY="gsk_xxxxx..."

# Mac/Linux
export GROQ_API_KEY="gsk_xxxxx..."

```

### 5. Jalankan Aplikasi

```bash
python app.py

```

Akses di browser: `http://127.0.0.1:5000`

---

## Konfigurasi Environment

Aplikasi ini membutuhkan **Environment Variables** agar berjalan dengan aman (terutama untuk API Key).

| Variable Name | Deskripsi | Wajib? |
| --- | --- | --- |
| `GROQ_API_KEY` | API Key dari Console Groq untuk fitur AI Analyst. | **YA** |
| `FLASK_ENV` | Set ke `development` saat coding, `production` saat deploy. | Tidak |

---

## Panduan Modul

### 1. AI Analyst (`modules/ai_analyst.py`)

Modul ini bertindak sebagai "otak" yang membaca hasil scan dari modul lain.

* **Input:** JSON Data dari hasil scan.
* **Proses:** Mengirim prompt ke LLM Llama-3 via Groq Cloud.
* **Output:** Narasi analisis risiko keamanan (Low/Medium/High).

### 2. Image Forensics (`modules/image_forensics.py`)

* **Teknologi:** Menggunakan library `Pillow` (PIL).
* **Fitur:** Mengekstrak `TAGS` dan `GPSTAGS`. Mengonversi koordinat GPS mentah (DMS) menjadi Desimal agar bisa dibuka di Google Maps.

### 3. Aviation (`modules/aviation.py`)

* **Teknologi:** `FlightRadarAPI`.
* **Fungsi:** Mencari informasi pesawat berdasarkan nomor registrasi atau nomor penerbangan.

### 4. YouTube Intel (`modules/youtube_intel.py`)

* **Teknologi:** `youtube-transcript-api`.
* **Fungsi:** Mengambil transkrip otomatis dari video YouTube untuk keperluan analisis teks tanpa harus menonton video.

---

## Deployment (Vercel)

Aplikasi ini dikonfigurasi untuk berjalan di **Vercel Serverless Functions**.

### Persyaratan File

Pastikan file-file ini ada sebelum deploy:

1. **`requirements.txt`**: Harus bersih dari library berat (seperti TensorFlow/OpenCV). Gunakan `Pillow`, `groq`, dll.
2. **`vercel.json`**:

```json
{
    "version": 2,
    "builds": [{"src": "app.py", "use": "@vercel/python"}],
    "routes": [{"src": "/(.*)", "dest": "app.py"}]
}

```

### Langkah Deploy

1. Push kode ke GitHub.
2. Import project di Dashboard Vercel.
3. Masuk ke **Settings > Environment Variables**.
4. Tambahkan: `GROQ_API_KEY` dengan value API Key kamu.
5. Klik **Deploy**.

---

## Disclaimer

> **PENGGUNAAN ALAT INI HANYA UNTUK TUJUAN EDUKASI DAN PENELITIAN KEAMANAN.**

Pengembang tidak bertanggung jawab atas penyalahgunaan alat ini untuk tindakan ilegal, doxing, atau pelanggaran privasi orang lain. Pastikan Anda memiliki izin atau otoritas sebelum melakukan pemindaian terhadap target tertentu.

---

*Dibuat dengan ❤️ dan Kopi oleh Zoelmatoriq*