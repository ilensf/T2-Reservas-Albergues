# Camiño Aberto · Reservas de albergues

Aplicación de proba para xestionar albergues, peregrinos e reservas do Camiño de Santiago. O proxecto emprega PostgreSQL para os datos relacionais, MongoDB para as fichas flexibles dos albergues e Redis para dispoñibilidade e caché.

## Tecnoloxías

- Python e `psycopg` para a aplicación e a conexión con PostgreSQL.
- PostgreSQL 17 para albergues, peregrinos e reservas.
- MongoDB 8.0 para as fichas dos albergues.
- Redis 7.4 para os contadores de prazas dispoñibles e a caché.
- Docker Compose para levantar os servizos; Adminer para consultar PostgreSQL desde o navegador.

## Estrutura do proxecto

```text
.T2-Reservas-Albergues
├── .env.example       # Modelo de configuración local
├── .gitignore
├── README.md
├── app.py             # Reservas, dispoñibilidade, caché e probas
├── compose.yaml       # PostgreSQL, Redis, MongoDB e Adminer
├── requirements.txt   # Dependencias de Python
└── src/
    ├── __init__.py
    ├── copia.sh       # Copias de PostgreSQL e MongoDB
    └── xera_datos.py  # Xeración e carga dos datos de proba
```

O ficheiro `.env` e as copias xeradas gárdanse localmente e están excluídos do repositorio. Os scripts execútanse desde a raíz do proxecto.

## Datos de proba

`src/xera_datos.py` xera datos ficticios e reproducibles coa semente indicada:

- **Albergues:** 40 por defecto, repartidos entre os camiños Francés, Portugués, Norte, Primitivo e Inglés; cada un ten concello, capacidade e prezo.
- **Peregrinos:** 1.500 por defecto, con nome, apelidos, documento, correo, país e data de nacemento.
- **Reservas:** ata 5.000 por defecto, para noites entre o 1 e o 30 de maio de 2027. Cada reserva ocupa de 1 a 4 prazas e non se supera a capacidade do albergue.
- **Fichas MongoDB:** unha por albergue, con servizos, horario e campos opcionais como contacto, admisión de cans, bicicletas, idiomas, opinións e titularidade.

Os valores anteriores son os parámetros por defecto; pódense cambiar con opcións da liña de comandos. A carga substitúe os datos existentes: en PostgreSQL baleira as táboas `reservas`, `peregrinos` e `albergues`, e en MongoDB baleira a colección `fichas_albergues`. Usa `--sen-carga` para xerar e amosar unha mostra sen modificar as bases de datos.

## Posta en marcha

Requisitos: Docker con Docker Compose e Python instalado.

```bash
# Crear a configuración local a partir do modelo
cp .env.example .env

# Levantar PostgreSQL, Redis, MongoDB e Adminer
docker compose up -d

# Crear e activar un contorno virtual (Linux/macOS)
python -m venv .venv
source .venv/bin/activate

# En Windows PowerShell, activar o contorno con:
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

Por defecto, `.env.example` configura as credenciais de desenvolvemento `p1` / `cambiame` e as bases de datos `albergues`. Cambia as credenciais antes de usar o proxecto fóra dun contorno local.

Xera unha mostra sen cargar datos:

```bash
python -m src.xera_datos --sen-carga
```

Xera e carga os valores por defecto:

```bash
python -m src.xera_datos
```

Tamén se poden indicar cantidades, semente e período:

```bash
python -m src.xera_datos --albergues 40 --peregrinos 1500 --reservas 5000 --semente 42 --desde 2027-05-01 --dias 30
```

A aplicación execútase con:

```bash
python app.py
```

Adminer queda dispoñible en <http://localhost:8080>. Para PostgreSQL, selecciona o servidor `postgres` se accedes desde a rede de Docker, e usa as credenciais definidas en `.env`.

## Funcionamento da aplicación

- `reservar()` desconta prazas cun `DECRBY` atómico de Redis. Se non quedan prazas, reverte o contador; se falla a inserción en PostgreSQL, tamén devolve as prazas ao contador.
- As claves de dispoñibilidade teñen o formato `dispo:<albergue_id>:<AAAA-MM-DD>`.
- A busca de albergues con prazas libres por camiño gárdase en Redis durante 60 segundos, baixo a clave `cache:<camiño>:<AAAA-MM-DD>`.
- `app.py` inclúe unha proba de reservas simultáneas para comprobar que non se venden máis prazas das dispoñibles, así como unha comparación de tempo entre consultas a PostgreSQL e Redis.

## Medicións

Nunha mostra de 100 consultas de dispoñibilidade observouse PostgreSQL arredor de 22 ms e Redis arredor de 0,4 ms. Son valores medidos nunha execución concreta e dependen do equipo e da carga.

## Consumo de recursos

Mostra puntual de `docker stats` dos contedores en execución:

| Contedor | CPU | Memoria usada / límite | Memoria % | Rede I/O | Disco I/O | PIDs |
|---|---:|---:|---:|---:|---:|---:|
| `p1_adminer` | 0,00 % | 9,32 MiB / 15,29 GiB | 0,06 % | 872 B / 126 B | 0 B / 0 B | 1 |
| `p1_postgres` | 0,03 % | 61,04 MiB / 15,29 GiB | 0,39 % | 2,12 kB / 126 B | 86,2 MB / 52,2 MB | 6 |
| `p1_redis` | 0,21 % | 10,52 MiB / 15,29 GiB | 0,07 % | 1,95 kB / 126 B | 34,6 MB / 8,19 kB | 6 |
| `p1_mongo` | 0,43 % | 397,6 MiB / 15,29 GiB | 2,54 % | 1,93 kB / 338 B | 357 MB / 528 kB | 49 |

O consumo pode variar segundo a carga e o tempo de execución dos servizos.

## Copias de seguridade e restauración

Desde a raíz do proxecto, crea unha copia de PostgreSQL e MongoDB con:

```bash
./src/copia.sh
```

Os ficheiros gárdanse en `copias/copia_<data>_<hora>/`: un `.sql` de PostgreSQL e un `.archive` de MongoDB.

Para comprobar a restauración nunha contorna de proba, elimináronse os datos das dúas bases:

```sql
-- PostgreSQL
DROP TABLE reservas, albergues, peregrinos CASCADE;
```

```javascript
// MongoDB, dentro de mongosh
db.fichas_albergues.drop()
```

Despois restauráronse os ficheiros xerados polo script:

```bash
docker exec -i -e PGPASSWORD=cambiame p1_postgres psql -U p1 -d albergues < copias/copia_XXXX/postgres_albergues.sql
docker exec -i p1_mongo mongorestore --username p1 --password cambiame --authenticationDatabase admin --archive < copias/copia_XXXX/mongo_albergues.archive
```

A restauración comprobouse coa aplicación e con consultas manuais. Substitúe `copia_XXXX` polo nome do cartafol real e adapta usuario, contrasinal e base de datos aos valores de `.env`. As ordes `DROP` eliminan datos: utilízaas só nunha proba controlada.

## Uso de ferramentas de IA

Durante o desenvolvemento utilizouse a asistencia de Gemini para identificar e resolver a incompatibilidade de MongoDB 8 co kernel de Linux (kernel 6.19 ou superior) mediante a variable `GLIBC_TUNABLES`, refinar a execución de `pg_dump` e `mongorestore` con `docker exec` para evitar problemas de permisos locais e estruturar os comandos da proba de restauración, así como información relevante.
