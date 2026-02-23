# Cadence DevOps

Infrastructure configurations for local development and production deployment.

---

## Directory Structure

```
devops/
├── local/              # Local development
│   ├── database.yaml   # Docker Compose (all databases + admin UIs)
│   ├── config/         # Database configurations
│   ├── init-scripts/   # Initialization scripts
│   └── README.md
│
└── production/         # Production deployment
    ├── database.yaml   # Production Docker Compose (SSL, backups)
    ├── config/
    ├── scripts/        # Backup and maintenance scripts
    ├── .env.example
    └── README.md
```

---

## Quick Start

### Local Development

```bash
cd local
docker-compose -f database.yaml up -d
```

Includes: PostgreSQL, MongoDB, Redis, RabbitMQ, MinIO, and admin UIs (pgAdmin, Mongo Express, Redis Commander).

### Production

```bash
cd production
cp .env.example .env
# Edit .env with strong passwords
docker-compose -f database.yaml up -d
```

See [production/README.md](./production/README.md) for SSL, backup, and hardening details.

---

## Connection Strings

### Local

```bash
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:cadence_dev_password@localhost:5432/cadence_dev
CADENCE_MONGO_URL=mongodb://cadence:cadence_dev_password@localhost:27017/
CADENCE_REDIS_URL=redis://:cadence_dev_password@localhost:6379/0
```

### Production

```bash
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:${POSTGRES_PASSWORD}@localhost:5432/cadence?ssl=require
CADENCE_MONGO_URL=mongodb://cadence:${MONGO_ROOT_PASSWORD}@localhost:27017/?tls=true
CADENCE_REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
```

---

## Common Commands

```bash
# Start / stop
docker-compose -f database.yaml up -d
docker-compose -f database.yaml down

# Logs / status
docker-compose -f database.yaml logs -f
docker-compose -f database.yaml ps

# Run migrations (from cadence root)
poetry run alembic upgrade head
```

---

## Troubleshooting

**Port conflict** — check what's using the port and change `ports:` in `database.yaml` accordingly:

```bash
lsof -i :5432   # PostgreSQL
lsof -i :27017  # MongoDB
lsof -i :6379   # Redis
```

**Container won't start** — check logs:

```bash
docker-compose -f database.yaml logs <service-name>
```

---

## License

See [LICENSE](../../LICENSE).
