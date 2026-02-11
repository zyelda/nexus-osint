import datetime

def get_zodiac(day, month):
    zodiacs = [
        (120, 'Capricorn'), (218, 'Aquarius'), (320, 'Pisces'), (420, 'Aries'),
        (521, 'Taurus'), (621, 'Gemini'), (722, 'Cancer'), (823, 'Leo'),
        (923, 'Virgo'), (1023, 'Libra'), (1122, 'Scorpio'), (1222, 'Sagittarius'), (1231, 'Capricorn')
    ]
    date_number = int(f"{month}{day:02d}")
    for z_val, z_name in zodiacs:
        if date_number <= z_val:
            return z_name
    return 'Capricorn'

def get_generation(year):
    if year >= 2013: return "Gen Alpha"
    if year >= 1997: return "Gen Z"
    if year >= 1981: return "Millennial (Gen Y)"
    if year >= 1965: return "Gen X"
    if year >= 1946: return "Baby Boomer"
    return "Silent Generation"

def get_weton(date_obj):
    pasaran = ["Legi", "Pahing", "Pon", "Wage", "Kliwon"]
    reference_date = datetime.date(1900, 1, 1) 
    days_passed = (date_obj - reference_date).days
    return pasaran[(days_passed + 1) % 5]

# NAMA FUNGSI DIKEMBALIKAN JADI 'parse_nik' AGAR COCOK DENGAN APP.PY
def parse_nik(nik):
    if not isinstance(nik, str) or len(nik) != 16 or not nik.isdigit():
        return {
            "status": "INVALID",
            "message": "NIK harus berupa string angka 16 digit."
        }

    wilayah_map = {
        "11": "Aceh", "12": "Sumatera Utara", "13": "Sumatera Barat", "14": "Riau",
        "15": "Jambi", "16": "Sumatera Selatan", "17": "Bengkulu", "18": "Lampung",
        "19": "Kepulauan Bangka Belitung", "21": "Kepulauan Riau",
        "31": "DKI Jakarta", "32": "Jawa Barat", "33": "Jawa Tengah", "34": "DI Yogyakarta",
        "35": "Jawa Timur", "36": "Banten",
        "51": "Bali", "52": "Nusa Tenggara Barat", "53": "Nusa Tenggara Timur",
        "61": "Kalimantan Barat", "62": "Kalimantan Tengah", "63": "Kalimantan Selatan",
        "64": "Kalimantan Timur", "65": "Kalimantan Utara",
        "71": "Sulawesi Utara", "72": "Sulawesi Tengah", "73": "Sulawesi Selatan",
        "74": "Sulawesi Tenggara", "75": "Gorontalo", "76": "Sulawesi Barat",
        "81": "Maluku", "82": "Maluku Utara",
        "91": "Papua", "92": "Papua Barat", "93": "Papua Selatan",
        "94": "Papua Tengah", "95": "Papua Pegunungan", "96": "Papua Barat Daya"
    }

    prov_code = nik[:2]
    kota_code = nik[2:4]
    kec_code = nik[4:6]
    tanggal_code = int(nik[6:8])
    bulan_code = int(nik[8:10])
    tahun_code = int(nik[10:12])
    urutan_code = nik[12:]

    jenis_kelamin = "Laki-Laki"
    tanggal_lahir = tanggal_code

    if tanggal_code > 40:
        jenis_kelamin = "Perempuan"
        tanggal_lahir = tanggal_code - 40

    current_date = datetime.date.today()
    current_year_full = current_date.year
    century_prefix = 1900
    
    # Logika deteksi tahun 2000an
    if (2000 + tahun_code) <= current_year_full:
        century_prefix = 2000
    
    tahun_lahir_full = century_prefix + tahun_code
    
    try:
        birth_date_obj = datetime.date(tahun_lahir_full, bulan_code, tanggal_lahir)
    except ValueError:
        return {"status": "INVALID", "message": "Kombinasi tanggal pada NIK tidak valid."}

    age_years = current_date.year - birth_date_obj.year
    age_months = current_date.month - birth_date_obj.month
    age_days = current_date.day - birth_date_obj.day

    if age_days < 0:
        age_months -= 1
        age_days += 30 
    if age_months < 0:
        age_years -= 1
        age_months += 12

    next_birthday = datetime.date(current_date.year, birth_date_obj.month, birth_date_obj.day)
    if next_birthday < current_date:
        next_birthday = datetime.date(current_date.year + 1, birth_date_obj.month, birth_date_obj.day)
    days_to_birthday = (next_birthday - current_date).days

    provinsi_nama = wilayah_map.get(prov_code, "Provinsi Tidak Terdaftar")

    return {
        "status": "VALID",
        "metadata": {
            "timestamp_check": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input_nik": nik
        },
        "data_pribadi": {
            "jenis_kelamin": jenis_kelamin,
            "tanggal_lahir": birth_date_obj.strftime("%d %B %Y"),
            "zodiak": get_zodiac(tanggal_lahir, bulan_code),
            "weton": get_weton(birth_date_obj),
            "generasi": get_generation(tahun_lahir_full)
        },
        "data_usia": {
            "tahun": age_years,
            "bulan": age_months,
            "hari": age_days,
            "ulang_tahun_berikutnya": f"{days_to_birthday} hari lagi"
        },
        "data_wilayah": {
            "kode_provinsi": prov_code,
            "nama_provinsi": provinsi_nama,
            "kode_kab_kota": f"{prov_code}.{kota_code}",
            "kode_kecamatan": f"{prov_code}.{kota_code}.{kec_code}",
            "keterangan": "Kode Kab/Kota dan Kecamatan membutuhkan database Dukcapil lengkap untuk nama spesifik."
        },
        "data_administrasi": {
            "nomor_urut_registrasi": urutan_code,
            "unik_id": f"{prov_code}{kota_code}{kec_code}-{urutan_code}"
        }
    }