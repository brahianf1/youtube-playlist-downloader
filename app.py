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

# Función para manejar el progreso
def progress_hook(d, download_id):
    status = download_status.get(download_id)
    if not status:
        return

    # Identificar qué parte se está procesando (video, audio, merge)
    filename = d.get('filename', '')
    format_id = d.get('info_dict', {}).get('format_id', 'default')
    
    # Inicializar o actualizar el seguimiento de partes si no existe
    if 'parts' not in status:
        status['parts'] = {}
    
    # Crear una clave única para esta parte del proceso
    part_key = format_id
    if '_mp4' in filename or '.mp4.' in filename or '.mkv.' in filename:
        part_key = 'merge'
    
    # Inicializar la entrada para esta parte si no existe
    if part_key not in status['parts']:
        status['parts'][part_key] = {
            'total_bytes': 0,
            'downloaded_bytes': 0,
            'status': 'pending'
        }
    
    part = status['parts'][part_key]
    
    status['hook_status'] = d['status']
    status['current_stage'] = 'Mezclando formatos...' if part_key == 'merge' else f"Descargando {part_key}..."
    
    if d['status'] == 'downloading':
        # Actualizar datos de esta parte
        status['current_video'] = os.path.basename(filename)
        part['status'] = 'downloading'
        
        # Actualizar bytes solo si hay información disponible
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        if total_bytes:
            part['total_bytes'] = total_bytes
        
        downloaded_bytes = d.get('downloaded_bytes')
        if downloaded_bytes:
            part['downloaded_bytes'] = downloaded_bytes
        
        # Actualizar métricas de velocidad y tiempo
        status['speed'] = d.get('speed')
        status['eta'] = d.get('eta')
        status['elapsed'] = d.get('elapsed')
        
        # Calcular el progreso general combinando todas las partes
        total_bytes_all_parts = sum(p.get('total_bytes', 0) for p in status['parts'].values())
        downloaded_bytes_all_parts = sum(p.get('downloaded_bytes', 0) for p in status['parts'].values())
        
        if total_bytes_all_parts > 0:
            status['total_bytes'] = total_bytes_all_parts
            status['downloaded_bytes'] = downloaded_bytes_all_parts
            status['current_progress'] = int((downloaded_bytes_all_parts / total_bytes_all_parts) * 100)

    elif d['status'] == 'finished':
        # Marcar esta parte como completada
        part['status'] = 'finished'
        if part['total_bytes'] > 0:
            part['downloaded_bytes'] = part['total_bytes']  # Asegurar que se marca como 100% completado
        
        # Guardar el archivo finalizado
        if not filename.endswith(('.part', '.ytdl', '.f')):
            if 'completed_files' not in status:
                status['completed_files'] = []
            if filename not in status['completed_files']:
                status['completed_files'].append(filename)
        
        # No incrementamos completed_videos aquí, se hará al final
    
    elif d['status'] == 'error':
        part['status'] = 'error'
        status['errors'].append(f"Error durante la descarga del fragmento: {os.path.basename(filename)}")

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
    url = download_options['url']
    
    # Configurar opciones de descarga
    download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
    os.makedirs(download_dir, exist_ok=True)

    common_opts = {
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [lambda d: progress_hook(d, download_id)],
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ignoreerrors': True,
        'noprogress': True, # Desactiva la barra de progreso de yt-dlp en consola
        'quiet': True,
        'no_warnings': True,
        'writeinfojson': True,  # Guardar metadatos para identificar archivos finales
        'writethumbnail': True, # Guardar miniatura
    }

    # Obtener información de la lista/video primero
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': True, 'force_generic_extractor': False}) as ydl:
            info = ydl.extract_info(url, download=False)
            if 'entries' in info:
                valid_entries = [entry for entry in info.get('entries', []) if entry is not None]
                download_status[download_id]['playlist_title'] = info.get('title', 'Playlist')
                download_status[download_id]['total_videos'] = len(valid_entries)
            else:
                download_status[download_id]['playlist_title'] = info.get('title', 'Video')
                download_status[download_id]['total_videos'] = 1
    except Exception as e:
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['errors'].append(f'Error al obtener información: {str(e)}')
        return

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
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',  # Unir en mp4 por defecto
                **common_opts
            }
    else: # single video
        # Para video único, queremos unir video y audio con los formatos seleccionados
        ydl_opts = {
            'format': f"{download_options['video_format_id']}+{download_options['audio_format_id']}/bestvideo+bestaudio/best",
            'merge_output_format': 'mp4', # Unir en mp4 por defecto
            **common_opts
        }
    
    # Iniciar descarga
    try:
        download_status[download_id]['status'] = 'downloading'
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Procesar los archivos finales
        final_files = []
        for filename in os.listdir(download_dir):
            # Ignorar archivos temporales y metadatos
            if filename.endswith(('.part', '.ytdl', '.f', '.json', '.webp', '.jpg')):
                continue
            
            file_path = os.path.join(download_dir, filename)
            if os.path.isfile(file_path):
                final_files.append({
                    'name': filename,
                    'path': file_path,
                    'size': os.path.getsize(file_path),
                    'url': f'/downloads/{download_id}/{filename}'
                })
        
        if final_files:
            download_status[download_id]['status'] = 'completed'
            download_status[download_id]['current_progress'] = 100
            download_status[download_id]['final_files'] = final_files
            download_status[download_id]['completed_videos'] = len(final_files)
            download_status[download_id]['current_stage'] = 'Descarga completada'
        else:
            # Si no hay archivos finales pero no hubo error, puede ser un problema
            if not download_status[download_id]['errors']:
                download_status[download_id]['errors'].append('La descarga finalizó pero no se encontraron archivos. Puede que el formato no sea compatible.')
            download_status[download_id]['status'] = 'error'
            download_status[download_id]['current_stage'] = 'Error en la descarga'
    
    except Exception as e:
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['current_stage'] = 'Error en la descarga'
        download_status[download_id]['errors'].append(f'Error inesperado durante la descarga: {str(e)}')

# Rutas de la aplicación
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/video_info', methods=['POST'])
def get_video_info():
    data = request.json
    url = data.get('url', '')
    if not url or not re.match(r'^(https?\:\/\/)?(www\.youtube\.com|youtu\.?be)\/.*$', url):
        return jsonify({
            'error': 'URL de YouTube inválida.',
            'source': 'backend_validation',
            'details': 'La URL proporcionada no parece ser un enlace de YouTube válido.'
        }), 400

    ydl_opts = {'quiet': True, 'no_warnings': True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
    except yt_dlp.utils.DownloadError as e:
        error_message = str(e)
        user_friendly_message = "No se pudo obtener la información del video desde YouTube. "
        if 'Unsupported URL' in error_message:
            user_friendly_message += "La URL no es compatible."
        elif 'video is unavailable' in error_message.lower():
            user_friendly_message += "El video no está disponible (puede haber sido eliminado)."
        elif 'private video' in error_message.lower():
            user_friendly_message += "El video es privado y no se puede acceder."
        else:
            user_friendly_message += "Verifica la URL e inténtalo de nuevo."
        
        return jsonify({
            'error': user_friendly_message,
            'source': 'yt-dlp',
            'details': error_message
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'Ocurrió un error inesperado en el servidor al procesar la solicitud.',
            'source': 'backend_server',
            'details': str(e)
        }), 500

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
        'total_bytes': 0,
        'downloaded_bytes': 0,
        'speed': 0,
        'eta': 0,
        'elapsed': 0,
        'hook_status': 'pending',
        'current_stage': 'Iniciando...',
        'parts': {},           # Para seguimiento detallado de partes de video/audio
        'completed_files': [],  # Archivos que han terminado de descargarse
        'final_files': [],      # Lista final de archivos con URLs
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
    
    status = download_status[download_id]
    
    # Construir una respuesta simplificada con la información relevante
    response = {
        'status': status['status'],
        'current_stage': status.get('current_stage', 'Procesando...'),
        'current_progress': status.get('current_progress', 0),
        'total_bytes': status.get('total_bytes', 0),
        'downloaded_bytes': status.get('downloaded_bytes', 0),
        'speed': status.get('speed', 0),
        'eta': status.get('eta', 0),
        'elapsed': status.get('elapsed', 0),
        'current_video': status.get('current_video', 'Procesando...'),
        'total_videos': status.get('total_videos', 1),
        'completed_videos': status.get('completed_videos', 0),
        'errors': status.get('errors', [])
    }
    
    # Si la descarga está completa o con error, incluir los archivos finales
    if status['status'] in ['completed', 'error'] and status.get('final_files'):
        response['files'] = [
            {
                'name': f.get('name'),
                'size': f.get('size', 0),
                'url': f.get('url')
            } for f in status.get('final_files', [])
        ]
    
    return jsonify(response)

@app.route('/downloads/<download_id>/<path:filename>', methods=['GET'])
def download_file(download_id, filename):
    # Validar que el ID de descarga existe
    if download_id not in download_status:
        return jsonify({'error': 'ID de descarga no encontrado'}), 404
    
    # Usar el secure_filename para evitar ataques de path traversal
    safe_filename = secure_filename(os.path.basename(filename))
    download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
    
    # Verificar que el directorio existe
    if not os.path.exists(download_dir):
        return jsonify({'error': 'Directorio de descarga no encontrado'}), 404
    
    # Intenta primero con el nombre exacto y luego con el nombre seguro
    try:
        return send_from_directory(download_dir, filename, as_attachment=True)
    except:
        try:
            return send_from_directory(download_dir, safe_filename, as_attachment=True)
        except:
            return jsonify({'error': 'Archivo no encontrado'}), 404

@app.route('/api/downloads/<download_id>', methods=['GET'])
def list_downloads(download_id):
    if download_id not in download_status:
        return jsonify({'error': 'ID de descarga no encontrado'}), 404
    
    status = download_status[download_id]
    download_dir = os.path.join(DOWNLOAD_FOLDER, download_id)
    
    if not os.path.exists(download_dir):
        return jsonify({'error': 'Directorio de descarga no encontrado'}), 404
    
    # Si hay archivos finales ya registrados, usarlos
    if status.get('final_files'):
        return jsonify({
            'files': status['final_files'],
            'status': status['status']
        })
    
    # De lo contrario, escanear el directorio
    files = []
    for filename in os.listdir(download_dir):
        if filename.endswith(('.part', '.ytdl', '.f', '.json', '.webp', '.jpg')):
            continue
        
        file_path = os.path.join(download_dir, filename)
        if os.path.isfile(file_path):
            files.append({
                'name': filename,
                'size': os.path.getsize(file_path),
                'url': f'/downloads/{download_id}/{filename}'
            })
    
    # Guardar en el estado para acceso futuro
    status['final_files'] = files
    
    return jsonify({
        'files': files,
        'status': status['status']
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('DEBUG', 'False').lower() == 'true')