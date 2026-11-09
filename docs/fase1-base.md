# Fase 1 – Base: estructura del repositorio y código del laboratorio

Fecha: 9 de noviembre de 2026

## Qué se hizo

Se migró el código del laboratorio de Nginx (Flask + Gunicorn + Nginx) a la estructura
del proyecto y se pasó de 2 a **3 backends**:

```
backend/
  app.py            ← igual al del lab, con comentarios
  requirements.txt  ← flask 3.1, gunicorn 23
  Dockerfile        ← imagen base con versión exacta
  .dockerignore     ← nuevo
nginx/
  nginx.conf        ← upstream con app1, app2 y app3 + "zone"
docker-compose.yml  ← 3 backends + Nginx en una red propia
```

| Cambio respecto al lab | Por qué |
|---|---|
| Se agregó `app3` (compose y `upstream`) | La guía pide al menos 3 instancias |
| Red `red_proyecto` declarada explícitamente | La guía pide una red Docker personalizada |
| `python:3.12.14-slim` y `nginx:1.27.5-alpine` | Versiones exactas: el entorno es reproducible |
| Se quitó el servicio `artillery` | La prueba de carga se hará desde el host (Fase 6) |
| `zone backend_pool 64k;` en el `upstream` | Reparto equitativo real (ver Problema 1) |
| Se monta la carpeta `nginx/` y no el archivo | Evita que Nginx deje de arrancar (ver Problema 2) |
| `.dockerignore` | Buena práctica vista en clase |

Todavía sin cambios (llegan en fases siguientes): `/metrics` y Gunicorn con 1 proceso
y 8 hilos (Fase 2), `stub_status` (Fase 3), monitoreo (Fase 4).

## Versiones elegidas

Se consultó Docker Hub antes de fijarlas:
- **nginx:** la rama 1.27 terminó en 1.27.5 (abril de 2025), así que `1.27-alpine` = `1.27.5-alpine`.
- **python:** la última 3.12 con más de dos semanas publicada era 3.12.14 (septiembre de 2026).

## Cómo se verificó

```text
$ docker compose config -q            → sin errores
$ docker compose up -d --build
 Container proyecto-final-app1-1 Healthy
 Container proyecto-final-app2-1 Healthy
 Container proyecto-final-app3-1 Healthy
 Container proyecto-final-nginx-1 Started

$ docker compose ps
proyecto-final-app1-1    Up (healthy)   5000/tcp
proyecto-final-app2-1    Up (healthy)   5000/tcp
proyecto-final-app3-1    Up (healthy)   5000/tcp
proyecto-final-nginx-1   Up             0.0.0.0:8080->80/tcp

$ curl -s localhost:8080
<h1>Hello from server 1</h1>

$ curl -sS -m 3 localhost:5000        → Failed to connect (los backends no están expuestos)

$ docker network inspect proyecto-final_red_proyecto
  → app1, app2, app3 y nginx conectados (driver bridge)

Dentro de los contenedores: Python 3.12.14, nginx/1.27.5, "nginx -t" correcto.

Reparto de 12 peticiones, 5 rondas seguidas (después de las dos correcciones):
Ronda 1..5:  4 server 1   4 server 2   4 server 3
```

## Problemas encontrados (útiles para el informe)

### Problema 1: el reparto no era equitativo (11/1/0)

La primera prueba de 12 peticiones dio **11 server 1, 1 server 2, 0 server 3**.

- **Causa:** Nginx crea un proceso *worker* por CPU. Docker Desktop le muestra 12 CPU,
  así que hubo 12 workers, cada uno con **su propio turno** del Round Robin. Como cada
  `curl` abre una conexión nueva que cae en un worker distinto, casi todos empezaban por
  app1. En el laboratorio (2 backends) salió 5/5 y el efecto pasó desapercibido.
- **Solución:** `zone backend_pool 64k;` dentro del `upstream`. Guarda el estado del pool en
  memoria compartida, así que los 12 workers usan un único contador. El algoritmo sigue
  siendo el Round Robin por defecto de Nginx.

### Problema 2: Nginx no volvía a arrancar después de editar `nginx.conf`

Tras editar el archivo y ejecutar `docker compose restart nginx`, el contenedor terminó con
el código 127:

```text
error mounting ".../docker-desktop-bind-mounts/Ubuntu/1143..." to rootfs at
"/etc/nginx/conf.d/default.conf": ... no such file or directory
```

- **Causa:** en Docker Desktop con WSL2, el montaje de **un archivo suelto** queda atado al
  archivo original. Muchos editores guardan escribiendo un archivo nuevo y renombrándolo,
  así que el montaje se queda apuntando a un archivo que ya no existe. Mientras tanto, el
  contenedor seguía leyendo la versión vieja (sin `zone`).
- **Solución:** montar la **carpeta** completa: `./nginx:/etc/nginx/conf.d:ro`. Nginx carga
  todos los `*.conf` de `conf.d`. Se comprobó reemplazando el archivo a propósito y
  reiniciando Nginx: arrancó bien y el reparto siguió en 4/4/4.
- **Lección:** al cambiar `nginx.conf`, validar siempre con `nginx -t` y comprobar el
  resultado. Si no se mide, un 4/4/4 casual puede ocultar que la configuración nueva nunca
  se aplicó.
