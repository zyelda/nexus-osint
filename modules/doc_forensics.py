import os
import hashlib
import datetime
import PyPDF2
from docx import Document

def calculate_hashes(filepath):
    hash_md5 = hashlib.md5()
    hash_sha1 = hashlib.sha1()
    hash_sha256 = hashlib.sha256()
    
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
            hash_sha1.update(chunk)
            hash_sha256.update(chunk)
            
    return {
        "MD5": hash_md5.hexdigest(),
        "SHA1": hash_sha1.hexdigest(),
        "SHA256": hash_sha256.hexdigest()
    }

def get_file_stats(filepath):
    stats = os.stat(filepath)
    return {
        "File Name": os.path.basename(filepath),
        "File Size": f"{stats.st_size / 1024:.2f} KB",
        "Created Time": datetime.datetime.fromtimestamp(stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
        "Modified Time": datetime.datetime.fromtimestamp(stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
    }

def analyze_document(filepath):
    ext = os.path.splitext(filepath)[1].lower()
    
    analysis = {
        "Type": "Unknown",
        "System Info": {},
        "Hashes": {},
        "Metadata": {},
        "Preview": "No preview available"
    }

    try:
        analysis["System Info"] = get_file_stats(filepath)
        analysis["Hashes"] = calculate_hashes(filepath)

        if ext == '.pdf':
            analysis["Type"] = "PDF Document"
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                meta = reader.metadata
                
                if meta:
                    analysis["Metadata"] = {
                        "Title": meta.title if meta.title else "Unknown",
                        "Author": meta.author if meta.author else "Unknown",
                        "Creator": meta.creator if meta.creator else "Unknown",
                        "Producer": meta.producer if meta.producer else "Unknown",
                        "Creation Date": str(meta.creation_date) if meta.creation_date else "Unknown"
                    }
                
                analysis["Metadata"]["Encrypted"] = str(reader.is_encrypted)
                analysis["Metadata"]["Pages"] = str(len(reader.pages))

                try:
                    first_page = reader.pages[0]
                    text = first_page.extract_text()
                    analysis["Preview"] = text[:500].replace('\n', ' ') + "..." if text else "[Empty]"
                except:
                    analysis["Preview"] = "[Protected/Image Only]"

        elif ext == '.docx':
            analysis["Type"] = "Microsoft Word (DOCX)"
            doc = Document(filepath)
            props = doc.core_properties
            
            analysis["Metadata"] = {
                "Title": props.title if props.title else "Unknown",
                "Author": props.author if props.author else "Unknown",
                "Last Modified By": props.last_modified_by if props.last_modified_by else "Unknown",
                "Revision": str(props.revision),
                "Created": str(props.created) if props.created else "Unknown",
                "Modified": str(props.modified) if props.modified else "Unknown",
                "Category": props.category if props.category else "None",
                "Subject": props.subject if props.subject else "None"
            }

            full_text = []
            for para in doc.paragraphs[:10]:
                if para.text.strip():
                    full_text.append(para.text.strip())
            
            analysis["Preview"] = " ".join(full_text)[:500] + "..." if full_text else "[Empty]"

        else:
            return {"Error": "Unsupported file format."}

        return analysis

    except Exception as e:
        return {"Error": f"Analysis Failed: {str(e)}"}