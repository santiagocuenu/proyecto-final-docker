# Guía clic por clic: dashboard de Grafana (lo arma el equipo)

Tiempo estimado: **10-15 minutos**. Versión de Grafana: **13.2.4**.
Sugerencia: grábenlo mientras lo hacen; sirve como demostración del monitoreo para el video.

Los nombres de los botones corresponden a Grafana 13. Si alguno se ve un poco distinto, busquen
el más parecido (por ejemplo, **Add → Visualization** en lugar de **+ Add visualization**).

---

## 0. Antes de empezar

1. Asegúrense de que todo esté arriba: `docker compose ps` (8 contenedores).
2. Para que haya datos en las gráficas, dejen corriendo en una terminal:
   ```bash
   artillery run loadtest/carga-100-por-segundo.yml
   ```
   O, en lugar de generar tráfico nuevo, elijan después el rango de las pruebas ya hechas:
   **9 de noviembre de 2026, 14:17 a 14:28**.

## 1. Entrar a Grafana

1. Abran **http://localhost:3000**.
2. Usuario `admin`, contraseña `admin`.
3. Grafana pide una contraseña nueva: pongan una que recuerden los tres (o clic en **Skip**).
4. (Opcional) Comprueben la conexión: menú izquierdo **Connections → Data sources → Prometheus**.
   Debe decir `http://prometheus:9090`. Ya viene configurada; no hay que tocar nada.

## 2. Crear el dashboard

1. Menú izquierdo → **Dashboards**.
2. Botón **New** → **New dashboard**.
3. Clic en **+ Add visualization**.
4. Si aparece la ventana **Select data source**, elijan **Prometheus**.
   (Si en cambio aparece **Configure visualization**, hagan clic ahí y elijan **Prometheus** en el
   desplegable **Data source** de la pestaña **Queries**).

Se abre el editor del panel: arriba la vista previa de la gráfica, abajo la consulta y a la
derecha las opciones.

## 3. Cómo se arma CADA panel (se repite 4 veces)

Para cada uno de los 4 paneles de la tabla de abajo:

1. **Consulta:** en el editor de consulta (abajo), a la derecha hay un selector
   **Builder | Code**: elijan **Code**. Peguen la consulta en el cuadro.
2. **Leyenda:** debajo de la consulta, abran **Options** → **Legend** → elijan **Custom** y
   escriban el texto de la columna "Leyenda".
3. Clic en **Refresh** (o fuera del cuadro) para ver la gráfica.
4. **Tipo de gráfica:** a la derecha, arriba, debe decir **Time series**. Si no, elíjanlo
   (en **All visualizations**).
5. **Título:** a la derecha, en **Panel options → Title**, escriban el título.
6. **Unidad:** a la derecha, busquen **Standard options → Unit** y elijan la unidad de la tabla
   (se puede escribir en el buscador del desplegable).
7. Clic en **Back** (o **Back to dashboard**) para volver al dashboard.
8. **Para el siguiente panel:** en modo edición, usen **Add** → **Visualization**, o el ícono
   **Add new element** de la barra lateral → **Panel**. Repitan desde el paso 1.

### Los 4 paneles obligatorios

**Panel 1. Tasa de peticiones**
| Campo | Valor |
|---|---|
| Título | `Peticiones por segundo por backend` |
| Consulta | `sum by (servidor) (rate(http_requests_total[1m]))` |
| Leyenda (Custom) | `{{servidor}}` |
| Unidad | **requests/sec (rps)** (en la categoría *Throughput*) |

**Panel 2. Latencia**
| Campo | Valor |
|---|---|
| Título | `Latencia p95 por backend` |
| Consulta | `histogram_quantile(0.95, sum by (le, servidor) (rate(http_request_duration_seconds_bucket[1m]))) * 1000` |
| Leyenda (Custom) | `{{servidor}}` |
| Unidad | **milliseconds (ms)** (en la categoría *Time*) |

**Panel 3. Memoria**
| Campo | Valor |
|---|---|
| Título | `Memoria por contenedor` |
| Consulta | `sum by (container_label_com_docker_compose_service) (container_memory_working_set_bytes{container_label_com_docker_compose_project="proyecto-final"})` |
| Leyenda (Custom) | `{{container_label_com_docker_compose_service}}` |
| Unidad | **bytes(IEC)** (en la categoría *Data*). Grafana mostrará MiB automáticamente |

**Panel 4. CPU**
| Campo | Valor |
|---|---|
| Título | `CPU por contenedor` |
| Consulta | `sum by (container_label_com_docker_compose_service) (rate(container_cpu_usage_seconds_total{container_label_com_docker_compose_project="proyecto-final"}[1m])) * 100` |
| Leyenda (Custom) | `{{container_label_com_docker_compose_service}}` |
| Unidad | **Percent (0-100)** (en la categoría *Misc*) |

### Paneles opcionales (si quieren cubrir también red y disco, que la guía menciona para cAdvisor)

| Título | Consulta | Leyenda | Unidad |
|---|---|---|---|
| `Red recibida por contenedor` | `sum by (container_label_com_docker_compose_service) (rate(container_network_receive_bytes_total{container_label_com_docker_compose_project="proyecto-final"}[1m]))` | `{{container_label_com_docker_compose_service}}` | **bytes/sec(IEC)** |
| `Escritura en disco por contenedor` | `sum by (container_label_com_docker_compose_service) (rate(container_fs_writes_bytes_total{container_label_com_docker_compose_project="proyecto-final"}[1m]))` | `{{container_label_com_docker_compose_service}}` | **bytes/sec(IEC)** |
| `Peticiones por segundo en Nginx` | `rate(nginx_http_requests_total[1m])` | `nginx` | **requests/sec (rps)** |
| `Conexiones activas en Nginx` | `nginx_connections_active` | `conexiones` | **none** |

## 4. Guardar el dashboard

1. Arriba a la derecha, clic en **Save** (o **Save dashboard**).
2. Título: `Proyecto final - Infraestructura` (o el que prefieran).
3. Carpeta: la que viene por defecto (**Dashboards**).
4. Clic en **Save**.
5. Clic en **Exit edit** para salir del modo edición.

## 5. Ajustes para que se vea bien en capturas y en el video

- **Rango de tiempo** (arriba a la derecha, el reloj): **Last 15 minutes** para una prueba en
  vivo, o un rango absoluto para las pruebas ya hechas (**From** `2026-11-09 14:17:00`,
  **To** `2026-11-09 14:28:00`).
- **Actualización automática** (flecha junto al botón de refrescar): **5s**.
- Pueden arrastrar los paneles para dejarlos en una cuadrícula de 2 × 2.
- Después de cambiar el rango o la actualización automática, vuelvan a guardar (**Save**) si quieren
  que quede así por defecto.

## 6. Comprobar que quedó bien

- [ ] Panel 1: una línea por servidor (server 1, server 2, server 3), parecidas entre sí
      (el balanceo reparte por igual).
- [ ] Panel 2: latencia de pocos milisegundos con `/`; sube a cientos o miles de ms durante las
      pruebas de saturación (puede tener huecos durante la saturación, ver `fase6-carga.md`).
- [ ] Panel 3: una línea por contenedor (app1, app2, app3, nginx, prometheus, grafana…).
- [ ] Panel 4: una línea por contenedor; sube durante las pruebas de carga.
- [ ] Al recargar la página (F5) el dashboard sigue ahí (está guardado en el volumen `grafana_data`).

## 7. Copia de seguridad (recomendado)

El dashboard vive en el volumen `grafana_data`. Para tener una copia en el repositorio:

1. Abran el dashboard → **Export** (o el ícono de compartir) → **Export as JSON** (o **Export as code**).
2. **Download file** y guárdenlo como `docs/dashboard-grafana.json`.
3. Hagan commit de ese archivo.

⚠️ Nunca usen `docker compose down -v`: borra el volumen y con él el dashboard.

## Qué significa cada consulta (para explicarlo en el video)

Ver la sección "Por qué estas consultas" de [`fase5-grafana.md`](fase5-grafana.md).
