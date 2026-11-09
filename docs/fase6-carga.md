# Fase 6 – Pruebas de carga con Artillery (desde el host)

Fecha: 9 de noviembre de 2026

## Qué se hizo

Se crearon 5 escenarios en `loadtest/` y se ejecutaron **desde WSL (la máquina física)** contra
`http://localhost:8080`, el mismo puerto que usa el navegador. En el laboratorio, Artillery
corría dentro de un contenedor y apuntaba a `http://nginx:80`; aquí corre fuera de Docker, como
pide la guía.

| Archivo | Ruta | Carga | Duración | Total enviado |
|---|---|---|---|---|
| `carga-70-por-minuto.yml` | `/` | 70 por minuto (`arrivalCount: 70`) | 60 s | 70 |
| `carga-100-por-segundo.yml` | `/` | 100/s (`arrivalRate: 100`) | 60 s | 6.000 |
| `carga-120-por-segundo.yml` | `/` | 120/s | 60 s | 7.200 |
| `saturacion-100-por-segundo.yml` | `/slow?ms=500` | 100/s | 60 s | 6.000 |
| `saturacion-120-por-segundo.yml` | `/slow?ms=500` | 120/s | 60 s | 7.200 |

Cómo se ejecutó cada una (el resumen queda en `.txt` y el detalle en `.json`):
```bash
export ARTILLERY_DISABLE_TELEMETRY=true      # que Artillery no envíe estadísticas de uso a internet
artillery run --output docs/resultados/carga-100-por-segundo.json \
  loadtest/carga-100-por-segundo.yml > docs/resultados/carga-100-por-segundo.txt
```

Horarios de cada prueba (hora de Colombia, UTC-5), en `docs/resultados/horarios.txt`. Sirven
para buscar cada prueba en Grafana (selector de tiempo arriba a la derecha):

| Prueba | Inicio | Fin |
|---|---|---|
| carga-70-por-minuto | 14:17:58 | 14:19:03 |
| carga-100-por-segundo | 14:19:08 | 14:20:14 |
| carga-120-por-segundo | 14:20:18 | 14:21:23 |
| saturacion-100-por-segundo | 14:21:31 | 14:22:46 |
| saturacion-120-por-segundo | 14:24:05 | 14:25:20 |

## Cálculo en papel (antes de ejecutar)

- Cada backend: 1 proceso × 8 hilos = **8 peticiones simultáneas**.
- 3 backends → **24 peticiones simultáneas**.
- `/` tarda ~2 ms → la capacidad teórica es de miles de peticiones/s: 100 y 120/s deberían ir sobradas.
- `/slow?ms=500` tarda 0,5 s → capacidad máxima = 24 ÷ 0,5 = **48 peticiones/s**.
  Pedir 100/s (2,1 veces) o 120/s (2,5 veces) debería saturar el sistema.

## Resultados (resumen de Artillery)

| Prueba | Respuestas 200 | Errores (timeout 10 s) | Latencia media | p95 | p99 | Máx. |
|---|---|---|---|---|---|---|
| 70 por minuto (`/`) | **70 / 70** | 0 | 1,8 ms | 2 ms | 2 ms | 2 ms |
| 100/s (`/`) | **6.000 / 6.000** | 0 | 2 ms | 3 ms | 3 ms | 27 ms |
| 120/s (`/`) | **7.200 / 7.200** | 0 | 2,1 ms | 3 ms | 3 ms | 37 ms |
| 100/s (`/slow` 500 ms) | **889 / 6.000** (15 %) | 5.111 `ERR_SOCKET_TIMEOUT` | 5.162 ms | 9.607 ms | 9.801 ms | 9.959 ms |
| 120/s (`/slow` 500 ms) | **770 / 7.200** (11 %) | 6.430 `ERR_SOCKET_TIMEOUT` | 5.127 ms | 9.417 ms | 9.801 ms | 9.993 ms |

La latencia de `/slow` solo se mide en las peticiones que sí respondieron (las que tardaron menos
de 10 s); por eso el máximo queda justo por debajo de 10.000 ms.

## Recursos durante cada prueba (máximos, consultados en Prometheus)

| Prueba | Req/s en Nginx | Conexiones Nginx | CPU app1 / app2 / app3 | CPU Nginx | RAM por backend | RAM Nginx |
|---|---|---|---|---|---|---|
| 70 por minuto | 1,4 | 6 | 1,9 / 2,4 / 1,9 % | 0,1 % | 33-35 MiB | 12 MiB |
| 100/s | 100,2 | 401 | 6,8 / 6,5 / 6,0 % | 5,6 % | 34-36 MiB | 15 MiB |
| 120/s | 120,2 | 482 | 7,6 / 8,4 / 7,7 % | 7,5 % | 36-38 MiB | 16 MiB |
| Saturación 100/s | 100,2 | **1.154** | 9,6 / 11,1 / 10,4 % | 4,6 % | 55-58 MiB | 33 MiB |
| Saturación 120/s | 120,2 | **1.269** | 13,0 / 14,1 / 12,6 % | 5,7 % | 58-59 MiB | 37 MiB |

(CPU en % de un núcleo. Las "conexiones Nginx" incluyen las que quedan abiertas en espera
*keep-alive* después de responder; por eso hay cientos incluso con `/`.)

## Análisis (para el informe)

### 1. Con `/`, el sistema aguanta 120 peticiones/s sin errores
El p95 pasó de 2 ms (70/min) a solo 3 ms (120/s). La CPU de cada backend no superó el 8,4 %:
hay capacidad de sobra. La guía pedía superar 65 peticiones/minuto; el sistema maneja
120 por **segundo** (unas 110 veces más) sin degradarse.

### 2. Con `/slow`, el sistema se satura como predijo el cálculo
- Los backends **sí procesaron todas** las peticiones (según sus propias métricas, unas 2.030
  cada uno en la prueba de 100/s, ~6.090 en total), pero a su ritmo máximo: la de 100/s tardó
  en vaciar la cola unos 132 s (de 14:21:31 a 14:23:43), es decir **~46 peticiones/s**, casi
  exactamente los **48/s** calculados en papel.
- Llegaban 100 por segundo y salían ~48: la **cola crecía ~52 peticiones cada segundo**. A los
  pocos segundos, cada petición nueva tenía que esperar más de 10 s y Artillery la abandonaba
  (`ERR_SOCKET_TIMEOUT`). El backend la procesaba de todos modos, más tarde: **trabajo
  desperdiciado**. Por eso solo 889 respuestas (100/s) y 770 (120/s) llegaron a tiempo, menos
  que las ~2.880 que permitiría la capacidad: a más carga, peor (770 < 889).
- **La CPU de los backends no pasó del 14 %:** estaban *esperando* (cada hilo dormido en
  `/slow`), no calculando. Saturación no significa CPU al 100 %; el límite eran los 24 hilos.
- La memoria de los backends subió de ~35 a ~58 MiB y la de Nginx de 15 a 37 MiB por las
  más de 1.200 conexiones que mantenía en espera.

### 3. Efectos secundarios de la saturación (hallazgos)
- **Los 3 backends quedaron `unhealthy` en Docker:** el healthcheck `/health` también hace cola
  detrás de cientos de `/slow` y no responde en sus 3 s. Se recuperaron solos al vaciarse la
  cola (a las 14:23:43 y a las 14:26:44). Nginx no usa ese estado, así que siguió enviando
  tráfico.
- **El monitoreo de los backends también se degradó:** entre 14:21:38 y 14:23:33, Prometheus
  no pudo leer `/metrics` en unas 23 de 72 visitas por backend (un tercio), porque `/metrics`
  compite por los mismos 8 hilos que `/slow`. En Grafana, las gráficas de peticiones y latencia
  de los backends tendrán **huecos** durante la saturación. cAdvisor y el exporter de Nginx no
  dependen de los backends y siguieron midiendo sin problemas.

### 4. Ideas para reducir las fallas (solo se proponen, no se implementan)
- Más hilos o más réplicas de backend: cada réplica suma 8 / 0,5 = 16 peticiones/s con `/slow`.
- Limitar la tasa en Nginx (`limit_req`) para rechazar rápido (código 503) en lugar de dejar
  crecer la cola.
- Servir `/metrics` y `/health` en un puerto o proceso separado, para que el monitoreo no se
  quede ciego justo cuando más se necesita.

## Capturas sugeridas para el informe y el video (las toma el equipo)
1. Una terminal con `artillery run loadtest/carga-120-por-segundo.yml` y su resumen final.
2. Una terminal con `artillery run loadtest/saturacion-100-por-segundo.yml` y su resumen final.
3. El dashboard de Grafana con el rango de tiempo **14:17 a 14:28 del 9 de noviembre**: se ven
   las 5 pruebas seguidas (requiere haber armado el dashboard).
4. `docker compose ps` durante la saturación, con los backends `unhealthy`.
