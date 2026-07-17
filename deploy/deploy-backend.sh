#!/usr/bin/env bash
#
# Despliega el backend de SaludAgendaX a una instancia EC2 usando rsync + Docker Compose.
#
# Variables de entorno:
#   EC2_HOST   (requerida) Host de la instancia EC2, formato usuario@ip (ej. ubuntu@1.2.3.4)
#   SSH_KEY    (opcional)  Ruta al archivo .pem para autenticacion SSH
#   REMOTE_DIR (opcional)  Directorio remoto donde se copia el codigo (default: saludagendax-backend, relativo al home remoto)
#
# Flags:
#   --setup    Instala Docker y el plugin docker compose en el EC2 antes de desplegar (idempotente)
#
# Ejemplos:
#   EC2_HOST=ubuntu@1.2.3.4 SSH_KEY=~/claves/mi-llave.pem ./deploy/deploy-backend.sh
#   EC2_HOST=ubuntu@1.2.3.4 SSH_KEY=~/claves/mi-llave.pem ./deploy/deploy-backend.sh --setup

EC2_HOST="ec2-user@ec2-13-220-179-121.compute-1.amazonaws.com"
SSH_KEY="/home/agox/.ssh/key-desarrollo.pem"
set -euo pipefail

# Ruta relativa al home del usuario remoto (sin ~: entre comillas no se expande)
REMOTE_DIR="${REMOTE_DIR:-saludagendax-backend}"
RUN_SETUP=false

for arg in "$@"; do
  case "$arg" in
  --setup)
    RUN_SETUP=true
    ;;
  *)
    echo "Argumento desconocido: $arg" >&2
    exit 1
    ;;
  esac
done

echo "==> Verificando requisitos locales..."
for cmd in rsync ssh; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Error: '$cmd' no esta instalado localmente. Instalalo antes de continuar." >&2
    exit 1
  fi
done

if [ -z "${EC2_HOST:-}" ]; then
  echo "Error: la variable de entorno EC2_HOST es requerida (formato usuario@ip)." >&2
  echo "Ejemplo: EC2_HOST=ubuntu@1.2.3.4 ./deploy/deploy-backend.sh" >&2
  exit 1
fi

SSH_OPTS=()
RSYNC_SSH="ssh"
if [ -n "${SSH_KEY:-}" ]; then
  SSH_OPTS+=(-i "$SSH_KEY")
  RSYNC_SSH="ssh -i $SSH_KEY"
fi

_BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$_BASE/../manage.py" ]; then
  # El script vive dentro del repo (carpeta deploy/)
  SCRIPT_DIR="$(cd "$_BASE/.." && pwd)"
else
  # El script vive en ~/desarrollo1/deploy-scripts, junto a los repos
  SCRIPT_DIR="$(cd "$_BASE/../backend-django" && pwd)"
fi
cd "$SCRIPT_DIR"

echo "==> Directorio local del proyecto: $SCRIPT_DIR"
echo "==> Host remoto: $EC2_HOST"
echo "==> Directorio remoto: $REMOTE_DIR"

if [ "$RUN_SETUP" = true ]; then
  echo "==> Instalando Docker y docker compose en el EC2 (--setup)..."
  ssh "${SSH_OPTS[@]}" "$EC2_HOST" '
    set -euo pipefail
    if ! command -v docker >/dev/null 2>&1; then
      . /etc/os-release
      if [ "${ID:-}" = "amzn" ]; then
        # get.docker.com no soporta Amazon Linux; se instala desde los repos de AWS
        sudo dnf install -y docker
        sudo systemctl enable --now docker
      else
        curl -fsSL https://get.docker.com | sudo sh
      fi
      sudo usermod -aG docker "$USER"
      echo "Docker instalado. Es posible que debas reconectar la sesion SSH para que el grupo docker tenga efecto."
    else
      echo "Docker ya esta instalado, se omite instalacion."
    fi
    if ! docker compose version >/dev/null 2>&1; then
      # Amazon Linux no empaqueta el plugin compose junto con docker
      ARCH=$(uname -m)
      sudo mkdir -p /usr/local/lib/docker/cli-plugins
      sudo curl -fsSL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-${ARCH}" \
        -o /usr/local/lib/docker/cli-plugins/docker-compose
      sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
    fi
    BX_OK=false
    if docker buildx version >/dev/null 2>&1; then
      BX_CUR=$(docker buildx version | sed -n "s/.*v\([0-9.]*\).*/\1/p")
      if [ "$(printf "%s\n0.17.0\n" "$BX_CUR" | sort -V | head -1)" = "0.17.0" ]; then
        BX_OK=true
      fi
    fi
    if [ "$BX_OK" = false ]; then
      # compose build moderno requiere buildx >= 0.17; el de los repos de Amazon Linux es mas viejo
      case "$(uname -m)" in aarch64) BX_ARCH=arm64 ;; *) BX_ARCH=amd64 ;; esac
      BX_VER=$(curl -fsSL https://api.github.com/repos/docker/buildx/releases/latest | grep -m1 tag_name | cut -d\" -f4)
      sudo mkdir -p /usr/local/lib/docker/cli-plugins
      sudo curl -fsSL "https://github.com/docker/buildx/releases/download/${BX_VER}/buildx-${BX_VER}.linux-${BX_ARCH}" \
        -o /usr/local/lib/docker/cli-plugins/docker-buildx
      sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-buildx
    fi
    if ! docker compose version >/dev/null 2>&1; then
      echo "Error: el plugin docker compose no esta disponible tras la instalacion de Docker." >&2
      exit 1
    fi
  '
  echo "==> Setup completado."
fi

echo "==> Verificando archivo de variables de entorno (.env.production)..."
LOCAL_ENV_FILE=false
if [ -f "$SCRIPT_DIR/.env.production" ]; then
  LOCAL_ENV_FILE=true
  echo "Aviso: se encontro .env.production local y sera copiado al servidor remoto."
else
  echo "No se encontro .env.production local."
  if ssh "${SSH_OPTS[@]}" "$EC2_HOST" "test -f \"$REMOTE_DIR/.env.production\"" 2>/dev/null; then
    echo "Se usara el .env.production ya existente en el servidor remoto."
  else
    echo "Error: no existe .env.production ni localmente ni en el servidor remoto." >&2
    echo "Crea uno a partir de .env.production.example antes de desplegar." >&2
    exit 1
  fi
fi

echo "==> Creando directorio remoto (si no existe)..."
ssh "${SSH_OPTS[@]}" "$EC2_HOST" "mkdir -p \"$REMOTE_DIR\""

echo "==> Sincronizando codigo con rsync..."
# Nota: SSH_KEY y REMOTE_DIR no deben contener espacios; se interpolan en el
# comando remoto/en la opcion -e de rsync sin un escapado exhaustivo (ver DEPLOY.md).
RSYNC_EXCLUDES=(
  --exclude=".venv"
  --exclude=".git"
  --exclude=".claude"
  --exclude="graphify-out"
  --exclude="__pycache__"
  --exclude="db.sqlite3"
  --exclude="celerybeat-schedule*"
  --exclude="*.pdf"
  --exclude="HU*.md"
  --exclude="docs/"
  --exclude="ApiTests/"
  --exclude=".env.local"
  --exclude="Untitled"
  --exclude="staticfiles"
)

if [ "$LOCAL_ENV_FILE" = true ]; then
  rsync -avz --delete "${RSYNC_EXCLUDES[@]}" -e "$RSYNC_SSH" "$SCRIPT_DIR/" "$EC2_HOST:$REMOTE_DIR/"
else
  rsync -avz --delete "${RSYNC_EXCLUDES[@]}" --exclude=".env.production" -e "$RSYNC_SSH" "$SCRIPT_DIR/" "$EC2_HOST:$REMOTE_DIR/"
fi

echo "==> Construyendo la imagen en el servidor remoto..."
ssh "${SSH_OPTS[@]}" "$EC2_HOST" "cd \"$REMOTE_DIR\" && docker compose build"

echo "==> Ejecutando migraciones de base de datos (antes de servir trafico)..."
ssh "${SSH_OPTS[@]}" "$EC2_HOST" "cd \"$REMOTE_DIR\" && docker compose run --rm web python manage.py migrate"

echo "==> Levantando los servicios..."
ssh "${SSH_OPTS[@]}" "$EC2_HOST" "cd \"$REMOTE_DIR\" && docker compose up -d"

echo "==> Estado de los contenedores:"
ssh "${SSH_OPTS[@]}" "$EC2_HOST" "cd \"$REMOTE_DIR\" && docker compose ps"

echo "==> Despliegue completado con exito."
