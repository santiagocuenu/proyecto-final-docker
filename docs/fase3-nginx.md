# Fase 3 – Nginx: balanceo entre 3 backends y stub_status

Fecha: 9 de noviembre de 2026

## Qué se hizo

Se agregó a `nginx/nginx.conf` la página de estado interno de Nginx:

```nginx
location = /stub_status {
    stub_status;
    access_log off;
}
```

- **`location =`** es una coincidencia exacta: solo `/stub_status` la atiende Nginx; todo lo
  demás sigue yendo a los backends por `location /`.
- **`access_log off`:** el exporter la consultará cada pocos segundos (Fase 4) y esas visitas
  no deben mezclarse con el tráfico real en los logs.
- Queda accesible desde el host en `http://localhost:8080/stub_status` (el profesor lo aprobó).
- Antes se comprobó que la imagen trae el módulo: `nginx -V` → `--with-http_stub_status_module`.

El balanceo (Round Robin por defecto, con `zone` desde la Fase 1) no cambió.

La recarga se hizo **sin cortar el servicio**:
```bash
docker compose exec nginx nginx -t          # validar SIEMPRE antes de recargar
docker compose exec nginx nginx -s reload   # recargar en caliente
```

## Qué significa cada valor de stub_status

```text
Active connections: 1
server accepts handled requests
 61 61 61
Reading: 0 Writing: 1 Waiting: 0
```

| Valor | Significado |
|---|---|
| Active connections | Conexiones abiertas en este momento |
| accepts | Conexiones aceptadas desde que arrancó Nginx |
| handled | Conexiones atendidas (si es menor que accepts, Nginx rechazó algunas por límite) |
| requests | Peticiones HTTP totales |
| Reading / Writing / Waiting | Conexiones leyendo la petición / escribiendo la respuesta / en espera (keep-alive) |

`stub_status` **no mide latencia**, solo conteos. Por eso la latencia del dashboard saldrá del
histograma de los backends (Fase 2).

## Cómo se verificó (estas pruebas sirven para el video)

**1. stub_status desde el host y sin pasar por un backend**
```text
$ curl -s localhost:8080/stub_status          → página de estado (arriba)
$ curl -sI localhost:8080/stub_status         → 200, Content-Type: text/plain, SIN X-Backend
```
El contador `requests` subió de 20 a 61 entre dos lecturas, exactamente las 41 peticiones
hechas entre ambas.

**2. Quién atendió cada petición (cabeceras)**
```text
$ curl -sI localhost:8080      (3 veces)
X-Backend: server 1   X-Upstream: 172.18.0.2:5000
X-Backend: server 2   X-Upstream: 172.18.0.3:5000
X-Backend: server 3   X-Upstream: 172.18.0.4:5000
```
`X-Backend` lo pone Flask y `X-Upstream` lo pone Nginx.

**3. Reparto equitativo con 12 peticiones (criterio de aceptación)**
```bash
for i in $(seq 1 12); do curl -s localhost:8080 | grep -o "server [0-9]"; done | sort | uniq -c
```
```text
Ronda 1:  4 server 1   4 server 2   4 server 3
Ronda 2:  4 server 1   4 server 2   4 server 3
Ronda 3:  4 server 1   4 server 2   4 server 3
```

**4. Los backends no son accesibles directamente**
```text
$ curl -sS -m 3 localhost:5000
curl: (7) Failed to connect to localhost port 5000 ... Could not connect to server
```

**5. Tolerancia a fallos (se apaga app1)**
```bash
docker compose stop app1
for i in $(seq 1 10); do curl -s -o /dev/null -w "%{http_code} %{time_total}s\n" localhost:8080; done
```
```text
200 2.003161s     ← Nginx intentó app1, esperó 2 s (proxy_connect_timeout) y reenvió
200 0.001552s
...               ← las otras 8 también 200, en ~1,5 ms
Reparto de 12 con app1 apagado:  6 server 2   6 server 3
```
Log de Nginx de esa primera petición (se ven los dos backends intentados):
```text
upstream timed out (110: Operation timed out) while connecting to upstream ... "http://172.18.0.2:5000/"
172.18.0.1 -> upstream=172.18.0.2:5000, 172.18.0.3:5000 "GET / HTTP/1.1" status=200 tiempo=2.002 s
```
Al encender app1 (`docker compose start app1`) volvió a estar *healthy* en ~4 s y a recibir
tráfico: `3 server 1   5 server 2   4 server 3`. Al principio el reparto no es exacto porque
Nginx mantiene a app1 marcado como caído unos segundos (`fail_timeout`, 10 s por defecto).

**Diferencia con el laboratorio:** en el lab **dos** peticiones tardaron ~2 s; aquí solo **una**.
Con `zone`, los 12 procesos worker de Nginx comparten también el estado "app1 está caído",
así que basta con que uno lo descubra.

## Problemas encontrados

Ninguno nuevo. Como el montaje es de la carpeta `nginx/` (Fase 1), el contenedor vio el archivo
editado y la recarga en caliente funcionó sin recrear el contenedor.
