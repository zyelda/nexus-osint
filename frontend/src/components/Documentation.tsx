import { backendConfigured } from '../api';
import type { ToolSpec } from '../types';
import { CloseIcon, ExternalIcon } from './Icons';

interface DocumentationProps {
  tools: ToolSpec[];
  onBack: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  domain: 'Domain',
  network: 'Jaringan',
  identity: 'Identitas',
  breach: 'Kebocoran data',
  social: 'Sosial',
  finance: 'Finansial',
  media: 'Media',
  reputation: 'Reputasi',
  academic: 'Akademik',
};

const ENDPOINTS = [
  ['GET', '/health', 'Status server, versi, jumlah tool, dan statistik cache.'],
  ['GET', '/keys/health', 'Status key tanpa menampilkan nilainya, provider AI, dan batas batch.'],
  ['GET', '/tools', 'Daftar tool, tipe input, dan status key.'],
  ['POST', '/intake/parse', 'Pecah teks menjadi entity dan rencana tool.'],
  ['GET', '/cases', 'Daftar kasus yang tersimpan.'],
  ['POST', '/cases', 'Buat kasus dari teks, entity eksplisit, atau keduanya.'],
  ['GET', '/cases/<id>', 'Detail satu kasus.'],
  ['DELETE', '/cases/<id>', 'Hapus kasus, graph, bukti, dan folder unggahan.'],
  ['POST', '/cases/<id>/entities', 'Tambah satu entity ke kasus.'],
  ['POST', '/cases/<id>/runs', 'Jalankan tool yang belum selesai untuk kasus.'],
  ['POST', '/cases/<id>/pivot', 'Jalankan satu tool untuk satu entity.'],
  ['POST', '/cases/<id>/files', 'Unggah sampai 8 file bukti.'],
  ['GET', '/cases/<id>/graph', 'Node, edge, findings, dan status run.'],
  ['GET', '/cases/<id>/findings', 'Panel temuan tanpa data graph penuh.'],
  ['GET', '/cases/<id>/summary', 'Ringkasan tiga lapis. Parameter audience public atau analyst.'],
  ['GET', '/cases/<id>/events', 'Server-Sent Events untuk perubahan graph dan status run.'],
  ['GET', '/cases/<id>/export', 'Ekspor json, csv, pdf, atau graphml.'],
];

export function Documentation({ tools, onBack }: DocumentationProps) {
  const categories = Array.from(new Set(tools.map((tool) => tool.category))).sort();

  return (
    <main className="docs">
      <header className="docs-head">
        <div>
          <p className="eyebrow">Panduan penggunaan</p>
          <h1 className="docs-title">Dokumentasi Berkas</h1>
          <p className="docs-lede">
            Berkas adalah workspace investigasi sumber publik. Panduan ini menjelaskan cara memakai aplikasi,
            membaca hasil, menjalankan sendiri, dan menghubungkan frontend Vercel ke backend.
          </p>
        </div>
        <button type="button" className="btn" onClick={onBack}>
          <CloseIcon size={16} />
          Kembali ke aplikasi
        </button>
      </header>

      {!backendConfigured && (
        <div className="notice notice-warn" role="status">
          <strong>Backend belum terhubung.</strong> Deployment statis ini belum punya alamat API. Isi
          <code> VITE_API_BASE </code>
          di environment Vercel, lalu deploy ulang. Bagian <a href="#docs-vercel">Vercel</a> menjelaskan urutannya.
        </div>
      )}

      <div className="docs-layout">
        <nav className="docs-toc" aria-label="Daftar isi dokumentasi">
          <span className="file-tab">Daftar isi</span>
          <ol>
            <li>
              <a href="#docs-apa">Apa itu Berkas</a>
            </li>
            <li>
              <a href="#docs-mulai">Mulai satu kasus</a>
            </li>
            <li>
              <a href="#docs-hasil">Membaca hasil</a>
            </li>
            <li>
              <a href="#docs-ringkasan">Ringkasan dan redaksi</a>
            </li>
            <li>
              <a href="#docs-tools">Daftar tool</a>
            </li>
            <li>
              <a href="#docs-berkas">File dan batas ukuran</a>
            </li>
            <li>
              <a href="#docs-api">API</a>
            </li>
            <li>
              <a href="#docs-jalan">Menjalankan sendiri</a>
            </li>
            <li>
              <a href="#docs-vercel">Deploy Vercel</a>
            </li>
            <li>
              <a href="#docs-batas">Batas penggunaan</a>
            </li>
            <li>
              <a href="#docs-kredit">Kredit</a>
            </li>
          </ol>
        </nav>

        <div className="docs-body">
          <section id="docs-apa" className="docs-section">
            <span className="file-tab">01</span>
            <h2>Apa itu Berkas</h2>
            <p>
              Berkas menerima nama, email, nomor telepon, username, domain, URL, IP, NIK, NPWP, NIM, alamat Bitcoin,
              atau MAC dalam satu intake. Parser menandai tipe dan nilai ternormalisasi, lalu tool yang relevan
              berjalan untuk membangun graph koneksi.
            </p>
            <p>
              Setiap temuan membawa sumber, bobot bukti, tingkat keyakinan, dan peringatan batasan data. Aplikasi tidak
              menjual kesimpulan dan tidak mengubah hipotesis menjadi fakta. Kamu tetap memutuskan langkah berikutnya.
            </p>
            <div className="docs-split">
              <div>
                <h3>Cocok untuk</h3>
                <ul>
                  <li>Verifikasi vendor atau domain sebelum transaksi.</li>
                  <li>Pemetaan jejak publik satu identitas atau organisasi.</li>
                  <li>Pemeriksaan metadata dokumen dan gambar yang diunggah.</li>
                  <li>Penyusunan ringkasan yang bisa disitasi untuk laporan internal.</li>
                </ul>
              </div>
              <div>
                <h3>Tidak untuk</h3>
                <ul>
                  <li>Mencari pemilik NIK, NPWP, atau nomor telepon.</li>
                  <li>Face recognition atau pencocokan wajah.</li>
                  <li>Membuka akun di balik login atau membeli data bocor.</li>
                  <li>Memindai port target tanpa izin.</li>
                </ul>
              </div>
            </div>
          </section>

          <section id="docs-mulai" className="docs-section">
            <span className="file-tab">02</span>
            <h2>Mulai satu kasus</h2>
            <ol className="docs-steps">
              <li>
                <strong>Isi entity.</strong> Tempel satu atau beberapa nilai, satu per baris. Format
                <code> label: nilai </code>
                juga dikenali, misalnya <code>email: budi@example.com</code>. Chip di bawah kolom menunjukkan tipe dan
                confidence hasil parser.
              </li>
              <li>
                <strong>Unggah bukti bila ada.</strong> Seret file ke area unggah atau klik area tersebut. Metadata,
                EXIF GPS, dan entity di dalam dokumen masuk ke graph yang sama.
              </li>
              <li>
                <strong>Isi detail kasus.</strong> Judul, tujuan, dan dasar kewenangan bersifat opsional tetapi
                membantu audit. Isi dasar kewenangan sebelum memakai tool yang menyentuh data pribadi.
              </li>
              <li>
                <strong>Buka berkas kasus.</strong> Tool otomatis berjalan bila centang autorun aktif. Bila antrean
                melebihi batas batch, sisa job ditunda dan bisa dijalankan lagi dari panel kiri.
              </li>
              <li>
                <strong>Baca graph dan panel temuan.</strong> Klik node untuk melihat detail dan pivot yang tersedia.
                Panel kanan menyusun kandidat identitas, clue, peringatan, dan langkah berikutnya.
              </li>
            </ol>
            <p className="docs-note">
              Pintasan: <kbd>Ctrl</kbd> atau <kbd>Cmd</kbd> + <kbd>Enter</kbd> membuka kasus dari kolom intake.
            </p>
          </section>

          <section id="docs-hasil" className="docs-section">
            <span className="file-tab">03</span>
            <h2>Membaca hasil</h2>
            <p>
              Skor keyakinan dihitung dari bukti yang terkumpul, bukan dari satu tool. Angka dan alasannya ditampilkan
              bersama agar bisa diperiksa.
            </p>
            <table className="docs-table">
              <thead>
                <tr>
                  <th>Band</th>
                  <th>Skor</th>
                  <th>Arti praktis</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>High</td>
                  <td className="mono">80 sampai 100</td>
                  <td>Beberapa sumber independen saling menguatkan. Tetap periksa sitasi sebelum dipakai sebagai bukti formal.</td>
                </tr>
                <tr>
                  <td>Probable</td>
                  <td className="mono">60 sampai 79</td>
                  <td>Pola kuat, tetapi masih ada celah atau sumber yang belum dikonfirmasi.</td>
                </tr>
                <tr>
                  <td>Possible</td>
                  <td className="mono">30 sampai 59</td>
                  <td>Petunjuk awal. Perlakukan sebagai hipotesis yang perlu pivot tambahan.</td>
                </tr>
                <tr>
                  <td>Low</td>
                  <td className="mono">0 sampai 29</td>
                  <td>Bukti tipis atau bertentangan. Jangan jadikan dasar keputusan.</td>
                </tr>
              </tbody>
            </table>
            <h3>Yang perlu diperiksa</h3>
            <ul>
              <li>
                <strong>Bobot bukti.</strong> Clue dengan bobot tinggi berasal dari sumber yang lebih langsung.
              </li>
              <li>
                <strong>Peringatan.</strong> Peringatan menyebut keterbatasan nyata, misalnya key yang belum diset
                atau sumber tunggal.
              </li>
              <li>
                <strong>Konflik.</strong> Bila dua sumber menyebut hal berbeda, keduanya dipertahankan. Jangan pilih
                yang paling nyaman.
              </li>
              <li>
                <strong>Waktu.</strong> Linimasa membantu melihat urutan kejadian, bukan membuktikan kausalitas.
              </li>
            </ul>
          </section>

          <section id="docs-ringkasan" className="docs-section">
            <span className="file-tab">04</span>
            <h2>Ringkasan dan redaksi</h2>
            <p>
              Panel temuan punya dua mode. Mode Awam menyamarkan sebagian email, telepon, NIK, dan NPWP. Mode Analis
              menampilkan data penuh dan lampiran teknis. Tombol mata pada panel mengatur tampilan data.
            </p>
            <ul>
              <li>Ringkasan disusun dari data kasus, bukan dari pengetahuan umum model.</li>
              <li>Setiap poin membawa ID sitasi yang bisa dicocokkan dengan daftar bukti.</li>
              <li>Bila provider AI tidak tersedia atau gagal, ringkasan disusun lokal. Hasilnya tetap bisa dipakai.</li>
              <li>Data yang dikirim ke provider AI sudah diredaksi lebih dulu pada mode Awam.</li>
            </ul>
            <p className="docs-note">
              Redaksi mengurangi paparan, bukan menghapus kewajiban hukum. Jangan unggah data yang tidak berhak kamu
              proses.
            </p>
          </section>

          <section id="docs-tools" className="docs-section">
            <span className="file-tab">05</span>
            <h2>Daftar tool</h2>
            <p>
              Tool yang tampil di bawah dibaca langsung dari registry backend. Tool tanpa key tetap berjalan. Tool
              dengan key yang belum diset akan ditandai dan mengembalikan status <code>missing_key</code>, bukan hasil
              palsu.
            </p>
            {tools.length === 0 ? (
              <div className="empty-block" role="status">
                <strong>Daftar tool belum tersedia</strong>
                Backend belum terhubung atau permintaan daftar tool gagal. Dokumentasi lain tetap bisa dibaca.
              </div>
            ) : (
              categories.map((category) => (
                <div className="docs-tool-group" key={category}>
                  <h3>{CATEGORY_LABELS[category] ?? category}</h3>
                  <table className="docs-table">
                    <thead>
                      <tr>
                        <th>Tool</th>
                        <th>Input</th>
                        <th>Key</th>
                      </tr>
                    </thead>
                    <tbody>
                      {tools
                        .filter((tool) => tool.category === category)
                        .map((tool) => (
                          <tr key={tool.id}>
                            <td>
                              <strong>{tool.label}</strong>
                              <span className="docs-tool-id mono">{tool.id}</span>
                              <span className="docs-tool-desc">{tool.description}</span>
                            </td>
                            <td className="mono">{tool.inputs.join(', ') || '-'}</td>
                            <td>
                              {tool.requires_key ? (
                                <span className={tool.configured ? 'docs-key ready' : 'docs-key'}>
                                  {tool.configured ? 'siap' : tool.requires_key}
                                </span>
                              ) : (
                                <span className="docs-key ready">tanpa key</span>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ))
            )}
          </section>

          <section id="docs-berkas" className="docs-section">
            <span className="file-tab">06</span>
            <h2>File dan batas ukuran</h2>
            <p>Format yang dibaca: PNG, JPG, WEBP, GIF, PDF, DOCX, XLSX, CSV, JSON, TXT, MD, dan LOG.</p>
            <ul>
              <li>Maksimal 16 MB per file.</li>
              <li>Maksimal 8 file per unggahan.</li>
              <li>File disimpan per kasus di folder unggahan backend.</li>
              <li>Menghapus kasus juga menghapus folder unggahannya.</li>
            </ul>
            <p>
              Metadata EXIF dan properti dokumen bisa mengandung lokasi atau identitas. Periksa sebelum membagikan
              hasil ekspor.
            </p>
          </section>

          <section id="docs-api" className="docs-section">
            <span className="file-tab">07</span>
            <h2>API</h2>
            <p>
              Semua endpoint berada di bawah <code>/api/v1</code>. Bila backend memakai token, kirim header
              <code> X-Berkas-Token </code>
              atau parameter <code>?token=</code>. Endpoint <code>/health</code> tetap terbuka.
            </p>
            <table className="docs-table docs-table-api">
              <thead>
                <tr>
                  <th>Method</th>
                  <th>Path</th>
                  <th>Fungsi</th>
                </tr>
              </thead>
              <tbody>
                {ENDPOINTS.map(([method, path, description]) => (
                  <tr key={`${method}:${path}`}>
                    <td className="mono">{method}</td>
                    <td className="mono">{path}</td>
                    <td>{description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <pre className="docs-code">
              <code>{`curl -s http://127.0.0.1:5000/api/v1/health

curl -s -X POST http://127.0.0.1:5000/api/v1/cases \\
  -H "Content-Type: application/json" \\
  -H "X-Berkas-Token: token-kamu" \\
  -d '{"text":"email: budi@example.com","autorun":true}'`}</code>
            </pre>
          </section>

          <section id="docs-jalan" className="docs-section">
            <span className="file-tab">08</span>
            <h2>Menjalankan sendiri</h2>
            <p>Prasyarat: Python 3.11 atau lebih baru dan Node 18 atau lebih baru.</p>
            <pre className="docs-code">
              <code>{`python -m venv venv
venv\\Scripts\\activate        # Windows
source venv/bin/activate     # Linux atau macOS

pip install -r requirements.txt
cp .env.example .env

cd frontend
npm install
npm run build
cd ..

python app.py`}</code>
            </pre>
            <p>
              Buka <code>http://127.0.0.1:5000</code>. Flask menyajikan hasil build frontend dan API dari origin yang
              sama, jadi tidak perlu konfigurasi CORS.
            </p>
            <h3>Docker</h3>
            <pre className="docs-code">
              <code>{`cp .env.example .env
# isi FLASK_SECRET_KEY dan key yang dipakai
docker compose up --build`}</code>
            </pre>
            <p>
              Compose menyimpan database dan unggahan di volume <code>berkas-data</code>. Untuk produksi, set
              <code> FLASK_ENV=production </code>
              dan isi <code>FLASK_SECRET_KEY</code>.
            </p>
          </section>

          <section id="docs-vercel" className="docs-section">
            <span className="file-tab">09</span>
            <h2>Deploy Vercel</h2>
            <p>
              Vercel hanya menjalankan frontend. Backend Flask membutuhkan proses yang hidup, SQLite yang persisten,
              worker thread, dan koneksi SSE. Tiga hal itu tidak tersedia di serverless Vercel, jadi backend harus
              berjalan di Docker, VPS, Render, Fly, atau host lain yang mendukung proses panjang.
            </p>
            <ol className="docs-steps">
              <li>
                <strong>Deploy backend lebih dulu.</strong> Catat URL publiknya, misalnya
                <code> https://api.contoh.com</code>.
              </li>
              <li>
                <strong>Set CORS di backend.</strong> Isi
                <code> BERKAS_CORS_ORIGINS </code>
                dengan origin frontend, misalnya <code>https://berkas.vercel.app</code>. Beberapa origin dipisahkan
                koma.
              </li>
              <li>
                <strong>Set environment Vercel.</strong> Tambahkan
                <code> VITE_API_BASE </code>
                dengan URL backend, lalu deploy ulang. Nilai ini dibaca saat build.
              </li>
              <li>
                <strong>Deploy frontend.</strong> File <code>vercel.json</code> sudah mengarahkan build ke
                <code> frontend/dist</code>. Tidak perlu Root Directory khusus.
              </li>
            </ol>
            <p className="docs-note">
              Tanpa <code>VITE_API_BASE</code>, halaman dan dokumentasi tetap terbuka, tetapi intake akan menampilkan
              pesan bahwa backend belum terhubung.
            </p>
          </section>

          <section id="docs-batas" className="docs-section">
            <span className="file-tab">10</span>
            <h2>Batas penggunaan</h2>
            <p>Berkas hanya memakai sumber publik dan API resmi. Yang sengaja tidak dilakukan:</p>
            <ul>
              <li>Lookup pemilik nomor telepon, NIK, atau NPWP.</li>
              <li>Face recognition dan people-search scraper.</li>
              <li>Scraping halaman di balik login.</li>
              <li>Pemindaian port default. Data port hanya dibaca dari indeks Shodan bila key tersedia.</li>
              <li>Dark web.</li>
            </ul>
            <h3>Batas teknis</h3>
            <ul>
              <li>Satu instance melayani satu kumpulan kasus. Worker dan event bus berjalan di proses yang sama.</li>
              <li>SQLite cukup untuk satu instance. Untuk beberapa penulis bersamaan, pindah ke PostgreSQL.</li>
              <li>Batas batch default 12 tool. Sisanya ditunda, bukan dibuang.</li>
              <li>Cache tool default 1 jam dan cache ringkasan default 24 jam. Set ke 0 untuk mematikan.</li>
              <li>Skor keyakinan adalah alat bantu, bukan bukti identitas final.</li>
            </ul>
            <p>
              Gunakan hanya untuk tujuan yang sah dan dengan kewenangan yang jelas. Isi tujuan dan dasar kewenangan
              saat membuat kasus.
            </p>
          </section>

          <section id="docs-kredit" className="docs-section">
            <span className="file-tab">11</span>
            <h2>Kredit</h2>
            <p>
              Berkas dibuat oleh <strong>Zulmatoriq (zyelda)</strong>. Kode sumber, catatan rilis, dan panduan versi
              terbaru ada di GitHub.
            </p>
            <p>
              <a className="docs-link" href="https://github.com/zyelda/nexus-osint" target="_blank" rel="noreferrer">
                github.com/zyelda/nexus-osint
                <ExternalIcon size={14} />
              </a>
            </p>
            <p className="docs-note">
              Nama repositori masih memakai nama lama. Nama produk dan seluruh identifier internal sudah memakai
              Berkas.
            </p>
          </section>
        </div>
      </div>
    </main>
  );
}
