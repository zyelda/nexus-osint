import re

def identify_target(target):
    target = target.strip()
    
    if re.match(r"^[0-9]{16}$", target):
        return "nik"

    if re.match(r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$", target):
        return "ip"

    if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", target):
        return "email"

    if "youtube.com" in target or "youtu.be" in target:
        return "youtube"

    short_domains = ["bit.ly", "goo.gl", "tinyurl.com", "ow.ly", "s.id", "t.co", "is.gd", "cutt.ly"]
    if any(domain in target for domain in short_domains):
        return "shortlink"

    if re.match(r"^[A-Z0-9]{1,3}-[A-Z0-9]{2,5}$", target.upper()) or re.match(r"^N[0-9]{1,5}[A-Z]{0,2}$", target.upper()):
        return "aircraft"

    if re.match(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$", target):
        return "mac"

    if re.match(r"^(bc1|[13])[a-zA-HJ-NP-Z0-9]{25,39}$", target):
        return "btc"

    clean_phone = re.sub(r'[\s\-]', '', target)
    if re.match(r"^(\+62|62|08)[0-9]{8,13}$", clean_phone):
        return "phone"

    if re.match(r"^(https?:\/\/)?([a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}([/\w .-]*)?$", target):
        return "domain"

    if re.match(r"^[A-Z0-9]{7,20}$", target.upper()) and not target.isdigit():
        return "nim"
        
    if target.isdigit() and 8 <= len(target) <= 15 and not target.startswith("08"):
        return "nim"

    if " " in target:
        return "person"

    return "username"