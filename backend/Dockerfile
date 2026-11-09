# =============================================================================
# Dockerfile del backend: la "receta" para construir la imagen.
# Con esta única imagen se crean los 3 contenedores app1, app2 y app3.
# =============================================================================

# Imagen base: Python 3.12 en su variante "slim" (Debian reducido, pesa poco).
# Se fija la versión exacta (3.12.14) para que la imagen sea reproducible:
# sin esto, "3.12-slim" podría cambiar cada vez que salga un parche.
FROM python:3.12.14-slim

# Directorio de trabajo dentro de la imagen; los comandos siguientes ocurren aquí.
WORKDIR /app

# Primero se copian SOLO las dependencias y se instalan.
# Así, si luego cambia app.py, Docker reutiliza la capa en caché de pip y la
# construcción es mucho más rápida (el orden de las capas importa).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Después se copia el código de la aplicación.
COPY app.py .

# Documenta el puerto en el que escucha la aplicación dentro del contenedor.
# No lo publica hacia el host: los backends solo son accesibles a través de Nginx.
EXPOSE 5000

# Comando de arranque: Gunicorn, un servidor apto para producción
# (el servidor de desarrollo de Flask se vuelve un cuello de botella).
#   -w 2         -> 2 procesos
#   --threads 4  -> 4 hilos por proceso (8 peticiones simultáneas por backend)
#   -b 0.0.0.0:5000 -> escucha en todas las interfaces del contenedor, puerto 5000
#   app:app      -> el objeto "app" del archivo app.py
CMD ["gunicorn", "-w", "2", "--threads", "4", "-b", "0.0.0.0:5000", "app:app"]
