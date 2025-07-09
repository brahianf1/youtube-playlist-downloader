# Descargador de Listas de YouTube

Esta aplicación web permite descargar listas de reproducción completas de YouTube con un solo clic. Puedes elegir entre descargar los videos completos o solo el audio en formato MP3.

## Características

- Interfaz web intuitiva y fácil de usar
- Descarga automática de listas de reproducción completas
- Opción para descargar videos completos o solo audio (MP3)
- Visualización en tiempo real del progreso de descarga
- Acceso directo a los archivos descargados desde la interfaz

## Requisitos previos

Para ejecutar esta aplicación, necesitas tener instalado:

- Docker y Docker Compose (recomendado para facilitar la instalación)

O alternativamente:

- Python 3.8 o superior
- FFmpeg (para el procesamiento de audio/video)

## Despliegue en DigitalOcean

### Opción 1: Despliegue con un solo clic

[![Deploy to DigitalOcean](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/brahianf1/youtube-playlist-downloader/tree/main)

1. Haz clic en el botón "Deploy to DigitalOcean" de arriba
2. Inicia sesión en tu cuenta de DigitalOcean (o crea una nueva)
3. La configuración se cargará automáticamente desde el archivo `.do/deploy.template.yaml`
4. Haz clic en "Next" y luego en "Create Resources"
5. Espera a que se complete el despliegue
6. ¡Listo! Tu aplicación estará disponible en la URL proporcionada por DigitalOcean

### Opción 2: Usando App Platform manualmente

1. Crea una cuenta en [DigitalOcean](https://www.digitalocean.com/) si aún no tienes una
2. Haz clic en "Create" y selecciona "Apps"
3. Conecta tu repositorio de GitHub o sube este código directamente
4. Configura la aplicación:
   - Tipo: Web Service
   - Fuente: Dockerfile
   - Puerto HTTP: 8000
5. Haz clic en "Next" y luego en "Create Resources"

### Opción 3: Usando Droplets con Docker

1. Crea un Droplet en DigitalOcean (recomendado: Ubuntu 20.04 LTS)
2. Conéctate a tu Droplet mediante SSH
3. Instala Docker y Docker Compose:

```bash
# Actualizar paquetes
sudo apt update

# Instalar dependencias
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Añadir clave GPG de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

# Añadir repositorio de Docker
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"

# Actualizar paquetes e instalar Docker
sudo apt update
sudo apt install -y docker-ce

# Instalar Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.12.2/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

4. Clona o sube este repositorio a tu Droplet
5. Navega al directorio del proyecto y ejecuta:

```bash
sudo docker-compose up -d
```

6. La aplicación estará disponible en `http://tu-ip-droplet:8000`

## Instalación local

### Usando Docker (recomendado)

1. Clona este repositorio
2. Navega al directorio del proyecto
3. Ejecuta:

```bash
docker-compose up -d
```

4. Accede a la aplicación en `http://localhost:8000`

### Instalación manual

1. Clona este repositorio
2. Navega al directorio del proyecto
3. Crea un entorno virtual e instala las dependencias:

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt
```

4. Ejecuta la aplicación:

```bash
python app.py
```

5. Accede a la aplicación en `http://localhost:5000`

## Configuración

La aplicación puede configurarse mediante variables de entorno. Puedes crear un archivo `.env` basado en `.env.example` para personalizar la configuración:

```
# Puerto en el que se ejecutará la aplicación
PORT=8000

# Modo de depuración
DEBUG=False

# Directorio de descargas (opcional)
# DOWNLOAD_FOLDER=/ruta/personalizada/descargas

# Directorio de logs (opcional)
# LOGS_FOLDER=/ruta/personalizada/logs
```

## Uso

1. Abre la aplicación en tu navegador
2. Ingresa la URL de una lista de reproducción de YouTube
3. Selecciona el formato de descarga (video completo o solo audio)
4. Haz clic en "Iniciar Descarga"
5. Espera a que se complete la descarga
6. Descarga los archivos individualmente haciendo clic en ellos

## Limitaciones

- La aplicación está diseñada para uso personal y no comercial
- El rendimiento puede variar según las restricciones de YouTube y la velocidad de tu conexión
- Algunas listas de reproducción con restricciones de edad o geográficas pueden no ser descargables

## Solución de problemas

### Los videos no se descargan

- Verifica que la URL de la lista de reproducción sea válida
- Asegúrate de que la lista no tenga restricciones de privacidad
- Comprueba los logs de la aplicación para más detalles

### Error al convertir a MP3

- Verifica que FFmpeg esté correctamente instalado
- Comprueba los permisos de escritura en el directorio de descargas

## Licencia

Este proyecto está licenciado bajo la Licencia MIT - ver el archivo LICENSE para más detalles.