import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi

def extract_video_id(url):
    """
    Mengambil ID Video dari URL YouTube (Support Shorts, Mobile, Desktop)
    """
    regex = r"(?:v=|\/)([0-9A-Za-z_-]{11}).*"
    match = re.search(regex, url)
    if match:
        return match.group(1)
    return None

def scan_youtube_video(url):
    results = {}
    video_id = extract_video_id(url)
    
    if not video_id:
        return {"Error": "URL YouTube tidak valid atau ID video tidak ditemukan."}

    results['Video ID'] = video_id
    results['URL'] = url
    
    try:
        r = requests.get(url)
        if r.status_code == 200:
            html = r.text
            title = re.search(r'"title":"(.*?)"', html)
            views = re.search(r'"viewCount":"(.*?)"', html)
            author = re.search(r'"ownerChannelName":"(.*?)"', html)
            keywords = re.search(r'"keywords":\[(.*?)\]', html)
            
            results['Title'] = title.group(1) if title else "Unknown"
            results['Channel'] = author.group(1) if author else "Unknown"
            results['Views'] = views.group(1) if views else "0"
            results['Hidden Tags (SEO)'] = keywords.group(1).replace('"', '') if keywords else "None"
            
            results['Thumbnail HD'] = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
            
    except Exception as e:
        results['Metadata Error'] = str(e)
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['id', 'en'])
        full_text = " ".join([t['text'] for t in transcript_list])
        results['Transcript Preview'] = full_text[:500] + "... (Full transcript sent to AI)"
        results['Full_Transcript_Raw'] = full_text 
        
    except Exception as e:
        results['Transcript Status'] = "Subtitle tidak tersedia / dinonaktifkan oleh uploader."
    
    return results