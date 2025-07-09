// download-ui.js - UI profesional para feedback de descarga

function renderDownloadProgress({
    container,
    filename,
    percent,
    downloaded,
    total,
    speed,
    eta,
    elapsed,
    stage // Nuevo parámetro para la etapa actual
}) {
    // Calcular el porcentaje para mostrarlo solo si tenemos bytes totales
    const displayPercent = percent !== undefined ? Math.min(100, Math.max(0, percent)) : 0;
    
    // Determinar clase adicional para la barra según la etapa
    let progressBarClass = "bg-danger";
    let stageText = "";
    
    // Personalizar la barra según la etapa actual
    if (stage && stage.toLowerCase().includes('mezclando')) {
        progressBarClass = "bg-info";
        stageText = `<div class="text-center small text-info mb-2"><i class="bi bi-arrow-repeat"></i> ${stage}</div>`;
    } else if (stage && stage.toLowerCase().includes('codificando')) {
        progressBarClass = "bg-warning";
        stageText = `<div class="text-center small text-warning mb-2"><i class="bi bi-gear-wide-connected"></i> ${stage}</div>`;
    } else if (stage && stage.toLowerCase().includes('completada')) {
        progressBarClass = "bg-success";
        stageText = `<div class="text-center small text-success mb-2"><i class="bi bi-check-circle"></i> ${stage}</div>`;
    }
    
    container.innerHTML = `
        <div class="card shadow-sm border-0 mb-2">
            <div class="card-body py-3">
                <div class="d-flex align-items-center mb-2">
                    <i class="bi bi-file-earmark-play fs-4 text-danger me-2"></i>
                    <span class="fw-semibold">${filename || 'Descargando...'}</span>
                </div>
                ${stageText}
                <div class="progress mb-2" style="height: 25px; position: relative;">
                    <div class="progress-bar progress-bar-striped progress-bar-animated ${progressBarClass}" 
                         role="progressbar" 
                         style="width: ${displayPercent}%; transition: width 0.5s ease-in-out;">
                    </div>
                    <div class="position-absolute w-100 text-center" style="line-height: 25px; color: ${displayPercent > 50 ? 'white' : 'black'}; font-weight: bold; mix-blend-mode: difference;">
                        ${displayPercent}%
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

// Función para mostrar enlaces a los archivos descargados
function renderDownloadLinks({
    container,
    files,
    title = "Descarga completada"
}) {
    if (!files || files.length === 0) {
        container.innerHTML += `
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle"></i> No se encontraron archivos descargados.
            </div>
        `;
        return;
    }

    let linksHtml = '';
    files.forEach(file => {
        const fileSize = typeof file.size === 'number' ? formatFileSize(file.size) : 'Desconocido';
        linksHtml += `
            <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                <div>
                    <i class="bi bi-file-earmark-play text-danger"></i>
                    <span class="ms-2">${file.name}</span>
                </div>
                <div>
                    <small class="text-secondary me-2">${fileSize}</small>
                    <a href="${file.url}" class="btn btn-sm btn-outline-primary" download>
                        <i class="bi bi-download"></i> Descargar
                    </a>
                </div>
            </div>
        `;
    });

    container.innerHTML += `
        <div class="card shadow-sm border-0 mb-3">
            <div class="card-header bg-success text-white">
                <i class="bi bi-check-circle"></i> ${title}
            </div>
            <div class="list-group list-group-flush">
                ${linksHtml}
            </div>
        </div>
    `;
}

// Exportar para uso global
window.renderDownloadProgress = renderDownloadProgress;
window.renderDownloadLinks = renderDownloadLinks;
