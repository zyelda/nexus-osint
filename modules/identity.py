import dns.resolver
import hashlib
import requests
import phonenumbers
from phonenumbers import geocoder, carrier, timezone, number_type

def scan_email(email):
    results = {}
    try:
        user_part, domain_part = email.split('@')
    except ValueError:
        return {"Error": "Format email tidak valid."}

    try:
        mx_records = dns.resolver.resolve(domain_part, 'MX')
        mx_list = [str(x.exchange).rstrip('.') for x in mx_records]
        results['Mail Server'] = mx_list
        results['Validasi Domain'] = "Aktif (MX Record Ditemukan)"
    except Exception:
        results['Validasi Domain'] = "Tidak Aktif / Domain Mati"
        results['Mail Server'] = "None"

    disposable_domains = [
        "tempmail.com", "throwawaymail.com", "mailinator.com", "guerrillamail.com", 
        "yopmail.com", "10minutemail.com", "sharklasers.com", "getnada.com",
        "dispostable.com", "grr.la"
    ]
    
    if domain_part in disposable_domains:
        results['Tipe Email'] = "⚠️ DISPOSABLE / FAKE EMAIL (Sekali Pakai)"
    elif "gmail" in domain_part or "yahoo" in domain_part or "outlook" in domain_part:
        results['Tipe Email'] = "Personal / Public Provider"
    elif "edu" in domain_part or "ac.id" in domain_part:
        results['Tipe Email'] = "Institusi Pendidikan"
    elif "gov" in domain_part or "go.id" in domain_part:
        results['Tipe Email'] = "Pemerintahan"
    else:
        results['Tipe Email'] = "Custom Domain / Corporate"

    email_hash = hashlib.md5(email.lower().encode('utf-8')).hexdigest()
    gravatar_url = f"https://www.gravatar.com/avatar/{email_hash}?d=404"
    
    try:
        r = requests.get(gravatar_url, timeout=5)
        if r.status_code == 200:
            results['Gravatar Profile'] = "Ditemukan"
            results['Profile Picture Link'] = gravatar_url
        else:
            results['Gravatar Profile'] = "Tidak Ditemukan"
    except:
        results['Gravatar Profile'] = "Error Connection"

    results['[LINK] Cek Kebocoran Data'] = f"https://haveibeenpwned.com/account/{email}"
    results['[LINK] Cari di Google'] = f"https://www.google.com/search?q=\"{email}\""
    results['[LINK] Cari di GitHub'] = f"https://github.com/search?q={email}&type=users"
    
    return results

def scan_phone_number(number):
    results = {}
    try:
        parsed_num = phonenumbers.parse(number, "ID")
        
        if not phonenumbers.is_valid_number(parsed_num):
            return {"Error": "Nomor tidak valid atau tidak terdaftar secara internasional."}

        e164_format = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.E164)
        
        results['Format Internasional'] = e164_format
        results['Format Nasional'] = phonenumbers.format_number(parsed_num, phonenumbers.PhoneNumberFormat.NATIONAL)
        
        provider = carrier.name_for_number(parsed_num, "en")
        results['Provider (Carrier)'] = provider if provider else "Tidak Teridentifikasi / Fixed Line"
        
        region = geocoder.description_for_number(parsed_num, "id")
        results['Lokasi (Region)'] = region if region else "Indonesia (Umum)"
        
        num_type_code = number_type(parsed_num)
        if num_type_code == phonenumbers.PhoneNumberType.MOBILE:
            results['Tipe Nomor'] = "Seluler (Mobile)"
        elif num_type_code == phonenumbers.PhoneNumberType.FIXED_LINE:
            results['Tipe Nomor'] = "Telepon Rumah / Kantor (Fixed Line)"
        elif num_type_code == phonenumbers.PhoneNumberType.VOIP:
            results['Tipe Nomor'] = "VOIP (Internet Based)"
        else:
            results['Tipe Nomor'] = "Tidak Diketahui"

        timezones = timezone.time_zones_for_number(parsed_num)
        results['Zona Waktu'] = ", ".join(timezones)

        clean_num = e164_format.replace("+", "")
        results['[CHAT] WhatsApp'] = f"https://wa.me/{clean_num}"
        results['[CHAT] Telegram'] = f"https://t.me/{clean_num}"
        results['[CHAT] Viber'] = f"viber://chat?number={clean_num}"
        
        results['[SEARCH] TrueCaller'] = f"https://www.truecaller.com/search/id/{clean_num}"
        results['[SEARCH] Sync.me'] = f"https://sync.me/search/?number={clean_num}"
        
    except Exception as e:
        results['Error'] = f"Gagal memproses nomor: {str(e)}"

    return results