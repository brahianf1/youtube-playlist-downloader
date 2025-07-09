@echo off
echo Iniciando Descargador de Listas de YouTube...

:: Crear entorno virtual si no existe
if not exist venv (
    echo Creando entorno virtual...
    python -m venv venv
)

:: Activar entorno virtual
echo Activando entorno virtual...
call venv\Scripts\activate.bat

:: Instalar dependencias
echo Instalando dependencias...
pip install -r requirements.txt

:: Crear directorios necesarios
if not exist downloads mkdir downloads
if not exist logs mkdir logs

:: Iniciar la aplicación
echo Iniciando la aplicación...
python app.py

pause