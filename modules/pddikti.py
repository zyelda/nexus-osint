import requests
import urllib3
import re
import json
from requests.exceptions import ConnectionError, Timeout, RequestException

# Matikan warning SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class PDDiktiWrapper:
    """
    Implementasi Ringan berdasarkan Dokumentasi pddiktipy
    Khusus untuk deployment Vercel (Tanpa dependency berat)
    """
    def __init__(self):
        self.base_url = "https://api-frontend.kemdikbud.go.id"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://pddikti.kemdikbud.go.id/",
            "Origin": "https://pddikti.kemdikbud.go.id",
            "Accept": "application/json, text/plain, */*",
            "X-Forwarded-For": "103.190.46.12" 
        }

    def search_mahasiswa(self, keyword):
        """Implementasi endpoint /hit_mhs/"""
        endpoint = f"{self.base_url}/hit_mhs/{keyword}"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=False, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data.get('mahasiswa', [])
        except:
            return []
        return []

    def get_detail_mhs(self, id_mahasiswa):
        """Implementasi endpoint /detail_mhs/ sesuai dokumentasi"""
        endpoint = f"{self.base_url}/detail_mhs/{id_mahasiswa}"
        try:
            response = requests.get(endpoint, headers=self.headers, verify=False, timeout=5)
            if response.status_code == 200:
                return response.json()
        except:
            return None
        return None

def search_mahasiswa(target):
    client = PDDiktiWrapper()
    clean_target = target.strip()
    
    output = {}
    
    try:
        # 1. Lakukan Pencarian Dasar
        raw_results = client.search_mahasiswa(clean_target)
        
        if not raw_results:
            # Fallback jika API kosong/blokir
            raise ConnectionError("No Data / Blocked")

        # 2. Parsing Hasil Pencarian
        parsed_list = []
        target_id_for_detail = None
        
        # Regex parser (seperti sebelumnya)
        regex_pattern = r"^(.*?)\((.*?)\)\s?(.*?),\s?(.*)$"

        for mhs in raw_results:
            text = mhs.get('text', '')
            website_link = mhs.get('website-link', '')
            mhs_id = website_link.split('/')[-1] if website_link else None
            
            match = re.search(regex_pattern, text)
            
            item = {
                "Nama": match.group(1).strip() if match else text,
                "NIM": match.group(2).strip() if match else "-",
                "Kampus": match.group(3).strip() if match else "-",
                "Prodi": match.group(4).strip() if match else "-",
                "Link": f"https://pddikti.kemdikbud.go.id{website_link}",
                "ID_System": mhs_id
            }
            parsed_list.append(item)

            # Logika Cerdas: Jika NIM target cocok persis, simpan ID untuk deep scan
            if clean_target.lower() in item['NIM'].lower() or clean_target.lower() == item['Nama'].lower():
                target_id_for_detail = mhs_id

        # 3. DEEP DIVE (Fitur Baru dari Dokumentasi)
        # Jika hasil cuma 1 atau NIM cocok, ambil detail lengkapnya!
        detail_data = None
        if len(parsed_list) == 1:
            target_id_for_detail = parsed_list[0]['ID_System']
        
        if target_id_for_detail:
            detail_raw = client.get_detail_mhs(target_id_for_detail)
            if detail_raw:
                # Format Data Detail agar cantik di tabel
                detail_data = {
                    "STATUS SAAT INI": detail_raw.get('status_saat_ini', '-'),
                    "Angkatan": detail_raw.get('tahun_masuk', '-'),
                    "Jenis Kelamin": detail_raw.get('jenis_kelamin', '-'),
                    "Tempat/Tgl Lahir": f"{detail_raw.get('tempat_lahir','-')}, {detail_raw.get('tanggal_lahir','-')}",
                    "Jenjang": detail_raw.get('jenjang', '-'),
                    "Nomor Ijazah": detail_raw.get('nomor_seri_ijazah', 'Belum Lulus'),
                }

        # 4. Susun Output Akhir
        if detail_data:
            # Jika dapat detail, taruh di paling atas
            output["🔥 DETAIL MENDALAM (Deep Scan)"] = detail_data
        
        output["Hasil Pencarian"] = parsed_list[:10] # Ambil 10 teratas
        output["Info"] = f"Ditemukan {len(parsed_list)} data relevan."

    except Exception as e:
        # FALLBACK MODE (Google Dorks)
        google_link = f"https://www.google.com/search?q=site:pddikti.kemdikbud.go.id/data_mahasiswa/+{clean_target}"
        output["Status"] = "Akses API Terbatas / Tidak Ditemukan"
        output["Saran"] = "Gunakan Link Manual di bawah ini:"
        output["Link"] = google_link

    return output