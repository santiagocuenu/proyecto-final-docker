# Fase 5 – Grafana

Fecha: 9 de noviembre de 2026

> **Pendiente:** guía clic por clic para que el equipo arme el dashboard a mano en la interfaz
> (se entregará al terminar el proyecto). Las consultas de abajo ya están probadas.

## Qué se hizo

- Servicio `grafana` con la imagen `grafana/grafana:13.2.4`. Se descartaron las versiones del
  27 de octubre por tener menos de dos semanas.
- Puerto `3000` → `http://localhost:3000` (usuario `admin`, contraseña `admin` la primera vez).
- **Persistencia:** volumen con nombre `grafana_data` en `/var/lib/grafana`. Ahí se guardan los
  dashboards creados en la interfaz. ⚠️ `docker compose down -v` los borraría.
- **Fuente de datos automática** (*provisioning*): `grafana/provisioning/datasources/prometheus.yml`,
  montado de solo lectura en `/etc/grafana/provisioning`. Grafana crea la conexión a Prometheus
  al arrancar.
  - URL `http://prometheus:9090`, **no** `localhost:9090`: dentro del contenedor de Grafana,
    `localhost` es el propio Grafana.
  - `access: proxy`: las consultas las hace el servidor de Grafana dentro de la red Docker.
  - `timeInterval: 5s`, igual al `scrape_interval` de Prometheus.

## Cómo se verificó

```text
$ curl -s localhost:3000/api/health
{"database": "ok", "version": "13.2.4", ...}

Fuente de datos:  Prometheus  http://prometheus:9090  (default)
Prueba de conexión (botón "Test" de la interfaz, vía API):
{"message":"Successfully queried the Prometheus API.","status":"OK"}
```

## Consultas PromQL para los paneles (probadas con datos reales)

Se generaron 600 peticiones a `/` y 40 a `/slow?ms=400`, y se ejecutó cada consulta:

| # | Panel | Consulta | Resultado de la prueba |
|---|---|---|---|
| 1 | **Tasa de peticiones** (req/s por backend) | `sum by (servidor) (rate(http_requests_total[1m]))` | server 1 = 3,8 · server 2 = 3,9 · server 3 = 3,9 |
| 2 | **Latencia p95** (ms por backend) | `histogram_quantile(0.95, sum by (le, servidor) (rate(http_request_duration_seconds_bucket[1m]))) * 1000` | 5 ms en server 1; ~280-330 ms en los que atendieron `/slow` |
| 3 | **Memoria** (MiB por contenedor) | `sum by (container_label_com_docker_compose_service) (container_memory_working_set_bytes{container_label_com_docker_compose_project="proyecto-final"}) / 1024 / 1024` | app1-3 ≈ 33-35 · grafana ≈ 293 · prometheus ≈ 60 |
| 4 | **CPU** (% de un núcleo por contenedor) | `sum by (container_label_com_docker_compose_service) (rate(container_cpu_usage_seconds_total{container_label_com_docker_compose_project="proyecto-final"}[1m])) * 100` | app1-3 ≈ 2 % · grafana ≈ 21 % |

Consultas extra (opcionales), también probadas:

| Panel | Consulta |
|---|---|
| Peticiones/s que recibe Nginx | `rate(nginx_http_requests_total[1m])` |
| Latencia promedio (ms) | `sum by (servidor) (rate(http_request_duration_seconds_sum[1m])) / sum by (servidor) (rate(http_request_duration_seconds_count[1m])) * 1000` |
| Red recibida (KB/s) | `sum by (container_label_com_docker_compose_service) (rate(container_network_receive_bytes_total{container_label_com_docker_compose_project="proyecto-final"}[1m])) / 1024` |
| Disco escrito (KB/s) | `sum by (container_label_com_docker_compose_service) (rate(container_fs_writes_bytes_total{container_label_com_docker_compose_project="proyecto-final"}[1m])) / 1024` |
| Conexiones activas en Nginx | `nginx_connections_active` |

### Por qué estas consultas (para explicarlas en el video)

- **`rate(...[1m])`:** un contador solo sube; `rate` calcula cuánto subió por segundo en el
  último minuto, es decir, la tasa.
- **`sum by (servidor)`:** suma las series de cada backend (rutas y códigos distintos) para
  dejar una línea por servidor.
- **`histogram_quantile(0.95, ...)`:** a partir de las cubetas del histograma estima el valor
  por debajo del cual está el 95 % de las peticiones (p95). Se agrupa `by (le, servidor)`
  porque `le` (el límite de cada cubeta) es necesario para el cálculo.
- **`container_memory_working_set_bytes`:** la memoria "en uso real" (lo mismo que muestra
  `docker stats`), sin la caché que el sistema puede liberar.
- **El filtro `container_label_com_docker_compose_project="proyecto-final"`** deja solo los
  contenedores de este proyecto; la leyenda usa el nombre del servicio (`app1`, `nginx`…).
- Nginx recibe un poco más que la suma de los backends (11,8 vs 11,6 req/s) porque cuenta
  también las visitas del exporter a `/stub_status`, que no llegan a los backends.
