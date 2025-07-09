#!/bin/bash

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
echo "Instalando dependencias..."
pip install -r requirements.txt

# Crear directorios necesarios
mkdir -p downloads logs

# Iniciar la aplicación
echo "Iniciando la aplicación..."
python app.py