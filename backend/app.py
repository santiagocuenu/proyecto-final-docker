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

from flask import Flask, Response, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

app = Flask(__name__)

# Nombre de la instancia ("server 1", "server 2" o "server 3").
# Si no se define la variable, se usa "sin-nombre" para que el error sea visible.
SERVER_NAME = os.getenv("SERVER_NAME", "sin-nombre")


# =============================================================================
# Métricas de Prometheus (librería cliente oficial: prometheus_client)
# -----------------------------------------------------------------------------
# Prometheus visita /metrics cada pocos segundos y guarda estos valores.
# Etiquetas (labels) de cada métrica:
#   servidor -> "server 1", "server 2"... (para separar las instancias en Grafana)
#   metodo   -> GET, POST...
#   ruta     -> la PLANTILLA de la ruta ("/slow", no "/slow?ms=500"), para no
#               crear una serie nueva por cada valor distinto de la URL
#   codigo   -> código HTTP de la respuesta (200, 404, 500...)
# =============================================================================

# Contador: solo sube. Con rate() en PromQL se obtiene la TASA de peticiones
# por segundo.
PETICIONES = Counter(
    "http_requests_total",
    "Total de peticiones HTTP atendidas por el backend",
    ["servidor", "metodo", "ruta", "codigo"],
)

# Histograma: reparte la duración de cada petición en "cubetas" (buckets).
# Con histogram_quantile() en PromQL se calcula la LATENCIA (p. ej. el p95).
# Las cubetas por defecto (5 ms ... 10 s) cubren tanto "/" (~1 ms) como
# "/slow?ms=500" (0,5 s) y las colas de varios segundos bajo saturación.
LATENCIA = Histogram(
    "http_request_duration_seconds",
    "Duración de las peticiones HTTP en segundos",
    ["servidor", "metodo", "ruta"],
)

# Rutas que NO se cuentan: /metrics la visita Prometheus y /health la visita el
# healthcheck de Docker. No son tráfico de usuarios y ensuciarían la gráfica.
RUTAS_EXCLUIDAS = {"/metrics", "/health"}


@app.before_request
def iniciar_cronometro():
    # Guarda la hora de inicio de la petición en "g" (almacenamiento propio de
    # cada petición en Flask). perf_counter es un reloj preciso para medir duraciones.
    g.inicio = time.perf_counter()


def registrar_metricas(resp):
    # Se llama al final de cada petición (ver marcar_backend, más abajo).
    # Plantilla de la ruta; si la URL no existe (404) no hay plantilla y se
    # usa "desconocida", para que URLs inventadas no creen series nuevas.
    ruta = request.url_rule.rule if request.url_rule else "desconocida"
    if ruta in RUTAS_EXCLUIDAS:
        return
    duracion = time.perf_counter() - g.get("inicio", time.perf_counter())
    PETICIONES.labels(SERVER_NAME, request.method, ruta, str(resp.status_code)).inc()
    LATENCIA.labels(SERVER_NAME, request.method, ruta).observe(duracion)


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


@app.route("/metrics")
def metrics():
    # Endpoint que lee Prometheus: devuelve TODAS las métricas en formato de
    # texto de Prometheus (las nuestras + las del proceso Python que la
    # librería agrega sola: CPU, memoria, etc.).
    # Se usa content_type (no mimetype) porque CONTENT_TYPE_LATEST ya incluye
    # el charset; con mimetype, Flask lo agregaría por segunda vez.
    return Response(generate_latest(), content_type=CONTENT_TYPE_LATEST)


@app.after_request
def marcar_backend(resp):
    # Se ejecuta al final de TODAS las peticiones, también las que terminan en
    # error (404, 500):
    # 1) agrega la cabecera X-Backend con el nombre de la instancia
    #    (con "curl -sI localhost:8080" se ve quién respondió);
    # 2) registra la petición en las métricas de Prometheus.
    resp.headers["X-Backend"] = SERVER_NAME
    registrar_metricas(resp)
    return resp
