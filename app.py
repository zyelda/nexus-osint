import os
import re
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

# Import Modules (Pastikan semua import aman)
from modules.validator import identify_target
from modules.network import scan_ip_address, scan_domain_name
from modules.username import scan_username_profiles
from modules.image_forensics import analyze_image
from modules.identity import scan_email, scan_phone_number
# Hapus import bitcoin/mac jika tidak dipakai, atau biarkan jika ada
from modules.finance_intel import scan_bitcoin_address, scan_mac_address, generate_dorks
from modules.nik_parser import parse_nik
from modules.person import scan_person_name
from modules.ai_analyst import analyze_data_with_ai
from modules.aviation import scan_aircraft
from modules.youtube_intel import scan_youtube_video
from modules.threat_intel import expand_shortlink, scan_malware_url
from modules.doc_forensics import analyze_document
from modules.pddikti import search_mahasiswa

app = Flask(__name__)

# Konfigurasi Upload
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan_target():
    # --- 1. HANDLING FILE UPLOAD ---
    if 'file' in request.files:
        file = request.files['file']
        if file.filename != '':
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            ext = os.path.splitext(filename)[1].lower()
            result_data = {}
            scan_type = ""

            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                scan_type = "IMAGE FORENSICS"
                result_data = analyze_image(filepath)
            elif ext in ['.pdf', '.docx']:
                scan_type = "DOCUMENT FORENSICS"
                result_data = analyze_document(filepath)
            else:
                return jsonify({'error': 'Format file tidak didukung!'}), 400

            # Hapus file setelah dianalisa agar hemat storage
            try:
                os.remove(filepath)
            except:
                pass

            ai_narrative = analyze_data_with_ai(filename, scan_type, result_data)

            return jsonify({
                "target": filename,
                "type": scan_type,
                "data": result_data,
                "ai_analysis": ai_narrative,
                "google_dorks": None
            })

    # --- 2. HANDLING TEXT INPUT ---
    target = request.form.get('target')
    if not target:
        return jsonify({'error': 'Target kosong!'}), 400

    # Identifikasi Tipe Target
    target_type = identify_target(target)
    result_data = {}
    dorks_data = generate_dorks(target) # Generate dorks statis (nanti kita fix di tahap selanjutnya)

    try:
        # --- SCAN LOGIC PER TYPE ---
        
        if target_type == 'ip':
            result_data = scan_ip_address(target)

        elif target_type == 'domain':
            clean_domain = target.replace("https://", "").replace("http://", "").split("/")[0]
            net = scan_domain_name(clean_domain)
            virus = scan_malware_url(target)
            result_data = {**net, **virus}

        elif target_type == 'email':
            result_data = scan_email(target)

        elif target_type == 'phone':
            result_data = scan_phone_number(target)

        elif target_type == 'nik':
            result_data = parse_nik(target)

        elif target_type == 'youtube':
            result_data = scan_youtube_video(target)
            
        elif target_type == 'shortlink':
            exp = expand_shortlink(target)
            scan = scan_malware_url(exp.get('Real Destination', target))
            result_data = {**exp, **scan}
            
        elif target_type == 'aircraft':
            result_data = scan_aircraft(target)

        # --- FIX NO 1: UNIVERSAL PROFILE SCAN ---
        # Jika tipe adalah 'universal_profile' (Nama/Username/NIM),
        # Kita jalankan SEMUA scan yang relevan.
        elif target_type == 'universal_profile':
            target_type = "MULTI-PROFILE SCAN" # Ubah nama tipe biar keren di UI
            
            # 1. Cek PDDikti (Kampus)
            pddikti_res = search_mahasiswa(target)
            
            # 2. Cek Username Medsos
            social_res = scan_username_profiles(target)
            
            # 3. Cek Jejak Digital Web (DuckDuckGo/Google)
            web_res = scan_person_name(target)
            
            # Gabungkan Hasil
            result_data = {
                "DATA KAMPUS (PDDikti)": pddikti_res,
                "AKUN MEDSOS (Username)": {"Found Accounts": social_res} if social_res else {"Status": "Tidak ditemukan username persis"},
                "JEJAK DIGITAL (Web)": web_res
            }

        # Analisa AI
        ai_narrative = analyze_data_with_ai(target, target_type, result_data)

        return jsonify({
            "target": target,
            "type": target_type,
            "data": result_data,
            "ai_analysis": ai_narrative,
            "google_dorks": dorks_data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)