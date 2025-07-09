# Despliegue con un solo clic en DigitalOcean

Puedes desplegar esta aplicación en DigitalOcean App Platform con un solo clic utilizando el siguiente botón:

[![Deploy to DigitalOcean](https://www.deploytodo.com/do-btn-blue.svg)](https://cloud.digitalocean.com/apps/new?repo=https://github.com/brahianf1/youtube-playlist-downloader/tree/main)

## Pasos para el despliegue

1. Haz clic en el botón "Deploy to DigitalOcean" arriba
2. Inicia sesión en tu cuenta de DigitalOcean (o crea una nueva)
3. Configura las opciones de despliegue (puedes dejar los valores predeterminados)
4. Haz clic en "Deploy to App Platform"
5. Espera a que se complete el despliegue
6. ¡Listo! Tu aplicación estará disponible en la URL proporcionada por DigitalOcean

## Configuración adicional

Si deseas personalizar la configuración de la aplicación, puedes hacerlo a través del panel de control de DigitalOcean App Platform después del despliegue:

1. Ve a la sección "Apps" en tu panel de DigitalOcean
2. Selecciona tu aplicación
3. Haz clic en "Settings" y luego en "Edit" en la sección "Environment Variables"
4. Añade o modifica las variables de entorno según sea necesario
5. Haz clic en "Save" y luego en "Deploy Changes"

## Nota importante

Para que el botón de despliegue funcione correctamente, este repositorio debe contener un archivo `.do/deploy.template.yaml` con la configuración necesaria para App Platform. Este archivo ya está incluido en el repositorio.