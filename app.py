import os
import re
import json
import time
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

# Configuración mejorada de yt-dlp para optimizar las descargas
def get_ytdlp_config(download_type, options):
    """
    Genera una configuración optimizada de yt-dlp basada en el tipo de descarga y opciones.
    Esta configuración sigue las mejores prácticas recomendadas por expertos en yt-dlp.
    """
    # Configuración base optimizada para todas las descargas
    base_config = {
        'retries': 10,                     # Reintentos automáticos si falla la descarga
        'fragment_retries': 10,            # Reintentos para fragmentos individuales
        'skip_unavailable_fragments': True, # Continuar incluso si algunos fragmentos fallan
        'ignoreerrors': True,              # Ignorar errores en playlists y continuar
        'noprogress': True,                # Desactivar barra de progreso en consola
        'quiet': True,                     # Reducir salida a consola
        'no_warnings': True,               # Ocultar advertencias
        'socket_timeout': 30,              # Timeout para conexiones
        'http_chunk_size': 10485760,       # 10MB por chunk para mejor rendimiento
        'buffersize': 1024*1024,           # 1MB de buffer para mejor velocidad
        'nocheckcertificate': True,        # Ignorar problemas con certificados SSL
        'extractor_retries': 3,            # Reintentos para extractores
        'postprocessor_hooks': [lambda d: postprocessor_hook(d, options.get('download_id'))], # Hook para etapas de post-procesamiento
    }
    
    # Agregar opciones específicas para el tipo de descarga
    if download_type == 'single':
        # Para videos individuales, optimizar la mezcla de formatos
        base_config.update({
            'format': options.get('format', 'bestvideo+bestaudio/best'),
            'merge_output_format': 'mp4',   # Formato universal compatible
            'postprocessor_args': {
                'ffmpeg': ['-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k'], # Mantener video, optimizar audio
            },
        })
    elif download_type == 'playlist':
        # Para playlists, optimizar para múltiples descargas
        base_config.update({
            'playlist_items': '1-1000',
            'concurrent_fragment_downloads': 3,  # Descargar múltiples fragmentos a la vez
        })
        
        if options.get('format') == 'audio':
            base_config.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else: # video
            base_config.update({
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'merge_output_format': 'mp4',
            })
            
    return base_config

# Hook para capturar eventos de post-procesamiento
def postprocessor_hook(d, download_id):
    if not download_id or download_id not in download_status:
        return
        
    status = download_status[download_id]
    
    # Capturar el tipo de postprocesador y su estado
    pp_type = d.get('postprocessor')
    action = d.get('status')
    
    if pp_type and action:
        # Actualizar la etapa actual basada en el postprocesador
        if pp_type == 'MoveFiles' and action == 'started':
            status['current_stage'] = 'Organizando archivos...'
        elif pp_type == 'Merger' and action == 'started':
            status['current_stage'] = 'Mezclando video y audio...'
            # Establecer explícitamente progreso al 100% durante la mezcla
            status['current_progress'] = 100
            status['merging'] = True
        elif pp_type == 'FFmpegVideoConvertor' and action == 'started':
            status['current_stage'] = 'Codificando video...'
            status['current_progress'] = 100
            status['encoding'] = True
        elif pp_type == 'FFmpegExtractAudio' and action == 'started':
            status['current_stage'] = 'Extrayendo audio...'
            status['current_progress'] = 100
            status['extracting_audio'] = True
        elif pp_type == 'FFmpegMetadata' and action == 'started':
            status['current_stage'] = 'Añadiendo metadatos...'
        
        # Marcar como completado cuando finaliza
        if action == 'finished':
            if pp_type == 'Merger':
                status['merging'] = False
            elif pp_type == 'FFmpegVideoConvertor':
                status['encoding'] = False
            elif pp_type == 'FFmpegExtractAudio':
                status['extracting_audio'] = False
                
            # Si este es el último postprocesador, actualizar etapa
            if all(not status.get(k, False) for k in ['merging', 'encoding', 'extracting_audio']):
                status['current_stage'] = 'Procesamiento completado'

# Función para manejar el progreso con cálculos más estables
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
    
    # Inicializar historial de velocidad si no existe
    if 'speed_history' not in status:
        status['speed_history'] = []
    
    # Inicializar tiempo de inicio si no existe
    if 'start_time' not in status:
        status['start_time'] = time.time()
    
    # Crear una clave única para esta parte del proceso
    part_key = format_id
    
    # Detectar si estamos en fase de mezcla por el nombre del archivo
    if '_mp4' in filename or '.mp4.' in filename or '.mkv.' in filename or '.temp.' in filename:
        part_key = 'merge'
        status['current_stage'] = 'Mezclando video y audio...'
        status['merging'] = True
    elif 'merging' in d.get('status', '').lower():
        # También detectar por el status de yt-dlp
        status['current_stage'] = 'Mezclando video y audio...'
        status['merging'] = True
    
    # Inicializar la entrada para esta parte si no existe
    if part_key not in status['parts']:
        status['parts'][part_key] = {
            'total_bytes': 0,
            'downloaded_bytes': 0,
            'status': 'pending',
            'last_update': time.time(),
            'last_bytes': 0
        }
    
    part = status['parts'][part_key]
    
    status['hook_status'] = d['status']
    
    # Establecer la etapa actual si no estamos en un post-procesamiento
    if not any(status.get(k, False) for k in ['merging', 'encoding', 'extracting_audio']):
        if part_key == 'merge':
            status['current_stage'] = 'Mezclando video y audio...'
        else:
            status['current_stage'] = f"Descargando {part_key}..."
    
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
        
        # Calcular y suavizar la velocidad de descarga
        current_time = time.time()
        time_diff = current_time - part.get('last_update', current_time - 1)
        
        if time_diff > 0 and 'last_bytes' in part:
            bytes_diff = downloaded_bytes - part.get('last_bytes', 0)
            if bytes_diff > 0:
                # Calcular velocidad instantánea
                current_speed = bytes_diff / time_diff
                
                # Añadir a historial para suavizar (solo las últimas 5 muestras)
                status['speed_history'].append(current_speed)
                if len(status['speed_history']) > 5:
                    status['speed_history'].pop(0)
                
                # Calcular velocidad promedio
                avg_speed = sum(status['speed_history']) / len(status['speed_history'])
                status['speed'] = avg_speed
            else:
                # Si no hay progreso, usar el último valor o el reportado por yt-dlp
                status['speed'] = status.get('speed') or d.get('speed', 0)
        else:
            # Usar la velocidad reportada por yt-dlp si está disponible
            reported_speed = d.get('speed')
            if reported_speed:
                status['speed'] = reported_speed
        
        # Actualizar para la próxima iteración
        part['last_update'] = current_time
        part['last_bytes'] = downloaded_bytes
        
        # Calcular tiempo transcurrido desde el inicio de la descarga
        status['elapsed'] = time.time() - status.get('start_time', time.time())
        
        # Calcular ETA basado en la velocidad promedio
        if status.get('speed', 0) > 0:
            # Calcular bytes restantes
            total_bytes_all_parts = sum(p.get('total_bytes', 0) for p in status['parts'].values())
            downloaded_bytes_all_parts = sum(p.get('downloaded_bytes', 0) for p in status['parts'].values())
            
            if total_bytes_all_parts > downloaded_bytes_all_parts:
                remaining_bytes = total_bytes_all_parts - downloaded_bytes_all_parts
                status['eta'] = remaining_bytes / status['speed']
            else:
                status['eta'] = 0
        else:
            # Si no podemos calcular, usar el ETA reportado por yt-dlp
            status['eta'] = d.get('eta', 0)
        
        # Calcular el progreso general combinando todas las partes
        total_bytes_all_parts = sum(p.get('total_bytes', 0) for p in status['parts'].values())
        downloaded_bytes_all_parts = sum(p.get('downloaded_bytes', 0) for p in status['parts'].values())
        
        if total_bytes_all_parts > 0:
            status['total_bytes'] = total_bytes_all_parts
            status['downloaded_bytes'] = downloaded_bytes_all_parts
            # Si estamos mezclando, mantener el progreso en 99% hasta que termine
            if status.get('merging', False) or status.get('encoding', False) or status.get('extracting_audio', False):
                status['current_progress'] = 99
            else:
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
        
        # Si detectamos que todas las partes están descargadas, establecer la etapa de mezcla
        all_parts_finished = all(p.get('status') == 'finished' for p in status['parts'].values())
        if all_parts_finished and not status.get('current_stage', '').startswith('Mezclando'):
            status['current_stage'] = 'Mezclando video y audio...'
            status['current_progress'] = 99  # Mantener en 99% durante la mezcla
            status['merging'] = True
    
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

    # Añadir el download_id a las opciones para que los hooks lo tengan disponible
    download_options['download_id'] = download_id
    
    # Obtener configuración optimizada de yt-dlp
    base_config = get_ytdlp_config(download_options['type'], download_options)
    
    # Configurar ruta de salida y hooks de progreso
    base_config.update({
        'outtmpl': os.path.join(download_dir, '%(title)s.%(ext)s'),
        'progress_hooks': [lambda d: progress_hook(d, download_id)],
        'writeinfojson': True,  # Guardar metadatos para identificar archivos finales
        'writethumbnail': True, # Guardar miniatura
    })

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

    # Configurar opciones específicas según el tipo de descarga
    if download_options['type'] == 'single':
        # Para video único, usar los formatos seleccionados por el usuario
        base_config['format'] = f"{download_options['video_format_id']}+{download_options['audio_format_id']}/bestvideo+bestaudio/best"
    
    # Si es una playlist, las opciones ya estarán configuradas por get_ytdlp_config
    
    # Iniciar descarga
    try:
        download_status[download_id]['status'] = 'downloading'
        with yt_dlp.YoutubeDL(base_config) as ydl:
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

    # Inicializar un estado de descarga profesional y completo
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
        'speed_history': [],       # Para suavizar las fluctuaciones
        'eta': 0,
        'start_time': time.time(), # Tiempo de inicio preciso
        'elapsed': 0,
        'hook_status': 'pending',
        'current_stage': 'Iniciando...',
        'parts': {},               # Para seguimiento detallado de partes
        'completed_files': [],     # Archivos completados
        'final_files': [],         # Archivos finales con URLs
        'errors': []
    }

    thread = threading.Thread(target=download_videos, args=(data, download_id))
    thread.daemon = True
    thread.start()

    return jsonify({'download_id': download_id})

@app.route('/api/status/<download_id>', methods=['GET'])
def download_status_api(download_id):
    if download_id not in download_status:
        return jsonify({'error': 'ID de descarga no encontrado'})
    
    status_data = download_status[download_id].copy()
    
    # Comprobar si estamos en fase de post-procesamiento
    is_postprocessing = False
    if status_data.get('merging', False) or status_data.get('encoding', False) or status_data.get('extracting_audio', False):
        is_postprocessing = True
        
    # Si hemos terminado de descargar todas las partes pero todavía estamos en postprocesamiento
    all_parts_finished = all(p.get('status') == 'finished' for p in status_data.get('parts', {}).values()) if status_data.get('parts') else False
    
    if all_parts_finished and is_postprocessing:
        # Actualizar la etapa para mostrar el post-procesamiento
        if not status_data.get('current_stage') or 'Descargando' in status_data.get('current_stage', ''):
            if status_data.get('merging', False):
                status_data['current_stage'] = 'Mezclando video y audio...'
            elif status_data.get('encoding', False):
                status_data['current_stage'] = 'Codificando video...'
            elif status_data.get('extracting_audio', False):
                status_data['current_stage'] = 'Extrayendo audio...'
        
        # Mantener el progreso en 99% durante post-procesamiento
        status_data['current_progress'] = 99
    
    # Preparar archivos para la respuesta
    if 'final_files' in status_data:
        status_data['files'] = [
            {
                'name': os.path.basename(f['path']),
                'size': f['size'],
                'url': f['url']
            } for f in status_data['final_files']
        ]
    
    # Eliminar información interna que no queremos exponer en la API
    keys_to_remove = ['final_files', 'parts', 'speed_history', 'completed_files', 'hook_status']
    for key in keys_to_remove:
        if key in status_data:
            del status_data[key]
    
    return jsonify(status_data)

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