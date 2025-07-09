// app.js - Lógica principal modularizada para Youtube-dl

// Utilidades de UI
function showSpinner(container, message = 'Cargando...') {
    container.innerHTML = `<div class="d-flex align-items-center justify-content-center py-4">
        <div class="spinner-border text-danger me-2" role="status"></div>
        <span>${message}</span>
    </div>`;
}
function hideSpinner(container) {
    container.innerHTML = '';
}

// Formateo de bytes y tiempo
function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}
function formatTime(seconds) {
    if (!seconds || seconds < 0 || isNaN(seconds)) return '--:--';
    
    // Para tiempos largos, mostrar horas
    if (seconds >= 3600) {
        const h = Math.floor(seconds / 3600);
        const m = Math.floor((seconds % 3600) / 60);
        const s = Math.floor(seconds % 60);
        return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}
}

// Estado global de descargas
const statusIntervals = {};
const downloadTimers = {}; // Para controlar el tiempo transcurrido en cada descarga

// Inicialización principal
function initApp() {
    const playlistDownloadForm = document.getElementById('playlist-download-form');
    const singleVideoForm = document.getElementById('single-video-form');
    const downloadsContainer = document.getElementById('downloads-container');
    const downloadTemplate = document.getElementById('download-template');
    const getVideoInfoBtn = document.getElementById('get-video-info-btn');
    const videoInfoContainer = document.getElementById('video-info-container');
    const startSingleDownloadBtn = document.getElementById('start-single-download-btn');
    const videoFormatSelect = document.getElementById('video-format-select');
    const audioFormatSelect = document.getElementById('audio-format-select');

    // Feedback de carga al obtener info del video
    getVideoInfoBtn.addEventListener('click', function() {
        const videoUrl = document.getElementById('video-url').value.trim();
        const feedbackContainer = document.getElementById('video-feedback-container');
        feedbackContainer.innerHTML = ''; // Limpiar feedback anterior

        if (!videoUrl) {
            alert('Por favor, ingresa la URL de un video.');
            return;
        }
        videoInfoContainer.classList.add('d-none');
        showSpinner(feedbackContainer, 'Obteniendo información del video...'); // Usar el contenedor de feedback
        getVideoInfoBtn.disabled = true;
        let didRespond = false;
        
        // Timeout de 15 segundos para feedback
        const timeoutId = setTimeout(() => {
            if (!didRespond) {
                hideSpinner(feedbackContainer); // Usar el contenedor de feedback
                getVideoInfoBtn.disabled = false;
                feedbackContainer.innerHTML = '<div class="alert alert-warning">La consulta está tardando más de lo normal. Verifica tu conexión o intenta con otro video.</div>';
            }
        }, 15000);

        fetch('/api/video_info', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: videoUrl })
        })
        .then(response => response.json())
        .then(data => {
            didRespond = true;
            clearTimeout(timeoutId);
            hideSpinner(feedbackContainer); // Usar el contenedor de feedback
            getVideoInfoBtn.disabled = false;
            if (data.error) {
                // Mostrar error detallado
                let errorMessage = `<div class='alert alert-danger'>
                    <strong>Error:</strong> ${data.error}<br>
                    <small class="text-muted">Fuente: ${data.source || 'Desconocida'}</small><br>
                    <small class="text-muted">Detalles: ${data.details || 'No disponibles'}</small>
                </div>`;
                feedbackContainer.innerHTML = errorMessage;
                return;
            }
            populateVideoInfo(data, videoFormatSelect, audioFormatSelect);
            videoInfoContainer.classList.remove('d-none');
        })
        .catch(error => {
            didRespond = true;
            clearTimeout(timeoutId);
            hideSpinner(feedbackContainer); // Usar el contenedor de feedback
            getVideoInfoBtn.disabled = false;
            feedbackContainer.innerHTML = `<div class='alert alert-danger'>Error al obtener información del video: ${error}</div>`;
        });
    });

    // Mejor feedback al iniciar descarga de video único
    startSingleDownloadBtn.addEventListener('click', function() {
        const videoUrl = document.getElementById('video-url').value.trim();
        const videoFormat = document.getElementById('video-format-select').value;
        const audioFormat = document.getElementById('audio-format-select').value;
        const feedbackContainer = document.getElementById('video-feedback-container');
        feedbackContainer.innerHTML = '';
        if (!videoUrl || !videoFormat || !audioFormat) {
            feedbackContainer.innerHTML = '<div class="alert alert-warning">Por favor, selecciona los formatos y la URL antes de descargar.</div>';
            return;
        }
        showSpinner(feedbackContainer, 'Preparando descarga...');
        startSingleDownloadBtn.disabled = true;
        fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                url: videoUrl, 
                type: 'single', 
                video_format_id: videoFormat,
                audio_format_id: audioFormat
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                feedbackContainer.innerHTML = `<div class='alert alert-danger'>${data.error}</div>`;
                startSingleDownloadBtn.disabled = false;
                return;
            }
            // Iniciar feedback profesional de progreso
            const downloadId = data.download_id;
            let lastDownloaded = 0;
            
            // Inicializar el timer para esta descarga
            downloadTimers[downloadId] = {
                startTime: Date.now(),
                lastUpdateTime: Date.now(),
                totalElapsed: 0,
                running: true
            };
            
            statusIntervals[downloadId] = setInterval(() => {
                fetch(`/api/status/${downloadId}`)
                    .then(r => r.json())
                    .then(status => {
                        if (status.error) {
                            feedbackContainer.innerHTML = `<div class='alert alert-danger'>${status.error}</div>`;
                            clearInterval(statusIntervals[downloadId]);
                            startSingleDownloadBtn.disabled = false;
                            downloadTimers[downloadId].running = false;
                            return;
                        }
                        
                        // Calcular métricas
                        const percent = status.current_progress || 0;
                        const downloaded = status.downloaded_bytes || 0;
                        const total = status.total_bytes || 0;
                        
                        // Calcular tiempo transcurrido (acumulativo)
                        const timer = downloadTimers[downloadId];
                        const now = Date.now();
                        // Tiempo transcurrido desde la última actualización
                        const elapsedSinceLastUpdate = (now - timer.lastUpdateTime) / 1000;
                        
                        // Usar el tiempo del servidor si está disponible, de lo contrario, calcular localmente
                        let elapsedTime;
                        if (status.elapsed && status.elapsed > 0) {
                            elapsedTime = status.elapsed; // Tiempo reportado por yt-dlp
                        } else {
                            // Tiempo transcurrido desde el inicio
                            elapsedTime = timer.totalElapsed + elapsedSinceLastUpdate;
                        }
                        
                        // Actualizar el timer para la próxima iteración
                        timer.lastUpdateTime = now;
                        timer.totalElapsed = elapsedTime;
                        
                        // Calcular velocidad y ETA
                        let speed = 0, eta = 0;
                        
                        // Usar la velocidad proporcionada por el backend si está disponible
                        if (status.speed && status.speed > 0) {
                            speed = status.speed / (1024 * 1024); // Convertir a MB/s
                            eta = status.eta || 0;
                        } else if (downloaded > lastDownloaded && elapsedSinceLastUpdate > 0) {
                            // Calcular basado en la cantidad descargada desde la última actualización
                            const bytesDownloadedSinceLastUpdate = downloaded - lastDownloaded;
                            speed = (bytesDownloadedSinceLastUpdate / 1024 / 1024) / elapsedSinceLastUpdate;
                            
                            // Calcular ETA basado en la velocidad actual y los bytes restantes
                            if (speed > 0 && total > downloaded) {
                                eta = (total - downloaded) / (speed * 1024 * 1024);
                            }
                        }
                        
                        lastDownloaded = downloaded;
                        
                        // Mostrar la etapa actual del proceso
                        let stageInfo = '';
                        if (status.current_stage) {
                            stageInfo = `<div class="text-center small text-muted mb-2">${status.current_stage}</div>`;
                            feedbackContainer.innerHTML = stageInfo;
                        }
                        
                        window.renderDownloadProgress({
                            container: feedbackContainer,
                            filename: status.current_video || 'Descargando...',
                            percent,
                            downloaded,
                            total,
                            speed: speed ? speed.toFixed(2) : null,
                            eta,
                            elapsed: elapsedTime
                        });
                        
                        // Si la descarga ha terminado
                        if (status.status === 'completed' || status.status === 'partial' || status.status === 'error') {
                            clearInterval(statusIntervals[downloadId]);
                            startSingleDownloadBtn.disabled = false;
                            
                            if (status.status === 'completed') {
                                feedbackContainer.innerHTML += '<div class="alert alert-success mt-2">¡Descarga completada!</div>';
                                
                                // Mostrar enlaces a los archivos descargados si están disponibles
                                if (status.files && status.files.length > 0) {
                                    window.renderDownloadLinks({
                                        container: feedbackContainer,
                                        files: status.files,
                                        title: "Archivos descargados"
                                    });
                                } else {
                                    // Si no hay archivos en la respuesta, buscar en el endpoint específico
                                    fetch(`/api/downloads/${downloadId}`)
                                        .then(r => r.json())
                                        .then(data => {
                                            if (data.files && data.files.length > 0) {
                                                window.renderDownloadLinks({
                                                    container: feedbackContainer,
                                                    files: data.files,
                                                    title: "Archivos descargados"
                                                });
                                            } else {
                                                feedbackContainer.innerHTML += '<div class="alert alert-warning mt-2">No se encontraron archivos para descargar.</div>';
                                            }
                                        })
                                        .catch(err => {
                                            console.error("Error al obtener archivos:", err);
                                            feedbackContainer.innerHTML += '<div class="alert alert-warning mt-2">No se pudieron obtener los archivos descargados.</div>';
                                        });
                                }
                            } else if (status.status === 'partial') {
                                feedbackContainer.innerHTML += '<div class="alert alert-warning mt-2">Descarga parcial. Algunos archivos pueden faltar.</div>';
                                // Intentar mostrar los archivos parciales
                                fetch(`/api/downloads/${downloadId}`)
                                    .then(r => r.json())
                                    .then(data => {
                                        if (data.files && data.files.length > 0) {
                                            window.renderDownloadLinks({
                                                container: feedbackContainer,
                                                files: data.files,
                                                title: "Archivos disponibles (descarga parcial)"
                                            });
                                        }
                                    });
                            } else if (status.status === 'error') {
                                // Mostrar errores específicos si están disponibles
                                if (status.errors && status.errors.length > 0) {
                                    const errorList = status.errors.map(err => `<li>${err}</li>`).join('');
                                    feedbackContainer.innerHTML += `
                                        <div class="alert alert-danger mt-2">
                                            <p><strong>Ocurrieron errores durante la descarga:</strong></p>
                                            <ul>${errorList}</ul>
                                        </div>
                                    `;
                                } else {
                                    feedbackContainer.innerHTML += '<div class="alert alert-danger mt-2">Ocurrió un error durante la descarga.</div>';
                                }
                            }
                        }
                    });
            }, 1000);
        })
        .catch(error => {
            feedbackContainer.innerHTML = `<div class='alert alert-danger'>${error}</div>`;
            startSingleDownloadBtn.disabled = false;
        });
    });

    // Mejor feedback al iniciar descarga de playlist
    playlistDownloadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const playlistUrl = document.getElementById('playlist-url').value.trim();
        const formatOption = document.querySelector('input[name="playlist-format"]:checked').value;
        const downloadsContainer = document.getElementById('downloads-container');
        if (!playlistUrl) {
            downloadsContainer.innerHTML = '<div class="alert alert-warning">Por favor, ingresa una URL válida de YouTube para la lista.</div>';
            return;
        }
        // Crear un contenedor visual para la descarga
        const feedbackContainer = document.createElement('div');
        downloadsContainer.prepend(feedbackContainer);
        showSpinner(feedbackContainer, 'Preparando descarga de lista...');
        fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: playlistUrl, format: formatOption, type: 'playlist' })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                feedbackContainer.innerHTML = `<div class='alert alert-danger'>${data.error}</div>`;
                return;
            }
            // Iniciar feedback profesional de progreso para playlist
            const downloadId = data.download_id;
            let lastDownloaded = 0;
            let lastTime = Date.now();
            let elapsed = 0;
            statusIntervals[downloadId] = setInterval(() => {
                fetch(`/api/status/${downloadId}`)
                    .then(r => r.json())
                    .then(status => {
                        if (status.error) {
                            feedbackContainer.innerHTML = `<div class='alert alert-danger'>${status.error}</div>`;
                            clearInterval(statusIntervals[downloadId]);
                            return;
                        }
                        // Calcular métricas
                        const percent = status.total_videos > 0 ? Math.round((status.completed_videos / status.total_videos) * 100) : 0;
                        const downloaded = status.downloaded_bytes || 0;
                        const total = status.total_bytes || 0;
                        const now = Date.now();
                        elapsed = (elapsed === 0 && percent > 0) ? 1 : Math.floor((now - lastTime) / 1000);
                        let speed = 0, eta = 0;
                        
                        // Usar la velocidad proporcionada por el backend o calcularla
                        if (status.speed && status.speed > 0) {
                            speed = status.speed / (1024 * 1024); // Convertir a MB/s
                            eta = status.eta || 0;
                        } else if (downloaded > 0 && elapsed > 0) {
                            speed = ((downloaded - lastDownloaded) / 1024 / 1024) / (elapsed || 1);
                            eta = speed > 0 ? ((total - downloaded) / 1024 / 1024) / speed : 0;
                        }
                        
                        lastDownloaded = downloaded;
                        lastTime = now;
                        
                        // Mostrar la etapa actual
                        let stageInfo = '';
                        if (status.current_stage) {
                            stageInfo = `<div class="text-center small text-muted mb-2">${status.current_stage}</div>`;
                            feedbackContainer.innerHTML = stageInfo;
                        }
                        
                        window.renderDownloadProgress({
                            container: feedbackContainer,
                            filename: status.current_video || 'Descargando...',
                            percent,
                            downloaded,
                            total,
                            speed: speed ? speed.toFixed(2) : null,
                            eta,
                            elapsed
                        });
                        
                        // Mostrar progreso de videos
                        if (status.total_videos > 1) {
                            feedbackContainer.innerHTML += `<div class='text-center small text-muted mt-1'>Videos completados: <b>${status.completed_videos}</b> de <b>${status.total_videos}</b></div>`;
                        }
                        
                        // Si la descarga ha terminado
                        if (status.status === 'completed' || status.status === 'partial' || status.status === 'error') {
                            clearInterval(statusIntervals[downloadId]);
                            
                            if (status.status === 'completed') {
                                feedbackContainer.innerHTML += '<div class="alert alert-success mt-2">¡Descarga de lista completada!</div>';
                                
                                // Mostrar enlaces a los archivos descargados si están disponibles
                                if (status.files && status.files.length > 0) {
                                    window.renderDownloadLinks({
                                        container: feedbackContainer,
                                        files: status.files,
                                        title: "Videos descargados"
                                    });
                                } else {
                                    // Si no hay archivos en la respuesta, buscar en el endpoint específico
                                    fetch(`/api/downloads/${downloadId}`)
                                        .then(r => r.json())
                                        .then(data => {
                                            if (data.files && data.files.length > 0) {
                                                window.renderDownloadLinks({
                                                    container: feedbackContainer,
                                                    files: data.files,
                                                    title: "Videos descargados"
                                                });
                                            } else {
                                                feedbackContainer.innerHTML += '<div class="alert alert-warning mt-2">No se encontraron archivos para descargar.</div>';
                                            }
                                        })
                                        .catch(err => {
                                            console.error("Error al obtener archivos:", err);
                                            feedbackContainer.innerHTML += '<div class="alert alert-warning mt-2">No se pudieron obtener los archivos descargados.</div>';
                                        });
                                }
                            } else if (status.status === 'partial') {
                                feedbackContainer.innerHTML += '<div class="alert alert-warning mt-2">Descarga parcial. Algunos videos pueden faltar.</div>';
                                // Intentar mostrar los archivos parciales
                                fetch(`/api/downloads/${downloadId}`)
                                    .then(r => r.json())
                                    .then(data => {
                                        if (data.files && data.files.length > 0) {                                                window.renderDownloadLinks({
                                                container: feedbackContainer,
                                                files: data.files,
                                                title: "Videos disponibles (descarga parcial)"
                                            });
                                        }
                                    });
                            } else if (status.status === 'error') {
                                // Mostrar errores específicos si están disponibles
                                if (status.errors && status.errors.length > 0) {
                                    const errorList = status.errors.map(err => `<li>${err}</li>`).join('');
                                    feedbackContainer.innerHTML += `
                                        <div class="alert alert-danger mt-2">
                                            <p><strong>Ocurrieron errores durante la descarga:</strong></p>
                                            <ul>${errorList}</ul>
                                        </div>
                                    `;
                                } else {
                                    feedbackContainer.innerHTML += '<div class="alert alert-danger mt-2">Ocurrió un error durante la descarga.</div>';
                                }
                            }
                        }
                    });
            }, 1000);
        })
        .catch(error => {
            feedbackContainer.innerHTML = `<div class='alert alert-danger'>${error}</div>`;
        });
    });

    // ...El resto de la lógica se modularizará aquí (descarga de lista de reproducción, etc)...
}

// Modularización de la función para poblar info de video
function populateVideoInfo(data, videoSelect, audioSelect) {
    document.getElementById('video-title').textContent = data.title;
    videoSelect.innerHTML = '';
    audioSelect.innerHTML = '';
    // ...igual que antes, pero modularizado...
    const videoFormats = data.formats
        .filter(f => f.vcodec !== 'none' && f.acodec === 'none')
        .sort((a, b) => {
            const heightA = parseInt((a.resolution || '').split('x')[1]) || 0;
            const heightB = parseInt((b.resolution || '').split('x')[1]) || 0;
            return heightB - heightA;
        });
    videoFormats.forEach(f => {
        const option = document.createElement('option');
        option.value = f.format_id;
        const height = (f.resolution || '').split('x')[1] || 'N/A';
        const fps = f.fps ? `${f.fps}fps` : '';
        const size = f.filesize_approx ? formatFileSize(f.filesize_approx) : 'N/A';
        option.textContent = `${height}p ${fps} - ${f.ext} - ${size}`;
        videoSelect.appendChild(option);
    });
    if (videoFormats.length === 0) {
        data.formats
            .filter(f => f.vcodec !== 'none' && f.acodec !== 'none')
            .sort((a, b) => {
                const heightA = parseInt((a.resolution || '').split('x')[1]) || 0;
                const heightB = parseInt((b.resolution || '').split('x')[1]) || 0;
                return heightB - heightA;
            })
            .forEach(f => {
                const option = document.createElement('option');
                option.value = f.format_id;
                const height = (f.resolution || '').split('x')[1] || 'N/A';
                const fps = f.fps ? `${f.fps}fps` : '';
                const size = f.filesize_approx ? formatFileSize(f.filesize_approx) : 'N/A';
                option.textContent = `${height}p ${fps} - ${f.ext} - ${size} (con audio)`;
                videoSelect.appendChild(option);
            });
    }
    const audioFormats = data.formats
        .filter(f => f.acodec !== 'none' && f.vcodec === 'none')
        .sort((a, b) => (b.abr || 0) - (a.abr || 0));
    audioFormats.forEach(f => {
        const option = document.createElement('option');
        option.value = f.format_id;
        const abr = f.abr ? `${f.abr}kbps` : 'N/A';
        const size = f.filesize_approx ? formatFileSize(f.filesize_approx) : 'N/A';
        option.textContent = `${f.ext} - ${abr} - ${size}`;
        audioSelect.appendChild(option);
    });
    if (videoSelect.children.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No hay formatos de video disponibles';
        option.disabled = true;
        videoSelect.appendChild(option);
    }
    if (audioSelect.children.length === 0) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No hay formatos de audio disponibles';
        option.disabled = true;
        audioSelect.appendChild(option);
    }
}

// Inicializar la app al cargar
window.addEventListener('DOMContentLoaded', initApp);
