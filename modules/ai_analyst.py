import os
from groq import Groq

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not GROQ_API_KEY:
    print("Warning: GROQ_API_KEY not set")
    client = None

else:
    client = Groq(GROQ_API_KEY=GROQ_API_KEY)

def analyze_data_with_ai(target, target_type, json_data):
    if not GROQ_API_KEY:
        return "AI Analysis Disabled: No API Key found."

    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        context_instructions = {
            "IP": "Analisa lokasi server, ISP, reputasi ancaman, dan potensi celah keamanan jaringan.",
            "DOMAIN": "Analisa kepemilikan domain, konfigurasi DNS, umur domain, dan indikasi phishing.",
            "USERNAME": "Lakukan profiling jejak digital, korelasi minat/hobi, dan prediksi demografi pengguna.",
            "PERSON": "Analisa eksposur data pribadi, afiliasi organisasi, dan potensi risiko doxing.",
            "EMAIL": "Cek validitas server, indikasi akun disposable, dan sejarah kebocoran data (breach).",
            "PHONE": "Identifikasi lokasi geografis, provider, tipe nomor, dan keterhubungan sosial.",
            "IMAGE FORENSICS": "Analisa metadata EXIF, identifikasi perangkat, lokasi GPS, dan parameter teknis foto.",
            "DOCUMENT FORENSICS": "Analisa metadata penulis, riwayat revisi, software pembuat, dan integritas file."
        }
        
        specific_instruction = context_instructions.get(target_type, "Analisa anomali data dan pola yang mencurigakan.")

        system_prompt = "Anda adalah Senior Cyber Intelligence Analyst. Gaya bicara: Tajam, Dingin, Langsung pada inti (No fluff). Bahasa: Indonesia Formal. Output: Wajib 1 paragraf padat (maksimal 5 kalimat)."
        
        user_prompt = f"""
        TARGET: {target}
        TIPE: {target_type}
        DATA MENTAH: {str(json_data)}
        
        MISI:
        1. {specific_instruction}
        2. Tentukan RISK LEVEL (Low/Medium/High).
        3. Temukan korelasi atau 'Smoking Gun' dari data tersebut.
        
        OUTPUT:
        Sajikan rangkuman eksekutif dalam satu paragraf pendek yang tajam.
        """

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.6,
            max_tokens=300
        )

        return chat_completion.choices[0].message.content
    
    except Exception as e:
        return f"ERR_AI_ANALYSIS: {str(e)}"