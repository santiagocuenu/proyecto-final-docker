# Guía para armar el informe (máximo 10 páginas)

Este archivo relaciona cada sección **obligatoria** del informe (según
`Proyecto_final.pdf`) con los apuntes de `docs/` que tienen la información y las pruebas.
El informe lo redacta el equipo, con sus palabras y sus capturas.

## Datos obligatorios de la portada
- Nombres de **los 3 integrantes** (la guía lo exige).
- Enlace al repositorio en GitHub (debe ser público).
- Enlace al video de YouTube (máximo 10 minutos; **cada integrante debe aparecer al menos
  1 minuto**).
- Recordatorio: **cada integrante entrega individualmente** el PDF y los dos enlaces.

## Secciones que pide la guía y dónde está el material

| # | Sección del informe | Material | Extensión sugerida |
|---|---|---|---|
| 1 | Pasos para desarrollar el proyecto (decisiones y resultados) | `fase0-entorno.md` … `fase6-carga.md`: cada uno tiene *qué se hizo*, *por qué*, *cómo se verificó* y *problemas* | repartido en las demás secciones |
| 2 | **Descripción de la arquitectura** | Diagrama y tabla de servicios del `README.md`; abajo, "Resumen de la arquitectura" | 1 página |
| 3 | **Explicación del `docker-compose.yml`** | Comentarios del propio archivo; `fase1-base.md` (red, healthchecks, montaje de carpeta), `fase4-monitoreo.md` (volúmenes, cAdvisor), `fase5-grafana.md` | 1,5 páginas |
| 4 | **Explicación del Dockerfile del backend** | Comentarios de `backend/Dockerfile`; `fase2-backend.md` (por qué 1 proceso y 8 hilos) | 0,5 página |
| 5 | **Configuración de Nginx como proxy inverso** | Comentarios de `nginx/nginx.conf`; `fase1-base.md` (`zone`, problema 11/1/0), `fase3-nginx.md` (stub_status, tolerancia a fallos) | 1,5 páginas |
| 6 | **Métricas monitoreadas y dashboards de Grafana** | `fase2-backend.md` (métricas propias), `fase4-monitoreo.md` (cAdvisor y exporter), `fase5-grafana.md` (consultas PromQL explicadas) + capturas del dashboard | 2 páginas |
| 7 | **Resultados de las pruebas de carga** | `fase6-carga.md` (tablas, cálculo en papel, análisis) y `resultados/` | 2 páginas |
| 8 | README.md | Ya está en la raíz del repositorio (la guía solo pide que exista y mencionarlo) | 1 párrafo |

Total aproximado: 9 páginas + portada. Si sobra espacio, conviene recortar capturas antes
que el análisis.

## Resumen de la arquitectura (para la sección 2)

- **9 contenedores** definidos en un solo `docker-compose.yml`, todos en la red bridge
  personalizada **`red_proyecto`**, donde se encuentran por nombre gracias al DNS interno de
  Docker.
- **Tráfico:** el navegador (o Artillery) entra solo por **Nginx** (puerto 8080 del host).
  Nginx reparte las peticiones por turnos (Round Robin) entre **3 backends** Flask (`app1`,
  `app2`, `app3`), construidos con **la misma imagen** y diferenciados por la variable
  `SERVER_NAME`. Los backends no publican puertos.
- **Monitoreo:**
  - Cada backend expone `/metrics` (contador de peticiones e histograma de latencia, con
    `prometheus_client`).
  - **nginx-prometheus-exporter** traduce `/stub_status` de Nginx.
  - **cAdvisor** mide CPU, memoria, red y disco de cada contenedor leyendo los cgroups del kernel.
  - **Prometheus** visita los 5 targets cada 5 s y guarda las series en el volumen
    `prometheus_data`.
  - **Grafana** consulta a Prometheus con PromQL y guarda sus dashboards en el volumen
    `grafana_data`.
- **Persistencia:** volúmenes con nombre para los datos; bind mounts de **solo lectura** para
  la configuración (`nginx/`, `prometheus/`, `grafana/provisioning/`).

## Decisiones técnicas que conviene defender en el informe y el video

| Decisión | Por qué | Dónde está |
|---|---|---|
| Python/Flask + Gunicorn | Base del laboratorio; Gunicorn aguanta carga (el servidor de desarrollo de Flask no) | fase 1 |
| Gunicorn con 1 proceso y 8 hilos | `prometheus_client` guarda las métricas por proceso; con 2 procesos serían incoherentes | fase 2 |
| Ruta etiquetada como plantilla (`/slow`) | Evita crear una serie por cada valor de `?ms=` | fase 2 |
| `zone` en el `upstream` | Con 12 workers el reparto salía 11/1/0; con memoria compartida, 4/4/4 | fase 1 |
| Montar carpetas y no archivos sueltos | En Docker Desktop/WSL2 el montaje de un archivo se rompe al editarlo | fase 1 |
| `location = /stub_status` con `access_log off` | Ruta exacta (no llega a los backends) y sin ensuciar los logs | fase 3 |
| `scrape_interval: 5s` | Pruebas de 1 minuto: con 15 s habría muy pocos puntos | fase 4 |
| Ajustes de cAdvisor (`pid: host`, `/proc/1/root`) | Docker Desktop corre los contenedores en su propia máquina virtual | fase 4 |
| Fuente de datos de Grafana por *provisioning* con `http://prometheus:9090` | Dentro de Grafana, `localhost` es Grafana | fase 5 |
| Versiones fijas en todas las imágenes | Reproducibilidad (nada de `:latest`) | todas |

## Problemas encontrados y cómo se resolvieron (muy valorado en el informe)

1. Docker no existía en WSL → activar la integración de Docker Desktop (fase 0).
2. `sudo` no funciona con el prefijo `!` de Claude Code → instalar en otra pestaña (fase 0).
3. Reparto desigual 11/1/0 por los 12 workers de Nginx → `zone` (fase 1).
4. Nginx no arrancaba tras editar `nginx.conf` (montaje de archivo suelto) → montar la carpeta (fase 1).
5. `charset` duplicado en `/metrics` → `content_type=` (fase 2).
6. cAdvisor sin contenedores en Docker Desktop → `pid: host`, enlaces a `/proc/1/root` y socket
   de containerd (fase 4).
7. cAdvisor sin espacio en disco por contenedor → limitación del almacén de containerd;
   se usa la E/S de disco (fase 4).
8. Durante la saturación, backends `unhealthy` y huecos en las métricas de los backends →
   explicado: `/health` y `/metrics` comparten hilos con `/slow` (fase 6).

## Capturas que debe tomar el equipo (con fecha y hora visibles)

- [ ] Navegador en `http://localhost:8080` mostrando server 1, server 2 y server 3.
- [ ] Terminal: `docker compose up -d --build` y `docker compose ps`.
- [ ] Terminal: conteo de 12 peticiones (4/4/4) y `curl -sI` con `X-Backend`/`X-Upstream`.
- [ ] Terminal: tolerancia a fallos (`docker compose stop app1` + las 10 peticiones con 200).
- [ ] Navegador: `http://localhost:8080/stub_status`.
- [ ] Navegador: Prometheus → Status → **Targets** con los 5 en UP.
- [ ] Navegador: cAdvisor (`http://localhost:8081/containers/`).
- [ ] Grafana: el dashboard con los 4 paneles (peticiones, latencia, memoria, CPU), en el rango
      de las pruebas de carga (9 de noviembre, 14:17 a 14:28) o en una prueba nueva.
- [ ] Terminal: resumen final de Artillery de una prueba normal y una de saturación.

## Guion sugerido para el video (máximo 10 minutos)

| Minuto | Contenido | Quién |
|---|---|---|
| 0:00-1:30 | Resumen ejecutivo: objetivo, arquitectura (diagrama del README) | Integrante 1 |
| 1:30-3:30 | Demostración: `docker compose up -d --build`, `docker compose ps`, navegador en :8080 | Integrante 1 |
| 3:30-5:30 | Balanceo: conteo 4/4/4, cabeceras, apagar `app1` y mostrar que sigue funcionando | Integrante 2 |
| 5:30-8:00 | Monitoreo: targets en Prometheus, dashboard de Grafana; lanzar `artillery run loadtest/carga-120-por-segundo.yml` y ver subir las gráficas | Integrante 3 |
| 8:00-9:30 | Resultados de carga y conclusiones (saturación con `/slow`, cálculo de 48/s) | Integrante 2 o 3 |

Cada integrante debe aparecer al menos 1 minuto (puede ser en cámara al mismo tiempo).
