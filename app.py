import os
import tempfile
import re
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from modules.validator import identify_target
from modules.network import scan_ip_address, scan_domain_name
from modules.username import scan_username_profiles
from modules.image_forensics import analyze_image
from modules.identity import scan_email, scan_phone_number
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

UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/scan', methods=['POST'])
def scan_target():
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

    target = request.form.get('target')
    if not target:
        return jsonify({'error': 'Target kosong!'}), 400

    target_type = identify_target(target)
    result_data = {}
    dorks_data = generate_dorks(target)

    try:
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

        elif target_type == 'person':
            google_res = scan_person_name(target)
            pddikti_res = search_mahasiswa(target)
            result_data = {**google_res, "DATA KAMPUS (PDDikti)": pddikti_res}

        elif target_type == 'username':
            profiles = scan_username_profiles(target)
            if profiles:
                result_data = {"Found Accounts": profiles}
            else:
                result_data = {"Status": "Not Found"}

        elif re.match(r'^[A-Z0-9]{8,20}$', target.upper()) and not target.startswith("08"):
            target_type = "STUDENT ID (NIM)"
            result_data = search_mahasiswa(target)

        elif target_type == 'shortlink':
            exp = expand_shortlink(target)
            scan = scan_malware_url(exp.get('Real Destination', target))
            result_data = {**exp, **scan}

        elif target_type == 'nim':
            target_type = "STUDENT ID (NIM)"
            result_data = search_mahasiswa(target)

        else:
            target_type = "KEYWORD / NAME"
            pddikti_res = search_mahasiswa(target)
            google_res = scan_person_name(target)
            result_data = {
                "DATA KAMPUS (PDDikti)": pddikti_res,
                "GOOGLE SEARCH INFO": google_res
            }

        ai_narrative = analyze_data_with_ai(target, target_type.upper(), result_data)

        return jsonify({
            "target": target,
            "type": target_type.upper(),
            "data": result_data,
            "ai_analysis": ai_narrative,
            "google_dorks": dorks_data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)