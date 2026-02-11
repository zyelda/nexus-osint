import os
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS

def get_decimal_from_dms(dms, ref):
    degrees = dms[0]
    minutes = dms[1]
    seconds = dms[2]
    
    decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
    
    if ref in ['S', 'W']:
        decimal = -decimal
        
    return decimal

def decode_exif_value(val):
    if isinstance(val, bytes):
        try:
            return val.decode('utf-8').strip()
        except:
            return str(val)
    return str(val)

def analyze_image(image_path):
    result = {
        "File Metadata": {},
        "Device Information": {},
        "Shooting Parameters": {},
        "GPS Coordinates": None,
        "Google Maps Link": None,
        "Status": "No EXIF Data Found"
    }
    
    try:
        if not os.path.exists(image_path):
            return {"Error": "File tidak ditemukan."}

        file_stat = os.stat(image_path)
        img = Image.open(image_path)
        
        result["File Metadata"] = {
            "Filename": os.path.basename(image_path),
            "Filesize": f"{file_stat.st_size / 1024:.2f} KB",
            "Format": img.format,
            "Mode": img.mode,
            "Resolution": f"{img.width} x {img.height} pixels"
        }

        exif_raw = img._getexif()
        
        if not exif_raw:
            result["Status"] = "Clean Image (No Metadata)"
            return result

        result["Status"] = "Metadata Found"
        gps_data = {}

        for tag_id, value in exif_raw.items():
            tag_name = TAGS.get(tag_id, tag_id)
            clean_val = decode_exif_value(value)

            # 1. DEVICE INFO
            if tag_name in ['Make', 'Model', 'BodySerialNumber', 'LensModel', 'LensSerialNumber', 'Software', 'Artist', 'Copyright']:
                result["Device Information"][tag_name] = clean_val

            # 2. SHOOTING PARAMETERS (Teknis Fotografi)
            elif tag_name in ['ISOSpeedRatings', 'ExposureTime', 'FNumber', 'FocalLength', 'Flash', 'WhiteBalance', 'DateTimeOriginal', 'ShutterSpeedValue', 'ApertureValue']:
                if tag_name == 'ExposureTime' and isinstance(value, float):
                    clean_val = f"1/{int(1/value)}" if value < 1 else str(value)
                
                result["Shooting Parameters"][tag_name] = clean_val
            
            # 3. GPS PARSING
            elif tag_name == 'GPSInfo':
                for t in value:
                    sub_tag = GPSTAGS.get(t, t)
                    gps_data[sub_tag] = value[t]

        if 'GPSLatitude' in gps_data and 'GPSLongitude' in gps_data:
            try:
                lat = get_decimal_from_dms(gps_data['GPSLatitude'], gps_data['GPSLatitudeRef'])
                lon = get_decimal_from_dms(gps_data['GPSLongitude'], gps_data['GPSLongitudeRef'])
                
                altitude = "Unknown"
                if 'GPSAltitude' in gps_data:
                    altitude = f"{gps_data['GPSAltitude']} meters"

                result["GPS Coordinates"] = {
                    "Latitude": lat,
                    "Longitude": lon,
                    "Altitude": altitude,
                    "Map Reference": gps_data.get('GPSMapDatum', 'WGS-84')
                }
                result["Google Maps Link"] = f"https://www.google.com/maps?q={lat},{lon}"
            except Exception as e:
                result["GPS Coordinates"] = f"Error decoding GPS: {str(e)}"

        return result

    except Exception as e:
        return {"Error": f"Critical Failure: {str(e)}"}