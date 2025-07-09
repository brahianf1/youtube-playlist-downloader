// download-ui.js - UI profesional para feedback de descarga

function renderDownloadProgress({
    container,
    filename,
    percent,
    downloaded,
    total,
    speed,
    eta,
    elapsed
}) {
    container.innerHTML = `
        <div class="card shadow-sm border-0 mb-2">
            <div class="card-body py-3">
                <div class="d-flex align-items-center mb-2">
                    <i class="bi bi-file-earmark-play fs-4 text-danger me-2"></i>
                    <span class="fw-semibold">${filename || 'Descargando...'}</span>
                </div>
                <div class="progress mb-2" style="height: 22px;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated bg-danger" role="progressbar" style="width: ${percent}%">
                        ${percent}%
                    </div>
                </div>
                <div class="row small text-secondary">
                    <div class="col-6">
                        <i class="bi bi-arrow-down-circle"></i> ${formatFileSize(downloaded)} / ${formatFileSize(total)}
                    </div>
                    <div class="col-6 text-end">
                        <i class="bi bi-speedometer2"></i> ${speed ? speed + ' MB/s' : '--'}
                    </div>
                </div>
                <div class="row small mt-1">
                    <div class="col-6">
                        <i class="bi bi-clock-history"></i> Transcurrido: ${formatTime(elapsed)}
                    </div>
                    <div class="col-6 text-end">
                        <i class="bi bi-hourglass-split"></i> Restante: ${formatTime(eta)}
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Exportar para uso global
window.renderDownloadProgress = renderDownloadProgress;
