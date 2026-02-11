import requests
import base64

VT_API_KEY = "6188bf9d432315dbf29e17fc3c3ebdeafddeb3856b0ac811dea49d873b86c5f6" 

def expand_shortlink(short_url):
    results = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(short_url, headers=headers, allow_redirects=True, timeout=10)
        
        results['Original Shortlink'] = short_url
        results['Real Destination'] = response.url
        results['Status Code'] = response.status_code
        
        if short_url != response.url:
            results['Analisa'] = "Link ini adalah REDIRECT (Pengalihan). Hati-hati phishing."
        else:
            if response.history:
                results['Real Destination'] = response.history[-1].url
                results['Analisa'] = "Redirect terdeteksi dari history."
            else:
                results['Analisa'] = "Link tidak melakukan redirect (Mungkin halaman landas/interstitial)."
            
    except Exception as e:
        results['Error'] = f"Gagal expand link: {str(e)}"
    
    return results

def scan_malware_url(target_url):
    if "MASUKKAN" in VT_API_KEY or not VT_API_KEY:
        return {"Status": "Skipped", "Note": "API Key VirusTotal belum dipasang di modules/threat_intel.py"}

    results = {}
    
    url_id = base64.urlsafe_b64encode(target_url.encode()).decode().strip("=")
    
    headers = {
        "accept": "application/json",
        "x-apikey": VT_API_KEY
    }
    
    try:
        api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
        response = requests.get(api_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()['data']['attributes']
            
            stats = data['last_analysis_stats']
            results['Malicious Score'] = f"{stats['malicious']} / {stats['harmless'] + stats['malicious']}"
            results['Reputation'] = data.get('reputation', 0)
            
            vendors = []
            for engine, result in data['last_analysis_results'].items():
                if result['category'] == 'malicious':
                    vendors.append(engine)
            
            if vendors:
                results['Detected By'] = ", ".join(vendors)
                results['Conclusion'] = "BAHAYA! Link ini terdeteksi mengandung malware/phishing."
            else:
                results['Conclusion'] = "AMAN. Tidak ada vendor antivirus yang mendeteksi bahaya."
                
            results['Scan Date'] = data.get('last_analysis_date', 'Unknown')
            results['VirusTotal Link'] = f"https://www.virustotal.com/gui/url/{url_id}/detection"
            
        elif response.status_code == 404:
            results['Status'] = "URL belum ada di database VirusTotal (New URL)."
        else:
            results['Error'] = f"API Error: {response.status_code}"
            
    except Exception as e:
        results['Error'] = str(e)

    return results