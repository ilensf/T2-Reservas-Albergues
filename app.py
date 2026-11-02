"""Aplicacion de reservas Camiño Aberto."""
import json
import os
import threading
import time
from datetime import date

from dotenv import load_dotenv
import psycopg
import redis

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
PGHOST = os.getenv("PGHOST", "localhost")
PGUSER = os.getenv("POSTGRES_USER", "p1")
PGPASSWORD = os.getenv("POSTGRES_PASSWORD", "cambiame")
PGDB = os.getenv("POSTGRES_DB", "albergues")
TTL = 60

def pg_conn():
    return psycopg.connect(dbname=PGDB, user=PGUSER, password=PGPASSWORD, host=PGHOST)

def redis_cli():
    return redis.Redis(host=REDIS_HOST, decode_responses=True)

def clave_dispo(aid, fecha):
    return f"dispo:{aid}:{fecha.isoformat()}"

def clave_cache(camino, fecha):
    return f"cache:{camino}:{fecha.isoformat()}"

def inicializar(r):
    with pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, prazas FROM albergues")
            cap = {a: p for a, p in cur.fetchall()}
            cur.execute("SELECT albergue_id, data, SUM(prazas) FROM reservas GROUP BY albergue_id, data")
            occ = {(a, d): t for a, d, t in cur.fetchall()}
    pipe = r.pipeline()
    for (a, d), o in occ.items():
        pipe.set(clave_dispo(a, d), max(0, cap.get(a, 0) - o))
    pipe.execute()

def capacidad(aid):
    with pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT prazas FROM albergues WHERE id=%s", (aid,))
            f = cur.fetchone()
            return f[0] if f else None

def reservar(aid, fecha, peregrino, prazas=1):
    r = redis_cli()
    k = clave_dispo(aid, fecha)
    if r.get(k) is None:
        c = capacidad(aid)
        if c is None:
            return False, "albergue inexistente"
        r.set(k, c)
    resto = r.decrby(k, prazas)
    if resto < 0:
        r.incrby(k, prazas)
        return False, "sen prazas"
    try:
        with pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO reservas (albergue_id, peregrino_id, data, prazas) VALUES (%s,%s,%s,%s)", (aid, peregrino, fecha, prazas))
                conn.commit()
        return True, None
    except Exception as e:
        r.incrby(k, prazas)
        return False, str(e)

def dispo_camino(camino, fecha):
    r = redis_cli()
    k = clave_cache(camino, fecha)
    c = r.get(k)
    if c is not None:
        return json.loads(c), "cache"
    with pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nome, prazas FROM albergues WHERE camino=%s", (camino,))
            algs = cur.fetchall()
            cur.execute("SELECT albergue_id, SUM(prazas) FROM reservas WHERE data=%s GROUP BY albergue_id", (fecha,))
            occ = {a: t for a, t in cur.fetchall()}
    res = []
    for aid, nom, pz in algs:
        libres = pz - occ.get(aid, 0)
        if libres > 0:
            res.append({"albergue_id": aid, "nome": nom, "prazas_libres": libres})
    r.setex(k, TTL, json.dumps(res))
    return res, "bd"

def proba_superventa(aid, fecha, pz_tot, n):
    r = redis_cli()
    k = clave_dispo(aid, fecha)
    r.set(k, pz_tot)
    with pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reservas WHERE albergue_id=%s AND data=%s", (aid, fecha))
            conn.commit()
    acc = {"n": 0}
    lock = threading.Lock()
    def i(x):
        ok, _ = reservar(aid, fecha, x+1, 1)
        if ok:
            with lock:
                acc["n"] += 1
    hs = [threading.Thread(target=i, args=(x,)) for x in range(n)]
    for h in hs: h.start()
    for h in hs: h.join()
    cr = int(r.get(k))
    with pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT SUM(prazas) FROM reservas WHERE albergue_id=%s AND data=%s", (aid, fecha))
            tp = cur.fetchone()[0] or 0
    print("Superventa:", acc["n"], pz_tot, tp, cr)
    return acc["n"] == pz_tot == tp and cr == 0

def medir_pg(aid, fecha):
    ini = time.perf_counter()
    with pg_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT prazas FROM albergues WHERE id=%s", (aid,))
            pz = cur.fetchone()[0]
            cur.execute("SELECT SUM(prazas) FROM reservas WHERE albergue_id=%s AND data=%s", (aid, fecha))
            o = cur.fetchone()[0] or 0
    _ = pz - o
    return time.perf_counter() - ini

def medir_redis(r, aid, fecha):
    ini = time.perf_counter()
    _ = r.get(clave_dispo(aid, fecha))
    return time.perf_counter() - ini

def mediciones(aid, fecha, rep=100):
    r = redis_cli()
    if r.get(clave_dispo(aid, fecha)) is None:
        r.set(clave_dispo(aid, fecha), capacidad(aid) or 0)
    tpg = sum(medir_pg(aid, fecha) for _ in range(rep)) / rep
    tr = sum(medir_redis(r, aid, fecha) for _ in range(rep)) / rep
    print(f"PG {tpg*1000:.2f}ms Redis {tr*1000:.2f}ms")

def main():
    r = redis_cli()
    inicializar(r)
    hoy = date(2027, 5, 10)
    ok, msg = reservar(1, hoy, 1001, 1)
    print("Reserva ejemplo:", ok, msg)
    proba_superventa(5, date(2027, 5, 15), 3, 20)
    r.delete(clave_cache("Frances", date(2027, 5, 12)))
    res1, o1 = dispo_camino("Frances", date(2027, 5, 12))
    res2, o2 = dispo_camino("Frances", date(2027, 5, 12))
    print("Cache:", o1, o2, len(res1), len(res2))
    mediciones(1, hoy)

if __name__ == "__main__":
    main()
