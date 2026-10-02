import os
import sys
import time
import json
import uuid
import re
import urllib.request
import threading
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_file
from flask_cors import CORS
import yt_dlp
import imageio_ffmpeg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATIC_DIR = os.path.join(BASE_DIR, 'static')
if os.environ.get('VERCEL') or sys.platform != 'win32' or not os.access(BASE_DIR, os.W_OK):
    DOWNLOADS_DIR = os.path.join('/tmp', 'downloads_cache')
else:
    DOWNLOADS_DIR = os.path.join(BASE_DIR, 'downloads_cache')

try:
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
except Exception:
    DOWNLOADS_DIR = '/tmp'

USER_DOWNLOADS = str(Path.home() / "Downloads")

app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATES_DIR)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app)

try:
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = None

active_tasks = {}
download_history = []

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

def detect_platform(url):
    u = url.lower()
    if 'youtube.com' in u or 'youtu.be' in u:
        return {'name': 'YouTube', 'color': '#ff0033', 'icon': 'youtube'}
    elif 'facebook.com' in u or 'fb.watch' in u or 'fb.com' in u:
        return {'name': 'Facebook', 'color': '#1877f2', 'icon': 'facebook'}
    elif 'instagram.com' in u or 'instagr.am' in u:
        return {'name': 'Instagram', 'color': '#e1306c', 'icon': 'instagram'}
    elif 'tiktok.com' in u:
        return {'name': 'TikTok', 'color': '#00f2fe', 'icon': 'tiktok'}
    elif 'twitter.com' in u or 'x.com' in u:
        return {'name': 'Twitter / X', 'color': '#ffffff', 'icon': 'twitter'}
    elif 'pinterest.com' in u or 'pin.it' in u:
        return {'name': 'Pinterest', 'color': '#e60023', 'icon': 'pinterest'}
    elif 'reddit.com' in u:
        return {'name': 'Reddit', 'color': '#ff4500', 'icon': 'reddit'}
    else:
        return {'name': 'Universal Web', 'color': '#8b5cf6', 'icon': 'globe'}

@app.route('/')
def index():
    return render_template('index.html', downloads_dir=USER_DOWNLOADS)

@app.route('/api/info', methods=['POST'])
def get_video_info():
    data = request.json or {}
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    platform_info = detect_platform(url)

    try:
        ydl_opts = {
            'windowsfilenames': sys.platform == 'win32',
            'restrictfilenames': True,
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'nocheckcertificate': True
        }
        if FFMPEG_EXE and os.path.exists(str(FFMPEG_EXE)):
            ydl_opts['ffmpeg_location'] = FFMPEG_EXE
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            is_playlist = info.get('_type') == 'playlist'
            entries = info.get('entries', []) if is_playlist else [info]
            first_entry = entries[0] if entries else info
            
            # Safe duration parsing
            try:
                raw_dur = first_entry.get('duration')
                duration_sec = int(float(raw_dur)) if raw_dur is not None else 0
            except Exception:
                duration_sec = 0

            mins, secs = divmod(duration_sec, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                duration_str = f"{int(hours):02d}:{int(mins):02d}:{int(secs):02d}"
            elif duration_sec > 0:
                duration_str = f"{int(mins):02d}:{int(secs):02d}"
            else:
                duration_str = "HD Media"

            # Safe views parsing
            try:
                raw_views = first_entry.get('view_count')
                views = int(float(raw_views)) if raw_views is not None else 0
            except Exception:
                views = 0

            if views >= 1_000_000:
                views_str = f"{views / 1_000_000:.1f}M views"
            elif views >= 1_000:
                views_str = f"{views / 1_000:.1f}K views"
            elif views > 0:
                views_str = f"{views} views"
            else:
                views_str = "HD Quality"

            formats = first_entry.get('formats', [])
            has_4k = any(f.get('height') and f.get('height') >= 2160 for f in formats)
            has_2k = any(f.get('height') and f.get('height') >= 1440 for f in formats)
            has_1080 = any(f.get('height') and f.get('height') >= 1080 for f in formats) or platform_info['name'] in ['Facebook', 'Instagram', 'TikTok']
            has_720 = any(f.get('height') and f.get('height') >= 720 for f in formats) or bool(formats)
            has_480 = any(f.get('height') and f.get('height') >= 480 for f in formats)
            has_360 = any(f.get('height') and f.get('height') >= 360 for f in formats)

            media_type = 'video'
            if not formats or duration_sec == 0:
                if first_entry.get('thumbnail') or first_entry.get('url'):
                    media_type = 'image'

            # Safe thumbnail resolution
            thumbnail = first_entry.get('thumbnail')
            if not thumbnail:
                thumbs = first_entry.get('thumbnails')
                if thumbs and isinstance(thumbs, list) and len(thumbs) > 0:
                    last_thumb = thumbs[-1]
                    if isinstance(last_thumb, dict):
                        thumbnail = last_thumb.get('url')

            # Clean title
            raw_title = first_entry.get('title') or first_entry.get('description') or f"{platform_info['name']} Reel"
            if len(raw_title) > 100:
                raw_title = raw_title[:97] + "..."

            return jsonify({
                'title': raw_title,
                'uploader': first_entry.get('uploader') or first_entry.get('channel') or f"{platform_info['name']} User",
                'thumbnail': thumbnail or 'https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=800',
                'duration': duration_str,
                'duration_raw': duration_sec,
                'views': views_str,
                'id': first_entry.get('id') or 'media',
                'url': url,
                'platform': platform_info,
                'media_type': media_type,
                'resolutions': {
                    '4k': has_4k,
                    '2k': has_2k,
                    '1080': has_1080,
                    '720': has_720 or True,
                    '480': has_480,
                    '360': has_360
                }
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json or {}
    url = data.get('url', '').strip()
    format_type = data.get('format_type', 'video')
    quality = data.get('quality', '1080')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400

    task_id = str(uuid.uuid4())
    active_tasks[task_id] = {
        'status': 'starting',
        'percent': 0,
        'speed': '0 MB/s',
        'eta': '--:--',
        'downloaded_bytes': 0,
        'total_bytes': 0,
        'title': 'Extracting media...',
        'filename': '',
        'filepath': '',
        'error': None
    }

    thread = threading.Thread(target=run_downloader_thread, args=(task_id, url, format_type, quality))
    thread.daemon = True
    thread.start()

    return jsonify({'task_id': task_id, 'status': 'started'})

def progress_hook_factory(task_id):
    def hook(d):
        task = active_tasks.get(task_id)
        if not task:
            return
        
        try:
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed') or 0
                eta = d.get('eta') or 0
                
                percent = (downloaded / total) * 100 if total > 0 else 0
                speed_mb = speed / (1024 * 1024) if speed else 0
                
                task['status'] = 'downloading'
                task['percent'] = round(min(percent, 99.9), 1)
                task['speed'] = f"{speed_mb:.2f} MB/s"
                try:
                    task['eta'] = f"{int(float(eta))}s" if eta else "calculating..."
                except Exception:
                    task['eta'] = "calculating..."
                    
                task['downloaded_bytes'] = downloaded
                task['total_bytes'] = total
                if 'filename' in d:
                    task['filepath'] = d['filename']
                    task['filename'] = os.path.basename(d['filename'])
                    
            elif d['status'] == 'finished':
                task['status'] = 'processing'
                task['percent'] = 100
                task['eta'] = 'Finalizing file...'
                if 'filename' in d:
                    task['filepath'] = d['filename']
                    task['filename'] = os.path.basename(d['filename'])
        except Exception:
            pass
    return hook

def run_downloader_thread(task_id, url, format_type, quality):
    task = active_tasks[task_id]
    try:
        file_prefix = task_id[:8]
        
        if format_type == 'image':
            ydl_opts_img = {
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True
            }
            with yt_dlp.YoutubeDL(ydl_opts_img) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title') or 'Photo'
                task['title'] = title
                
                img_url = info.get('url') or info.get('thumbnail')
                if not img_url:
                    thumbs = info.get('thumbnails')
                    if thumbs and isinstance(thumbs, list) and len(thumbs) > 0:
                        last_t = thumbs[-1]
                        if isinstance(last_t, dict):
                            img_url = last_t.get('url')

                if not img_url:
                    raise Exception("No image stream found in post.")
                
                ext = 'jpg' if 'jpg' in img_url or 'jpeg' in img_url else 'png'
                clean_title = re.sub(r'[\\/*?:"<>|]', "", title)[:40]
                final_filename = f"{file_prefix}_{clean_title}.{ext}"
                final_path = os.path.join(DOWNLOADS_DIR, final_filename)
                
                req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as resp, open(final_path, 'wb') as f:
                    f.write(resp.read())
                
                task['filepath'] = final_path
                task['filename'] = final_filename
                task['status'] = 'completed'
                task['percent'] = 100

                download_history.insert(0, {
                    'id': task_id,
                    'title': title,
                    'quality': 'PHOTO HD',
                    'type': 'image',
                    'time': time.strftime("%I:%M %p"),
                    'filename': final_filename
                })
                return

        ydl_opts = {
            'windowsfilenames': sys.platform == 'win32',
            'restrictfilenames': True,
            'paths': {'home': DOWNLOADS_DIR, 'temp': DOWNLOADS_DIR},
            'outtmpl': {'default': f'{file_prefix}_%(id)s.%(ext)s'},
            'quiet': True,
            'no_warnings': True,
            'noprogress': True,
            'nocheckcertificate': True,
            'progress_hooks': [progress_hook_factory(task_id)]
        }
        if FFMPEG_EXE and os.path.exists(str(FFMPEG_EXE)):
            ydl_opts['ffmpeg_location'] = FFMPEG_EXE
        
        if format_type == 'audio':
            if 'mp3' in quality:
                bitrate = '320' if '320' in quality else '128'
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': bitrate,
                }]
            else:
                ydl_opts['format'] = 'bestaudio[ext=m4a]/bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                }]
        else:
            if quality == '4k':
                ydl_opts['format'] = 'bestvideo[height<=2160]+bestaudio/best[height<=2160]/best'
            elif quality == '2k':
                ydl_opts['format'] = 'bestvideo[height<=1440]+bestaudio/best[height<=1440]/best'
            elif quality == '1080':
                ydl_opts['format'] = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
            elif quality == '720':
                ydl_opts['format'] = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
            elif quality == '480':
                ydl_opts['format'] = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'
            else:
                ydl_opts['format'] = 'bestvideo[height<=360]+bestaudio/best[height<=360]/best'
            
            ydl_opts['merge_output_format'] = 'mp4'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title') or 'Media Video'
            task['title'] = video_title
            
            matched_files = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(file_prefix)]
            if matched_files:
                final_filename = matched_files[0]
                task['filepath'] = os.path.join(DOWNLOADS_DIR, final_filename)
                task['filename'] = final_filename

            task['status'] = 'completed'
            task['percent'] = 100
            
            display_title = video_title
            download_history.insert(0, {
                'id': task_id,
                'title': display_title,
                'quality': quality.upper(),
                'type': format_type,
                'time': time.strftime("%I:%M %p"),
                'filename': task['filename']
            })
            if len(download_history) > 20:
                download_history.pop()

    except Exception as e:
        import traceback
        traceback.print_exc()
        task['status'] = 'error'
        task['error'] = str(e)

@app.route('/api/progress/<task_id>')
def get_progress(task_id):
    task = active_tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)

@app.route('/api/get-file/<task_id>')
def download_file_to_browser(task_id):
    prefix = task_id[:8]
    task = active_tasks.get(task_id, {})
    
    candidates = [f for f in os.listdir(DOWNLOADS_DIR) if f.startswith(prefix)]
    if not candidates:
        return jsonify({'error': 'File missing or expired'}), 404
    
    filepath = os.path.join(DOWNLOADS_DIR, candidates[0])
    ext = os.path.splitext(candidates[0])[1]
    
    title = task.get('title') or 'Media_Download'
    clean_title = re.sub(r'[\\/*?:"<>|\r\n]', "", title).strip()[:80] or "Media_Download"
    clean_download_name = f"{clean_title}{ext}"

    return send_file(
        filepath,
        as_attachment=True,
        download_name=clean_download_name
    )

@app.route('/api/history')
def get_history():
    return jsonify(download_history)

@app.route('/api/open-downloads', methods=['POST'])
def open_downloads_folder():
    try:
        target = USER_DOWNLOADS if os.path.exists(USER_DOWNLOADS) else DOWNLOADS_DIR
        if sys.platform == 'win32':
            os.startfile(target)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', target])
        else:
            subprocess.Popen(['xdg-open', target])
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    PORT = 7860
    print(f"Starting The Downloader on http://localhost:{PORT}")
    app.run(host='127.0.0.1', port=PORT, debug=False)
