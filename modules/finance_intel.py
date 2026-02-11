import requests
import urllib.parse

def scan_bitcoin_address(address):
    results = {}
    api_url = f"https://blockchain.info/rawaddr/{address}"
    try:
        r = requests.get(api_url)
        data = r.json()
        balance = data['final_balance'] / 100000000
        total_received = data['total_received'] / 100000000
        results['Address'] = address
        results['Current Balance'] = f"{balance} BTC"
        results['Total Received'] = f"{total_received} BTC"
        results['Total Transactions'] = data['n_tx']
        results['Last Activity'] = "Active Wallet" if data['n_tx'] > 0 else "Dead/Unused Wallet"
    except Exception as e:
        results['Error'] = "Gagal mengambil data blockchain."
    return results

def scan_mac_address(mac):
    api_url = f"https://api.macvendors.com/{mac}"
    try:
        r = requests.get(api_url)
        return {"Vendor/Pabrikan": r.text, "MAC": mac} if r.status_code == 200 else {"Vendor": "Unknown", "MAC": mac}
    except:
        return {"Error": "Connection Failed"}

def generate_dorks(target):
    dorks = {}
    
    safe_target = urllib.parse.quote(target)
    
    is_domain = "." in target and " " not in target and "@" not in target

    if is_domain:
        dorks = {
            "Cari Subdomain Tersembunyi": f"https://www.google.com/search?q=site:*.{safe_target} -www",
            "Cari File Sensitif (PDF/DOC/XLS)": f"https://www.google.com/search?q=site:{safe_target} filetype:pdf OR filetype:docx OR filetype:xlsx OR filetype:pptx",
            "Cari Folder Terbuka (Index Of)": f"https://www.google.com/search?q=site:{safe_target} intitle:\"index of\"",
            "Cari Halaman Login/Admin": f"https://www.google.com/search?q=site:{safe_target} inurl:login OR inurl:admin OR inurl:portal",
            "Cari Error SQL / Database": f"https://www.google.com/search?q=site:{safe_target} intext:\"sql syntax near\" OR intext:\"syntax error\"",
            "Cari di Pastebin (Data Bocor)": f"https://www.google.com/search?q=site:pastebin.com \"{safe_target}\""
        }
    
    else:
        dorks = {
            "PENCARIAN TOTAL (Semua Web)": f"https://www.google.com/search?q=\"{safe_target}\"",
            
            "Cari di Dalam Teks Website (Intext)": f"https://www.google.com/search?q=intext:\"{safe_target}\"",
            
            "Cari di Judul Artikel/Berita (Intitle)": f"https://www.google.com/search?q=intitle:\"{safe_target}\"",
            
            "Cari di Sosial Media (FB/Twitter/IG/TikTok)": f"https://www.google.com/search?q=site:facebook.com OR site:twitter.com OR site:instagram.com OR site:tiktok.com OR site:linkedin.com \"{safe_target}\"",
            
            "Cari di Forum Diskusi (Reddit/Kaskus/Quora)": f"https://www.google.com/search?q=site:reddit.com OR site:quora.com OR site:kaskus.co.id \"{safe_target}\"",
            
            "Cari Dokumen Publik (SK/CV/Surat)": f"https://www.google.com/search?q=filetype:pdf OR filetype:docx OR filetype:txt intext:\"{safe_target}\"",
            
            "Cari Kebocoran Data (Pastebin/Dump)": f"https://www.google.com/search?q=site:pastebin.com OR site:ghostbin.com OR site:throwbin.io \"{safe_target}\""
        }
        
    return dorks