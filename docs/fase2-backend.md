# Fase 2 – Backend: 3 instancias con /health y /metrics

Fecha: 9 de noviembre de 2026

## Qué se hizo

1. **`app.py`:** se agregaron las métricas de Prometheus con la librería cliente oficial
   `prometheus_client`, y la ruta `/metrics`.
2. **`requirements.txt`:** versiones exactas: `flask==3.1.3`, `gunicorn==23.0.0`,
   `prometheus-client==0.26.0`.
3. **`Dockerfile`:** Gunicorn pasa de `-w 2 --threads 4` a `--workers 1 --threads 8`.

## Métricas que expone cada backend

| Métrica | Tipo | Para qué sirve | Etiquetas |
|---|---|---|---|
| `http_requests_total` | Counter (contador, solo sube) | **Tasa de peticiones**: `rate(http_requests_total[1m])` | servidor, metodo, ruta, codigo |
| `http_request_duration_seconds` | Histogram (histograma) | **Latencia**: `histogram_quantile(0.95, ...)` da el p95 | servidor, metodo, ruta |

La librería también agrega sola métricas del proceso Python (`process_cpu_seconds_total`,
`process_resident_memory_bytes`, etc.).

Decisiones:
- **Etiqueta `servidor`** ("server 1", "server 2", "server 3"): permite separar las 3
  instancias en Grafana con nombres legibles.
- **La ruta se guarda como plantilla** (`/slow`, no `/slow?ms=500`). Si se guardara la URL
  completa, cada valor distinto de `ms` crearía una serie nueva en Prometheus. Las URLs que
  no existen (404) se agrupan como `ruta="desconocida"` por la misma razón.
- **No se cuentan `/metrics` ni `/health`:** las visitan Prometheus (cada pocos segundos) y el
  healthcheck de Docker (cada 5 s). No son tráfico de usuarios y ensuciarían la tasa de
  peticiones.
- **Cubetas del histograma:** las de la librería por defecto (5 ms … 10 s). Cubren `/`
  (~0,05 ms), `/slow?ms=500` (0,5 s) y las colas de varios segundos bajo saturación.

## ¿Por qué Gunicorn con 1 proceso y 8 hilos?

`prometheus_client` guarda los contadores **en la memoria de cada proceso**. Con 2 procesos
(como en el lab), cada visita de Prometheus a `/metrics` caería al azar en uno o en otro, y el
contador subiría y bajaría sin sentido. Con 1 proceso y 8 hilos hay una sola memoria y las
métricas son exactas. La capacidad no cambia: siguen siendo **8 peticiones simultáneas por
backend** (antes 2 × 4, ahora 1 × 8), es decir, 24 en total con 3 backends.

## Cómo se verificó

```text
$ docker compose up -d --build
proyecto-final-app1-1    Up (healthy)
proyecto-final-app2-1    Up (healthy)
proyecto-final-app3-1    Up (healthy)

Comando de arranque dentro de app1:
gunicorn --workers 1 --threads 8 -b 0.0.0.0:5000 app:app
Log: "Using worker: gthread" / "Booting worker with pid: 7"   → 1 maestro + 1 worker con hilos
```

Se enviaron por Nginx 30 peticiones a `/`, 12 a `/slow` (6 de 300 ms y 6 de 700 ms), 3 a una
ruta inexistente y 3 a `/health`. Luego se leyó `/metrics` de cada backend desde dentro del
contenedor (los backends no publican puertos):

```bash
docker compose exec app1 python -c 'import urllib.request; print(urllib.request.urlopen("http://localhost:5000/metrics").read().decode())'
```

```text
http_requests_total{codigo="200",metodo="GET",ruta="/",servidor="server 1"} 18.0
http_requests_total{codigo="200",metodo="GET",ruta="/slow",servidor="server 1"} 4.0
http_requests_total{codigo="404",metodo="GET",ruta="desconocida",servidor="server 1"} 1.0
http_request_duration_seconds_sum{metodo="GET",ruta="/slow",servidor="server 1"} 2.0015
(app2 y app3: mismos conteos con "server 2" y "server 3")
```

- 18 peticiones a `/` por backend = 54 en total (30 de esta prueba + 24 de la Fase 1) ÷ 3. ✔
- 4 peticiones a `/slow` por backend, con suma de 2,0 s = 2 × 0,3 s + 2 × 0,7 s. ✔
- `/metrics` y `/health` no aparecen en las métricas. ✔
- Histograma (app1, una petición de 300 ms y otra de 700 ms):
  `le="0.25"` → 0, `le="0.5"` → 1, `le="0.75"` → 2. Cada petición cae en su cubeta. ✔
- Cabecera de `/metrics`: `text/plain; version=1.0.0; charset=utf-8`. ✔
- El reparto por Nginx siguió en 4/4/4.

## Problemas encontrados

### Cabecera `charset` duplicada en `/metrics`
La primera versión respondía `charset=utf-8; charset=utf-8`. La constante de la librería
(`CONTENT_TYPE_LATEST`) ya incluye el charset, y al pasarla como `mimetype=` Flask agregaba
otro. Prometheus 3 es estricto con esta cabecera. **Solución:** usar `content_type=`.

### Riesgo: Nginx guarda las IP de los backends al arrancar
Nginx traduce `app1`, `app2` y `app3` a direcciones IP **una sola vez, al arrancar**. Si se
reconstruyen los backends y Docker les asigna otras IP, Nginx seguiría enviando a las
viejas. En esta fase Docker reutilizó las mismas IP y todo funcionó, pero no está
garantizado. **Regla práctica:** después de reconstruir los backends, ejecutar
`docker compose restart nginx`.

## Nota

`/metrics` también responde a través de Nginx (`localhost:8080/metrics`), pero ahí contesta un
backend distinto en cada visita. Prometheus no la leerá por ahí: leerá directamente
`app1:5000`, `app2:5000` y `app3:5000` dentro de la red (Fase 4).
