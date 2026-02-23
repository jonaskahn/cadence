# Cadence Scripts

Utility scripts for development, operations, and administration.

---

## Scripts

### `setup-dev.sh` — Full dev environment setup

Checks prerequisites, creates `.env`, starts Docker services, installs
dependencies, and runs migrations. Run once when setting up a new machine.

```bash
./scripts/setup-dev.sh
# or
make setup
```

---

### `docker.sh` — Docker service management

Wraps `docker compose` for the local database stack
(`devops/local/database.yaml`). Supports v2 plugin (`docker compose`) with
automatic fallback to legacy `docker-compose`.

```bash
./scripts/docker.sh start           # start all services
./scripts/docker.sh stop            # stop all services
./scripts/docker.sh restart         # restart all services
./scripts/docker.sh status          # show container status
./scripts/docker.sh logs            # tail all logs
./scripts/docker.sh logs postgres   # tail logs for one service
./scripts/docker.sh reset           # stop + delete volumes (destructive)
```

Services: `postgres`, `mongo`, `redis`, `minio`, `pgadmin`,
`mongo-express`, `redis-commander`.

---

### `bootstrap.py` — First-run admin setup

Creates a `sys_admin` user (not bound to any organization), connects to Redis
to issue an initial session token, and prints the credentials and ready-to-use
JWT to stdout. Run once after a fresh database init.

```bash
poetry run python scripts/bootstrap.py

# Custom values
poetry run python scripts/bootstrap.py \
    --username alice \
    --email alice@acme.com \
    --password s3cr3t

# Add another sys_admin to an existing installation (skips schema creation)
poetry run python scripts/bootstrap.py --add-sys-admin --username bob
```

| Flag              | Default           | Description                              |
|-------------------|-------------------|------------------------------------------|
| `--user-id`       | random UUID       | Admin user ID                            |
| `--username`      | `admin`           | Admin username                           |
| `--email`         | `admin@localhost` | Admin email                              |
| `--password`      | auto-generated    | Admin password (printed if auto)         |
| `--force`         | off               | Skip confirmation prompts                |
| `--add-sys-admin` | off               | Create extra sys_admin, skip schema init |

The printed token is used directly as a `Bearer` token. It is valid for
`CADENCE_ACCESS_TOKEN_EXPIRE_MINUTES` (default 30 min). To get a fresh token
after expiry use `POST /api/auth/login` with the same credentials.

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/orgs
```

> **Note:** `sys_admin` users have no org membership by default. Use the
> Admin UI or `POST /api/admin/orgs` to create organizations, then
> `POST /api/orgs/{org_id}/members` to add users to them.

---

### `generate_openapi.py` — Export OpenAPI schema

Loads the FastAPI app and writes `openapi_schema.json` (excluded from git).

```bash
poetry run python scripts/generate_openapi.py
poetry run python scripts/generate_openapi.py --output docs/openapi.json
poetry run python scripts/generate_openapi.py --compact   # no indentation
```

---

### `init_db.py` — Create database tables

Creates all PostgreSQL tables directly from SQLAlchemy models. Useful when
Alembic is not set up or as a quick schema reset.

```bash
poetry run python scripts/init_db.py
```

---

## Makefile shortcuts

| Command          | Script                                          |
|------------------|-------------------------------------------------|
| `make setup`     | `./scripts/setup-dev.sh`                        |
| `make db-up`     | `./scripts/docker.sh start`                     |
| `make db-down`   | `./scripts/docker.sh stop`                      |
| `make db-logs`   | `./scripts/docker.sh logs`                      |
| `make db-clean`  | `./scripts/docker.sh reset`                     |
| `make bootstrap` | `poetry run python scripts/bootstrap.py`        |
| `make openapi`   | `poetry run python scripts/generate_openapi.py` |

---

## Troubleshooting

**Permission denied on shell scripts:**

```bash
chmod +x scripts/*.sh
```

**Import errors in Python scripts:**

```bash
poetry install          # install dependencies
poetry shell            # activate environment
```

**Database connection refused:**

```bash
./scripts/docker.sh status    # check containers are running
./scripts/docker.sh start     # start if stopped
```

**Bootstrap token expired:**

```bash
# Get a new token via the API (Redis must be running)
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "<your-password>"}'
```
