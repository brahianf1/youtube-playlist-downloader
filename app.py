import os
import re
import json
import threading
from flask import Flask, render_template, request, jsonify, send_from_directory
import yt_dlp
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'downloads')
LOGS_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# Crear directorios si no existen
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
os.makedirs(LOGS_FOLDER, exist_ok=True)

# Almacenamiento de estado de descargas
download_status = {}

# Clase para manejar el progreso de descarga
class DownloadLogger:
    def __init__(self, download_id):
        self.download_id = download_id
        self.current_video = None
        self.total_videos = 0
        self.completed_videos = 0
        self.current_progress = 0
        self.update_status()
    
    def debug(self, msg):
        pass
    
    def warning(self, msg):
        pass
    
    def error(self, msg):
        download_status[self.download_id]['errors'].append(msg)
        self.update_status()
    
    def update_status(self):
        download_status[self.download_id].update({
            'current_video': self.current_video,
            'total_videos': self.total_videos,
            'completed_videos': self.completed_videos,
            'current_progress': self.current_progress
        })

# Función para extraer información de la lista de reproducción
def extract_playlist_info(url):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'force_generic_extractor': False,
        'retries': 10,                # Aumentar el número de reintentos
        'fragment_retries': 10,       # Aumentar reintentos para fragmentos
        'skip_unavailable_fragments': True,
        'ignoreerrors': True,         # Ignorar errores y continuar
        'extractor_retries': 10,      # Reintentos específicos para extractores
        'socket_timeout': 30,         # Aumentar el tiempo de espera del socket
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                # Filtrar entradas None que pueden aparecer cuando hay errores
                valid_entries = [entry for entry in info['entries'] if entry is not None]
                return {
                    'title': info.get('title', 'Playlist desconocida'),
                    'total_videos': len(valid_entries),
                    'videos': [{
                        'title': entry.get('title', f'Video {i+1}'),
                        'id': entry.get('id', ''),
                        'url': entry.get('url', '')
                    } for i, entry in enumerate(valid_entries)]
                }
            else:
                return {
                    'title': info.get('title', 'Video único'),
                    'total_videos': 1,
                    'videos': [{
                        'title': info.get('title', 'Video único'),
                        'id': info.get('id', ''),
                        'url': url
                    }]
                }
        except Exception as e:
            return {'error': str(e)}

# Función para descargar videos
def download_videos(download_options, download_id):
    logger = DownloadLogger(download_id)
    url = download_options['url']

    # Obtener información de la lista/video
    playlist_info = extract_playlist_info(url)
    if 'error' in playlist_info:
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['errors'].append(playlist_info['error'])
        return

    download_status[download_id]['playlist_title'] = playlist_info['title']
    logger.total_videos = playlist_info['total_videos']
    logger.update_status()

    # Configurar opciones de descarga
    common_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, download_id, '%(title)s.%(ext)s'),
        'logger': logger,
        'progress_hooks': [lambda d: progress_hook(d, logger)],
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ignoreerrors': True,
        'extractor_retries': 10,
        'socket_timeout': 30,
    }

    if download_options['type'] == 'playlist':
        common_opts['playlist_items'] = '1-1000'
        if download_options['format'] == 'audio':
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                **common_opts
            }
        else:  # video
            ydl_opts = {
                'format': 'best',
                **common_opts
            }
    else: # single video
        ydl_opts = {
            'format': f"{download_options['video_format_id']}+{download_options['audio_format_id']}",
            **common_opts
        }
    
    # Crear directorio para esta descarga
    os.makedirs(os.path.join(DOWNLOAD_FOLDER, download_id), exist_ok=True)
    
    # Iniciar descarga
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            download_status[download_id]['status'] = 'downloading'
            ydl.download([url])
        
        # Verificar si se descargaron archivos
        download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
        files = [f for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
        
        if files:
            download_status[download_id]['status'] = 'completed'
            # Actualizar el contador de videos completados basado en archivos reales
            download_status[download_id]['completed_videos'] = len(files)
            logger.completed_videos = len(files)
            logger.update_status()
        else:
            download_status[download_id]['status'] = 'error'
            download_status[download_id]['errors'].append('No se pudieron descargar archivos. Intenta con otra lista de reproducción o video individual.')
    
    except yt_dlp.utils.ExtractorError as e:
        error_msg = str(e)
        download_status[download_id]['status'] = 'error'
        
        if 'Incomplete data received' in error_msg:
            # Mensaje específico para el error de datos incompletos
            download_status[download_id]['errors'].append(
                'Error: YouTube no proporcionó datos completos. Esto puede ocurrir con listas de reproducción grandes. '
                'Intenta descargar la lista en partes más pequeñas o descargar videos individuales.'
            )
        else:
            download_status[download_id]['errors'].append(f'Error al extraer información: {error_msg}')
    
    except Exception as e:
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['errors'].append(f'Error inesperado: {str(e)}')
        
    # Verificar si se descargaron algunos archivos a pesar de los errores
    if download_status[download_id]['status'] == 'error':
        download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
        if os.path.exists(download_dir):
            files = [f for f in os.listdir(download_dir) if os.path.isfile(os.path.join(download_dir, f))]
            if files:
                download_status[download_id]['status'] = 'partial'
                download_status[download_id]['completed_videos'] = len(files)
                download_status[download_id]['errors'].append(
                    f'Se descargaron {len(files)} archivos antes de encontrar errores. '
                    'Puedes acceder a los archivos descargados a continuación.'
                )

# Función para manejar el progreso
def progress_hook(d, logger):
    if d['status'] == 'downloading':
        logger.current_video = d.get('filename', '').split('/')[-1]
        try:
            downloaded = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            if total > 0:
                logger.current_progress = int(downloaded / total * 100)
            logger.update_status()
        except:
            pass
    elif d['status'] == 'finished':
        logger.completed_videos += 1
        logger.current_progress = 0
        logger.update_status()

# Rutas de la aplicación
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video_info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url', '')
    if not url or not re.match(r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.*$', url):
        return jsonify({'error': 'URL de YouTube inválida'}), 400

    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                formats.append({
                    'format_id': f.get('format_id'),
                    'ext': f.get('ext'),
                    'resolution': f.get('resolution'),
                    'fps': f.get('fps'),
                    'filesize_approx': f.get('filesize_approx'),
                    'vcodec': f.get('vcodec'),
                    'acodec': f.get('acodec'),
                    'abr': f.get('abr')
                })
            return jsonify({'title': info.get('title'), 'formats': formats})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '')

    if not url or not re.match(r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.*$', url):
        return jsonify({'error': 'URL de YouTube inválida'}), 400

    download_id = secure_filename(f"{data.get('type', 'download')}_{os.urandom(4).hex()}")

    download_status[download_id] = {
        'id': download_id,
        'status': 'starting',
        'playlist_title': '',
        'current_video': None,
        'total_videos': 0,
        'completed_videos': 0,
        'current_progress': 0,
        'errors': []
    }

    thread = threading.Thread(target=download_videos, args=(data, download_id))
    thread.daemon = True
    thread.start()

    return jsonify({'download_id': download_id})

@app.route('/api/status/<download_id>', methods=['GET'])
def get_status(download_id):
    if download_id not in download_status:
        return jsonify({'error': 'ID de descarga no encontrado'}), 404
    
    return jsonify(download_status[download_id])

@app.route('/downloads/<download_id>/<filename>', methods=['GET'])
def download_file(download_id, filename):
    return send_from_directory(os.path.join(DOWNLOAD_FOLDER, download_id), filename)

@app.route('/api/downloads/<download_id>', methods=['GET'])
def list_downloads(download_id):
    download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
    if not os.path.exists(download_dir):
        return jsonify({'error': 'Directorio de descarga no encontrado'}), 404
    
    files = []
    for filename in os.listdir(download_dir):
        file_path = os.path.join(download_dir, filename)
        if os.path.isfile(file_path):
            files.append({
                'name': filename,
                'size': os.path.getsize(file_path),
                'url': f'/downloads/{download_id}/{filename}'
            })
    
    # Incluir el estado de la descarga en la respuesta
    status = 'completed'
    if download_id in download_status:
        status = download_status[download_id]['status']
    
    return jsonify({
        'files': files,
        'status': status
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')