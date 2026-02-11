import requests
import socket
import whois
import dns.resolver
from concurrent.futures import ThreadPoolExecutor

def scan_ip_address(ip):
    results = {}
    
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}", timeout=5)
        data = response.json()
        if data['status'] == 'success':
            results['geo'] = {
                "Negara": data.get('country'),
                "Kota": data.get('city'),
                "ISP": data.get('isp'),
                "Koordinat": f"{data.get('lat')}, {data.get('lon')}",
                "Timezone": data.get('timezone')
            }
        else:
            results['geo'] = {"Error": "IP Privat / Tidak Ditemukan"}
    except Exception as e:
        results['geo'] = {"Error": str(e)}

    open_ports = []
    target_ports = [21, 22, 80, 443, 8080, 3306]
    
    def check_port(port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1) 
        result = sock.connect_ex((ip, port))
        if result == 0:
            open_ports.append(port)
        sock.close()

    with ThreadPoolExecutor(max_workers=10) as executor:
        executor.map(check_port, target_ports)

    results['ports'] = open_ports if open_ports else "Tidak ada port umum yang terbuka (Firewall aktif)"
    
    return results

def scan_domain_name(domain):
    results = {}

    try:
        w = whois.whois(domain)
        results['whois'] = {
            "Registrar": w.registrar,
            "Server Whois": w.whois_server,
            "Tanggal Dibuat": str(w.creation_date),
            "Tanggal Expired": str(w.expiration_date),
            "Lokasi": f"{w.city}, {w.country}" if w.city else "Hidden"
        }
    except Exception as e:
        results['whois'] = {"Error": "Data Whois Hidden / Terproteksi Privacy"}

    dns_info = {}
    try:
        a_records = dns.resolver.resolve(domain, 'A')
        dns_info['IP Address'] = [r.to_text() for r in a_records]
        
        mx_records = dns.resolver.resolve(domain, 'MX')
        dns_info['Mail Server'] = [r.to_text() for r in mx_records]
        
    except Exception:
        pass

    results['dns'] = dns_info
    
    return results