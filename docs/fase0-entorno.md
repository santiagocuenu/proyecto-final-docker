# Fase 0 – Preparación del entorno

Fecha: 9 de noviembre de 2026

## Qué se hizo

1. Se activó la integración de Docker Desktop con WSL2
   (Docker Desktop → Settings → Resources → WSL Integration → activar la distro Ubuntu).
   Antes de esto, el comando `docker` no existía dentro de WSL.
2. Se instalaron Node.js y Artillery dentro de WSL (Ubuntu), porque la guía pide
   ejecutar la prueba de carga **desde la máquina física** y no desde un contenedor
   (en el laboratorio, Artillery corría dentro de Docker).

```bash
sudo apt update && sudo apt install -y nodejs npm && sudo npm install -g artillery@2.0.34
```

## Por qué estas decisiones

- **Artillery en WSL y no en Windows:** WSL corre en el mismo computador físico,
  usa la misma terminal bash del laboratorio y llega a `localhost:8080` igual que el navegador.
- **Versión fija (`artillery@2.0.34`):** igual que con las imágenes Docker, fijar la versión
  hace que la prueba sea reproducible. Se eligió la última versión estable con más de dos
  semanas de publicada (agosto de 2026).
- **Node.js 22 desde los repositorios de Ubuntu:** Artillery 2.0.34 exige Node ≥ 22.18;
  Ubuntu 26.04 trae la 22.22.1, así que no hizo falta instalar Node por otra vía.

## Cómo se verificó

```text
$ docker --version
Docker version 29.9.2, build a82e528
$ docker compose version
Docker Compose version v5.6.1
$ docker run --rm hello-world
Hello from Docker!
This message shows that your installation appears to be working correctly.

$ node --version        → v22.22.1
$ npm --version         → 9.2.0
$ artillery version     → Artillery: 2.0.34 / Node.js: v22.22.1

$ docker info  → CPUs=12  Mem≈7,6 GiB  cgroup v2  OS=Docker Desktop  storage=overlayfs
```

Puertos que usará el proyecto, comprobados como libres: 8080 (Nginx), 3000 (Grafana),
8081 (cAdvisor), 9090 (Prometheus), 9113 (nginx-exporter).

## Problemas encontrados

- El primer intento de instalación se lanzó desde una terminal no interactiva y `sudo` falló
  (*"A terminal is required to authenticate"*): no había una terminal real donde escribir la
  contraseña. Solución: ejecutar la instalación en una pestaña normal de WSL.
- Docker Desktop usa el almacén de imágenes de containerd (`storage=overlayfs`) y cgroup v2.
  Es un dato a tener en cuenta en la Fase 4: con esta configuración, cAdvisor puede no mostrar
  los nombres de los contenedores.

## Nota para el informe

Docker Desktop reserva para su máquina virtual unos 7,6 GiB de los 16 GB del equipo.
Es suficiente para los 8 contenedores del proyecto.
