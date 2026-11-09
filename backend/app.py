# =============================================================================
# Backend del proyecto final (Flask)
# -----------------------------------------------------------------------------
# Es la misma aplicación del laboratorio de Nginx. Se ejecuta 3 veces
# (app1, app2 y app3) a partir de UNA sola imagen; lo único que cambia entre
# instancias es la variable de entorno SERVER_NAME, que llega desde
# docker-compose.yml. Así cada respuesta dice qué instancia la atendió.
# =============================================================================
import os
import socket
import time

from flask import Flask, jsonify, request

app = Flask(__name__)

# Nombre de la instancia ("server 1", "server 2" o "server 3").
# Si no se define la variable, se usa "sin-nombre" para que el error sea visible.
SERVER_NAME = os.getenv("SERVER_NAME", "sin-nombre")


@app.route("/")
def index():
    # Página principal: muestra el nombre de la instancia y el id del contenedor.
    # Es lo que se ve en el navegador al entrar a http://localhost:8080
    return (
        f"<h1>Hello from {SERVER_NAME}</h1>\n"
        f"<p>Contenedor: {socket.gethostname()}</p>\n"
    )


@app.route("/health")
def health():
    # Chequeo de salud: Docker lo consulta (healthcheck) para saber si el
    # contenedor está listo. Nginx no arranca hasta que los 3 respondan aquí.
    return jsonify(status="ok", server=SERVER_NAME)


@app.route("/headers")
def headers():
    # Muestra las cabeceras que recibe el backend. Sirve para comprobar que
    # Nginx le pasa la IP real del cliente (X-Forwarded-For, X-Real-IP).
    return jsonify(
        server=SERVER_NAME,
        ip_que_ve_flask=request.remote_addr,
        cabeceras=dict(request.headers),
    )


@app.route("/slow")
def slow():
    # Simula trabajo pesado: /slow?ms=500 tarda 500 ms en responder.
    # Se usa en las pruebas de carga para saturar el sistema a propósito.
    # El máximo es 30 000 ms para que nadie bloquee un hilo indefinidamente.
    ms = min(int(request.args.get("ms", 1000)), 30000)
    time.sleep(ms / 1000)
    return jsonify(server=SERVER_NAME, esperó_ms=ms)


@app.after_request
def marcar_backend(resp):
    # Agrega a TODAS las respuestas la cabecera X-Backend con el nombre de la
    # instancia. Con "curl -sI localhost:8080" se ve quién respondió.
    resp.headers["X-Backend"] = SERVER_NAME
    return resp
