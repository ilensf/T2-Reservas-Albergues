#!/usr/bin/env bash
# --------------------------------------------------------------------------
# Copias de seguridade do proxecto P1 · Reservas de albergues do Camiño.
# --------------------------------------------------------------------------
set -euo pipefail

if [ -f .env ]; then
    # shellcheck disable=SC1091
    set -a
    . .env
    set +a
fi

PGUSER="${POSTGRES_USER:-p1}"
PGPASSWORD="${POSTGRES_PASSWORD:-cambiame}"
PGDB="${POSTGRES_DB:-albergues}"

MONGO_USER="${MONGO_USER:-${MONGO_INITDB_ROOT_USERNAME:-p1}}"
MONGO_PASSWORD="${MONGO_PASSWORD:-${MONGO_INITDB_ROOT_PASSWORD:-cambiame}}"
MONGO_DB="${MONGO_DB:-albergues}"

DEST_DIR="copias"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="$DEST_DIR/copia_$TIMESTAMP"

mkdir -p "$BACKUP_DIR"

echo "=== Copia de seguridade $TIMESTAMP ==="
echo "Destino: $BACKUP_DIR"

# --- PostgreSQL: docker exec pg_dump ---
PG_DUMP_FILE="$BACKUP_DIR/postgres_$PGDB.sql"
# Contedor: p1_postgres (sen o 2>/dev/null para ver posibles erros)
if docker exec -e PGPASSWORD="$PGPASSWORD" p1_postgres pg_dump -U "$PGUSER" -d "$PGDB" > "$PG_DUMP_FILE"; then
    echo "[OK] PostgreSQL gardado en $PG_DUMP_FILE"
else
    echo "[ERRO] Fallou o pg_dump de PostgreSQL" >&2
    exit 1
fi

# --- MongoDB: docker exec mongodump ---
MONGO_DUMP_FILE="$BACKUP_DIR/mongo_$MONGO_DB.archive"
# Contedor: p1_mongo (sen o 2>/dev/null para ver posibles erros)
if docker exec p1_mongo mongodump --username "$MONGO_USER" --password "$MONGO_PASSWORD" --authenticationDatabase admin --db "$MONGO_DB" --archive > "$MONGO_DUMP_FILE"; then
    echo "[OK] MongoDB gardado en $MONGO_DUMP_FILE"
else
    echo "[ERRO] Fallou o mongodump de MongoDB" >&2
    exit 1
fi

echo "=== Copia completada: $BACKUP_DIR ==="