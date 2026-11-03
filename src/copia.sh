#!/usr/bin/env bash
# --------------------------------------------------------------------------
# Copias de seguridade do proxecto P1 · Reservas de albergues do Camiño.
# Garda nun cartafol copias/ (con data e hora) unha copia de PostgreSQL
# (pg_dump) e de MongoDB (mongodump).
#
# Uso (desde a raíz do proxecto): ./src/copia.sh   [ou   bash src/copia.sh]
# --------------------------------------------------------------------------
set -euo pipefail

# Cargamos as credenciais do .env se existe
if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a
    . .env
    set +a
fi

# Valores por defecto (coinciden co .env.example)
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"
PGUSER="${POSTGRES_USER:-p1}"
PGPASSWORD="${POSTGRES_PASSWORD:-cambiame}"
PGDB="${POSTGRES_DB:-albergues}"

MONGO_HOST="${MONGO_HOST:-localhost}"
MONGO_PORT="${MONGO_PORT:-27017}"
MONGO_USER="${MONGO_USER:-p1}"
MONGO_PASSWORD="${MONGO_PASSWORD:-cambiame}"
MONGO_DB="${MONGO_DB:-albergues}"

DEST_DIR="copias"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$DEST_DIR/copia_$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

echo "=== Copia de seguridade $TIMESTAMP ==="
echo "Destino: $BACKUP_DIR"

# --- PostgreSQL: pg_dump ---
export PGPASSWORD
PG_DUMP_FILE="$BACKUP_DIR/postgres_$PGDB.sql"
if pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDB" > "$PG_DUMP_FILE" 2>/dev/null; then
    echo "[OK] PostgreSQL gardado en $PG_DUMP_FILE"
else
    echo "[ERRO] Fallou o pg_dump de PostgreSQL" >&2
    exit 1
fi
unset PGPASSWORD

# --- MongoDB: mongodump ---
MONGO_DUMP_DIR="$BACKUP_DIR/mongo_$MONGO_DB"
if mongodump --host "$MONGO_HOST" --port "$MONGO_PORT" \
    --username "$MONGO_USER" --password "$MONGO_PASSWORD" \
    --db "$MONGO_DB" --out "$MONGO_DUMP_DIR" 2>/dev/null; then
    echo "[OK] MongoDB gardado en $MONGO_DUMP_DIR"
else
    echo "[ERRO] Fallou o mongodump de MongoDB" >&2
    exit 1
fi

echo "=== Copia completada: $BACKUP_DIR ==="
