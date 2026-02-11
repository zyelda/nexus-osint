from duckduckgo_search import DDGS
import urllib.parse

def scan_person_name(target):
    results = {}
    clean_target = target.strip()
    safe_target = urllib.parse.quote(clean_target)
    
    print(f"[*] Mencari jejak digital: {clean_target}...")
    
    found_links = []
    
    try:
        with DDGS() as ddgs:
            print("    > Menghubungi DuckDuckGo...")
            ddg_gen = ddgs.text(
                keywords=clean_target, 
                region='id-id', 
                safesearch='off', 
                timelimit='y',
                max_results=10
            )
            
            search_results = list(ddg_gen)
            
            if search_results:
                for res in search_results:
                    if res.get('title') and res.get('href'):
                        found_links.append({
                            "Kategori": "HASIL",
                            "Judul": res['title'],
                            "Link": res['href'],
                            "Deskripsi": res['body'][:100] + "..." if res.get('body') else "Klik untuk baca selengkapnya."
                        })
            else:
                print("    > Hasil scraping kosong (Mungkin Rate Limit).")

    except Exception as e:
        print(f"[!] Scraping Error: {e}")

    if len(found_links) < 3:
        print("    > Mengaktifkan Backup Links...")
        
        found_links.append({
            "Kategori": "🔍 AKSES LANGSUNG",
            "Judul": f"Cari '{clean_target}' di Google News",
            "Link": f"https://www.google.com/search?q={safe_target}&tbm=nws",
            "Deskripsi": "Klik link ini untuk melihat berita terbaru secara real-time."
        })
        
        found_links.append({
            "Kategori": "📸 AKSES LANGSUNG",
            "Judul": f"Cari Foto '{clean_target}' di Google Images",
            "Link": f"https://www.google.com/search?q={safe_target}&tbm=isch",
            "Deskripsi": "Lihat galeri foto terkait target."
        })

        found_links.append({
            "Kategori": "videos AKSES LANGSUNG",
            "Judul": f"Cari Video '{clean_target}' di YouTube",
            "Link": f"https://www.youtube.com/results?search_query={safe_target}",
            "Deskripsi": "Cek apakah ada video vlog atau berita terkait target."
        })
        
        found_links.append({
            "Kategori": "📄 AKSES LANGSUNG",
            "Judul": "Cari Dokumen PDF (SK/Surat)",
            "Link": f"https://www.google.com/search?q={safe_target}+filetype:pdf",
            "Deskripsi": "Mencari file resmi yang bocor atau dipublikasikan."
        })

    results["Jejak Digital"] = found_links
    results["Total Data"] = f"{len(found_links)} (Termasuk Link Akses)"
    
    if len(found_links) > 5:
        results["Status"] = "Target Ditemukan Popular"
        results["Info"] = "Banyak artikel/berita yang membahas nama ini."
    else:
        results["Status"] = "Pencarian Terbatas / Manual Mode"
        results["Info"] = "Scraping otomatis terbatas. Gunakan Link Akses Langsung di tabel untuk hasil akurat."

    return results