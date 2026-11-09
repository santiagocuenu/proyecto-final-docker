# Fase 4 – Monitoreo: Prometheus, nginx-exporter y cAdvisor

Fecha: 9 de noviembre de 2026

## Qué se hizo

Se agregaron 3 servicios al `docker-compose.yml`, todos en la red `red_proyecto`:

| Servicio | Imagen (versión fija) | Puerto en el host | Qué hace |
|---|---|---|---|
| `nginx-exporter` | `nginx/nginx-prometheus-exporter:1.5.3` | 9113 | Lee `http://nginx:80/stub_status` y lo traduce a métricas de Prometheus |
| `cadvisor` | `ghcr.io/google/cadvisor:v0.60.6` | 8081 (interno 8080) | CPU, memoria, red y disco de cada contenedor (lee los cgroups) |
| `prometheus` | `prom/prometheus:v3.15.1` | 9090 | Visita los `/metrics` cada 5 s y guarda las series de tiempo |

Y el archivo `prometheus/prometheus.yml` con 3 trabajos (*jobs*):

| Job | Targets | Métricas principales |
|---|---|---|
| `backends` | `app1:5000`, `app2:5000`, `app3:5000` | `http_requests_total`, `http_request_duration_seconds` |
| `nginx` | `nginx-exporter:9113` | `nginx_connections_active`, `nginx_http_requests_total`, `nginx_up` |
| `cadvisor` | `cadvisor:8080` | `container_cpu_usage_seconds_total`, `container_memory_usage_bytes`, `container_network_*`, `container_fs_*` |

### Decisiones

- **`scrape_interval: 5s`** (por defecto es 15 s): las pruebas de carga duran 1-2 minutos y con
  15 s las gráficas tendrían muy pocos puntos.
- **Los backends se leen directamente** (`app1:5000`…) y no a través de Nginx, porque por Nginx
  cada visita caería en un backend distinto.
- **Persistencia:** volumen con nombre `prometheus_data` montado en `/prometheus`.
- **Configuración:** se monta la **carpeta** `./prometheus` (solo lectura) en `/etc/prometheus`,
  por el mismo problema de Docker Desktop/WSL2 con archivos sueltos visto en la Fase 1.
- **Versiones:** se consultaron Docker Hub y GitHub. Se descartó Prometheus v3.16.0 por ser de
  hace 4 días (5 de noviembre) y se fijó la v3.15.1 (21 de octubre).
- **cAdvisor cambió de registro:** la presentación de clase usa `gcr.io/cadvisor/cadvisor`, pero
  ese registro dejó de recibir versiones (se comprobó: tiene la v0.52.1 pero no la v0.60.6). Las
  versiones nuevas están en `ghcr.io/google/cadvisor`.

## cAdvisor en Docker Desktop + WSL2 (el problema principal de esta fase)

### Síntoma
Con los montajes estándar de la documentación de cAdvisor (`/:/rootfs`, `/var/run`, `/sys`,
`/var/lib/docker`, `/dev/disk`), el target `cadvisor` aparecía en **UP**, pero solo reportaba
**una serie: la raíz `/`**. Ningún contenedor del proyecto aparecía.

### Causa
En Docker Desktop, los contenedores **no corren en Ubuntu (WSL)** sino en una máquina virtual
propia de Docker. Cuando el compose se ejecuta desde WSL, los montajes como `/:/rootfs` se
resuelven desde **Ubuntu**, no desde esa VM. El log de cAdvisor lo mostraba:

```text
Registration of the docker container factory failed: unable to create containerd client:
  dial unix /run/containerd/containerd.sock: connect: no such file or directory
failed to collect filesystem stats - could not stat "/rootfs/var/lib/docker/containers/<id>"
```

1. **Sin socket de containerd**, cAdvisor no sabe qué cgroup corresponde a qué contenedor
   (sin nombres) y, con `--docker_only`, los descarta todos.
2. **`/rootfs` era la raíz de Ubuntu**: allí no están los procesos de los contenedores
   (`/proc/<pid>/net/dev`, de donde sale el tráfico de red) ni sus datos de disco.

Lo que sí funcionaba: `/sys/fs/cgroup/docker` (cgroups de la VM) y `/var/run/docker.sock`
(Docker Desktop lo redirige automáticamente).

### Investigación
Con un contenedor desechable con `--pid=host` (comparte la tabla de procesos de la VM) se
comprobó que **`/proc/1/root`** (la raíz de archivos del proceso 1 de la VM, `initd`) contiene
todo lo que cAdvisor necesita:

```text
SOCKET en /proc/1/root/run/containerd/containerd.sock
OK red:   /proc/1/root/proc/<pid de app1>/net/dev
OK        /proc/1/root/var/lib/docker/containers/<id de app1>
```

### Solución aplicada (en `docker-compose.yml`)
1. `pid: host`: cAdvisor ve los procesos de la VM, así que `/proc/1/root` es la raíz real.
2. Se reemplazó el arranque de la imagen por un pequeño comando que primero crea dos enlaces
   simbólicos y después ejecuta el arranque original (`/usr/bin/entrypoint.sh`):
   - `/rootfs -> /proc/1/root`
   - `/var/lib/docker -> /proc/1/root/var/lib/docker`
3. `--containerd=/proc/1/root/run/containerd/containerd.sock`.
4. Se quitaron los montajes `/:/rootfs` y `/var/lib/docker` (apuntaban a Ubuntu). Se mantienen
   `/var/run` (socket de Docker), `/sys` (cgroups) y `/dev/disk`.

En Linux nativo (sin Docker Desktop) bastarían los montajes estándar de la documentación.

### Resultado
Log de cAdvisor: `Registration of the docker container factory successfully` y sin errores
(solo un aviso inofensivo por no encontrar `/etc/machine-id`).

Métricas por contenedor, identificadas por la etiqueta
`container_label_com_docker_compose_service` (nombre del servicio en el compose):

| Recurso | Métrica | ¿Funciona? |
|---|---|---|
| CPU | `container_cpu_usage_seconds_total` | ✅ los 7 contenedores |
| Memoria | `container_memory_usage_bytes` | ✅ los 7 contenedores |
| Red | `container_network_receive_bytes_total` / `..._transmit_...` | ✅ los 7 contenedores |
| Disco: E/S | `container_fs_reads_bytes_total` / `container_fs_writes_bytes_total` | ✅ en los contenedores que leen o escriben |
| Disco: espacio ocupado | `container_fs_usage_bytes` | ❌ no se reporta por contenedor |

Muestra tomada después de 300 peticiones a `/`:
```text
CPU (% de 1 núcleo):  app1=1.4  app2=1.6  app3=1.6  cadvisor=1.2  nginx=0.25  prometheus=0.6
Memoria (MiB):        app1=32   app2=35   app3=35   cadvisor=24   nginx=10.5  prometheus=51
Red recibida (KB/s):  app1=1.3  app2=1.4  app3=1.3  nginx=6.9    prometheus=8.7
Disco escrito (KB):   app2=304  app3=304  nginx=4   prometheus=476
```

**Limitación conocida (para el informe):** el espacio en disco ocupado por cada contenedor no
aparece. Docker Desktop usa el almacén de imágenes de containerd (`storage=overlayfs`, Fase 0)
y cAdvisor no calcula ese dato con ese almacén; tras el arreglo ya no hay ningún error en el
log, simplemente no lo reporta. El requisito de "disco" se cubre con la **E/S de disco por
contenedor** (bytes leídos y escritos), que sí funciona.

## Cómo se verificó

**1. Los 5 targets en UP** (`http://localhost:9090/targets` o la API):
```text
backends  app1:5000            up
backends  app2:5000            up
backends  app3:5000            up
cadvisor  cadvisor:8080        up
nginx     nginx-exporter:9113  up
```

**2. El exporter lee Nginx** (`http://localhost:9113/metrics`):
```text
nginx_up 1
nginx_connections_active 1
nginx_http_requests_total 99
```

**3. Persistencia de datos de Prometheus**: se eliminó **solo el contenedor** de Prometheus
(el volumen no se tocó), se recreó y se compararon los datos:
```text
ANTES:   muestras de "up" en 30 min: app1=69 app2=69 app3=68 | muestra más antigua de app1: 13:59:01
$ docker compose rm -sf prometheus      → Container proyecto-final-prometheus-1 Removed
  Volumen sigue existiendo: proyecto-final_prometheus_data
$ docker compose up -d prometheus
DESPUÉS: muestras de "up" en 30 min: app1=69 app2=69 app3=68 | muestra más antigua de app1: 13:59:01
```
Los datos sobrevivieron a la eliminación del contenedor. ⚠️ Solo se borrarían con
`docker compose down -v` (la `-v` elimina los volúmenes): **no usarlo**.

**4. Interfaces web desde el host:** Prometheus `http://localhost:9090`, cAdvisor
`http://localhost:8081/containers/`, exporter `http://localhost:9113/metrics`.

## Consultas útiles para probar en Prometheus (pestaña Query)

```promql
up                                                     # 1 = target arriba, 0 = caído
sum by (servidor) (rate(http_requests_total[1m]))      # peticiones/s por backend
container_memory_usage_bytes{container_label_com_docker_compose_project="proyecto-final"}
```
