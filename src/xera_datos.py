"""Xerador de datos de proba para a rede de albergues Camiño Aberto (ficticia).

ESQUELETO DO P1. Xa funciona: xera albergues e mostra un resumo. O resto
das funcións están marcadas con TODO e, mentres non as completes, avisan
e devolven unha lista baleira para que o script se poida executar desde o
primeiro día.

Exemplos (desde a raíz do proxecto):
  python -m src.xera_datos --sen-carga                    # só xerar e mostrar
  python -m src.xera_datos --albergues 60 --semente 7 --sen-carga
  python -m src.xera_datos                                 # xerar e cargar (cando estea feito)
"""
import argparse
import random
import os
from datetime import date, timedelta
from pymongo import MongoClient
import psycopg
from dotenv import load_dotenv
from faker import Faker

load_dotenv()  

DATA_REFERENCIA_NACEMENTOS = date(2026, 1, 1)
DATA_INICIAL_NACEMENTOS = date(1940, 1, 1)

# ------------------------------------------------------------------ catálogos
# Concellos galegos de cada camiño, en orde de etapas. Podes engadir máis.
CAMIÑOS = {
    "Francés":   ["Pedrafita do Cebreiro", "Triacastela", "Samos", "Sarria", "Portomarín",
                  "Palas de Rei", "Melide", "Arzúa", "O Pino"],
    "Portugués": ["Tui", "O Porriño", "Redondela", "Pontevedra", "Caldas de Reis", "Padrón", "Teo"],
    "Norte":     ["Ribadeo", "Lourenzá", "Mondoñedo", "Abadín", "Vilalba", "Guitiriz", "Sobrado"],
    "Primitivo": ["A Fonsagrada", "Castroverde", "Lugo", "Friol", "Melide"],
    "Inglés":    ["Ferrol", "Neda", "Pontedeume", "Betanzos", "Abegondo", "Ordes"],
}
NOMES_ALBERGUE = ["Vieiras", "Pedra Miúda", "O Cruceiro", "A Ponte Vella", "Bordón", "A Cabaciña",
                  "Fonte Vella", "Os Carballos", "A Estrela", "Camiño Real", "Casa do Peregrino",
                  "A Xesta", "O Muíño", "Santa Mariña", "O Hórreo", "A Lareira", "Sete Fontes"]


def pendente(nome):
    print(f"  [pendente] {nome}() aínda non está feita")
    return []


# ------------------------------------------------------------------ xeración
def xera_albergues(n, rng):
    """EXEMPLO RESOLTO: úsao como modelo para o resto de funcións.

    Devolve unha lista de dicionarios, un por albergue. Todo o azar sae de `rng`
    (un random.Random), non do módulo `random` directamente: así a semente controla
    o resultado.
    """
    albergues = []
    for i in range(1, n + 1):
        camino = rng.choice(list(CAMIÑOS))
        concello = rng.choice(CAMIÑOS[camino])
        albergues.append({
            "id": i,
            "nome": f"Albergue {rng.choice(NOMES_ALBERGUE)} ({concello})",
            "camino": camino,
            "concello": concello,
            "prazas": rng.randint(8, 60),
            "prezo": float(rng.randint(10, 22)),
        })
    return albergues


def xera_peregrinos(n, rng, fake):
    """TODO (primeiro paso): devolve `n` peregrinos.

    Cada peregrino é un dicionario con, polo menos: id, nome, apelidos, documento,
    email, pais e data_nacemento.

    Pistas:
      - fake.first_name() e fake.last_name() dan nomes realistas.
      - Faker(["es_ES", "pt_PT", "de_DE"]) mestura idiomas, pero para saber o país
        de cada peregrino é máis cómodo ter un Faker por país.
      - O documento e o email deben ser únicos.
      - Usa o intervalo fixo de datas de nacemento para evitar depender do día
        no que se execute o xerador.
    """
    peregrinos = []

    for i in range(1, n + 1):
        peregrinos.append({
            "id": i,
            "nome": fake.first_name(),
            "apelidos": fake.last_name(),
            "documento": fake.unique.ssn(),
            "email": fake.unique.email(),
            "pais": fake.country(),
            "data_nacemento": fake.date_between_dates(
                date_start=DATA_INICIAL_NACEMENTOS,
                date_end=DATA_REFERENCIA_NACEMENTOS,
            ),
        })

    return peregrinos


def xera_reservas(n, albergues, peregrinos, desde, dias, rng):
    """Devolve ata `n` reservas entre `desde` e `desde + dias - 1`.

    As prazas reservadas nun albergue e noite non superan a súa capacidade.
    """
    reservas = []
    prazas_ocupadas = {}

    for i in range(1, n + 1):
        albergue = rng.choice(albergues)
        peregrino = rng.choice(peregrinos)
        noite = desde + timedelta(days=rng.randint(0, dias - 1))
        clave = (albergue["id"], noite)
        dispoñibles = albergue["prazas"] - prazas_ocupadas.get(clave, 0)
        if dispoñibles <= 0:
            continue

        prazas = rng.randint(1, min(4, dispoñibles))
        reservas.append({
            "id": i,
            "albergue_id": albergue["id"],
            "peregrino_id": peregrino["id"],
            "data": noite,
            "prazas": prazas,
        })
        prazas_ocupadas[clave] = prazas_ocupadas.get(clave, 0) + prazas

    return reservas


def xera_fichas(albergues, rng, fake):
    """Devolve unha ficha por albergue para MongoDB con campos variables."""
    fichas = []
    caminos = ["Francés", "Portugués", "Primitivo", "Norte", "Inglés", "Vía da Prata"]
    servizos_base = ["cociña", "lavadora", "wifi", "almorzo", "tendedoiro", "enfermería", "máquina de refrescos"]
    idiomas_base = ["galego", "castelán", "inglés", "francés", "alemán", "italiano"]

    for albergue in albergues:
        # Asumimos que albergue é un tuplo (id, nome, ...) de PostgreSQL ou un dicionario
        albergue_id = albergue["id"] if isinstance(albergue, dict) else albergue[0]
        nome_albergue = albergue["nome"] if isinstance(albergue, dict) else albergue[1]

        # Campos base que teñen todos os albergues
        ficha = {
            "albergue_id": albergue_id,
            "nome": nome_albergue,
            "camino": rng.choice(caminos),
            "servizos": rng.sample(servizos_base, k=rng.randint(1, len(servizos_base))),
            "horario": {
                "apertura": f"{rng.randint(11, 14):02d}:00",
                "peche": f"{rng.randint(21, 23):02d}:{rng.choice(['00', '30'])}"
            }
        }

        # CAMPOS VARIABLES: Non todos os albergues terán estas claves

        # 1. Contacto (pode ter só teléfono, só web, ambos ou ningún)
        if rng.random() > 0.3:
            contacto = {}
            if rng.random() > 0.2:
                contacto["telefono"] = fake.phone_number()
            if rng.random() > 0.4:
                contacto["web"] = fake.url()
            if contacto:
                ficha["contacto"] = contacto

        # 2. Admisión de cans
        if rng.random() > 0.6:
            ficha["admite_cans"] = rng.choice([True, False])

        # 3. Instalacións para bicicletas
        if rng.random() > 0.5:
            ficha["bicicletas"] = {
                "garaxe": True,
                "prazas": rng.randint(5, 30)
            }

        # 4. Idiomas falados polo persoal
        if rng.random() > 0.2:
            ficha["idiomas"] = rng.sample(idiomas_base, k=rng.randint(1, 3))

        # 5. Opinións dos peregrinos (número variable)
        if rng.random() > 0.4:
            num_opinions = rng.randint(1, 4)
            opinions = []
            for _ in range(num_opinions):
                opinions.append({
                    "autor": f"{fake.first_name()[0]}.", # Ex: "M."
                    "nota": rng.randint(1, 5),
                    "texto": fake.sentence(nb_words=rng.randint(3, 8))
                })
            ficha["opinions"] = opinions
            
        # 6. Titularidade (público ou privado)
        if rng.random() > 0.5:
             ficha["titularidade"] = rng.choice(["Xunta de Galicia", "Concello", "Privada", "Asociación"])

        fichas.append(ficha)

    return fichas


# ------------------------------------------------------------------ carga
def carga_postgres(albergues, peregrinos, reservas):
    """Crea as táboas (se non existen) e insire os datos xerados en PostgreSQL."""
    try:
        # A conexión asume que a base de datos xa está levantada en localhost
        with psycopg.connect(
            dbname=os.getenv("POSTGRES_DB", "albergues"),
            user=os.getenv("POSTGRES_USER", "p1"),
            password=os.getenv("POSTGRES_PASSWORD", "cambiame"),
            host=os.getenv("PGHOST", "localhost")
        ) as conn:
            with conn.cursor() as cur:
                # 1. Definición do esquema
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS albergues (
                        id INTEGER PRIMARY KEY,
                        nome VARCHAR(100),
                        camino VARCHAR(50),
                        concello VARCHAR(50),
                        prazas INTEGER,
                        prezo DECIMAL(5,2)
                    );
                    
                    CREATE TABLE IF NOT EXISTS peregrinos (
                        id INTEGER PRIMARY KEY,
                        nome VARCHAR(50),
                        apelidos VARCHAR(100),
                        documento VARCHAR(50) UNIQUE,
                        email VARCHAR(100) UNIQUE,
                        pais VARCHAR(50),
                        data_nacemento DATE
                    );
                    
                    CREATE TABLE IF NOT EXISTS reservas (
                        id INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                        albergue_id INTEGER REFERENCES albergues(id),
                        peregrino_id INTEGER REFERENCES peregrinos(id),
                        data DATE,
                        prazas INTEGER
                    );
                """)
                
                # Limpar a base de datos por se executas o script varias veces
                cur.execute("TRUNCATE reservas, peregrinos, albergues RESTART IDENTITY CASCADE;")
                
                # 2. Carga de datos usando executemany para maior rendemento
                print("  [PostgreSQL] Inserindo albergues...")
                cur.executemany(
                    "INSERT INTO albergues (id, nome, camino, concello, prazas, prezo) VALUES (%(id)s, %(nome)s, %(camino)s, %(concello)s, %(prazas)s, %(prezo)s)",
                    albergues
                )
                
                print("  [PostgreSQL] Inserindo peregrinos...")
                cur.executemany(
                    "INSERT INTO peregrinos (id, nome, apelidos, documento, email, pais, data_nacemento) VALUES (%(id)s, %(nome)s, %(apelidos)s, %(documento)s, %(email)s, %(pais)s, %(data_nacemento)s)",
                    peregrinos
                )
                
                print("  [PostgreSQL] Inserindo reservas históricas...")
                cur.executemany(
                    "INSERT INTO reservas (id, albergue_id, peregrino_id, data, prazas) VALUES (%(id)s, %(albergue_id)s, %(peregrino_id)s, %(data)s, %(prazas)s)",
                    reservas
                )
                
                conn.commit()
                print("  [PostgreSQL] Carga completada con éxito.")
                
    except Exception as e:
        print(f"Erro conectando ou cargando en PostgreSQL: {e}")


def carga_mongo(fichas):
    """Garda as fichas variables nunha colección de MongoDB."""
    try:
        client = MongoClient(
            host=os.getenv("MONGO_HOST", "localhost"),
            username=os.getenv("MONGO_INITDB_ROOT_USERNAME", "p1"),
            password=os.getenv("MONGO_INITDB_ROOT_PASSWORD", "cambiame")
        )
        db = client[os.getenv("MONGO_DB", "albergues")]
        coleccion = db["fichas_albergues"]
        
        # Baleirar a colección antes de recargar
        coleccion.delete_many({})
        
        print("  [MongoDB] Inserindo fichas de albergues...")
        if fichas:
            coleccion.insert_many(fichas)
            
        print("  [MongoDB] Carga completada con éxito.")
        client.close()
        
    except Exception as e:
        print(f"Erro conectando ou cargando en MongoDB: {e}")


# ------------------------------------------------------------------ main
def mostra(titulo, filas, cantas=2):
    print(f"\n{titulo}: {len(filas)}")
    for f in filas[:cantas]:
        print(f"  {f}")


def main():
    ap = argparse.ArgumentParser(description="Xera e carga datos de proba de Camiño Aberto")
    ap.add_argument("--albergues", type=int, default=40)
    ap.add_argument("--peregrinos", type=int, default=1500)
    ap.add_argument("--reservas", type=int, default=5000)
    ap.add_argument("--semente", type=int, default=42, help="mesma semente → mesmos datos")
    ap.add_argument("--desde", type=date.fromisoformat, default=date(2027, 5, 1),
                    help="primeira noite da tempada (AAAA-MM-DD)")
    ap.add_argument("--dias", type=int, default=30, help="número de noites da tempada")
    ap.add_argument("--sen-carga", action="store_true", help="xera e mostra, pero non carga nada")
    args = ap.parse_args()

    rng = random.Random(args.semente)
    fake = Faker("es_ES")
    fake.seed_instance(args.semente)

    print(f"Semente {args.semente} · tempada {args.desde} + {args.dias} noites")
    albergues = xera_albergues(args.albergues, rng)
    peregrinos = xera_peregrinos(args.peregrinos, rng, fake)
    reservas = xera_reservas(args.reservas, albergues, peregrinos, args.desde, args.dias, rng)
    fichas = xera_fichas(albergues, rng, fake)

    mostra("Albergues", albergues)
    mostra("Peregrinos", peregrinos)
    mostra("Reservas", reservas)
    mostra("Fichas", fichas, 1)

    if not args.sen_carga:
        carga_postgres(albergues, peregrinos, reservas)
        carga_mongo(fichas)


if __name__ == "__main__":
    main()
