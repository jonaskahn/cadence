# Cadence Local Development - Database Setup

This directory contains Docker Compose configuration for running all Cadence databases locally.

## What's Included

### Databases
- **PostgreSQL 18.2** - Primary relational database (latest stable)
- **MongoDB 8.0.19** - Per-tenant conversation storage (latest stable)
- **Redis 8.6** - Caching, pub/sub, and rate limiting (latest GA)
- **MinIO** - S3-compatible object storage for plugin packages (source of truth)

### Admin UIs
- **pgAdmin 8.3** - PostgreSQL management (http://localhost:5050)
- **Mongo Express 1.0.2** - MongoDB management (http://localhost:8081)
- **Redis Commander** - Redis management (http://localhost:8082)
- **MinIO Console** - Object storage management (http://localhost:9001)

---

## Quick Start

### 1. Start All Databases

```bash
cd devops/local
docker-compose -f database.yaml up -d
```

### 2. Verify All Services Running

```bash
docker-compose -f database.yaml ps
```

Expected output:
```
NAME                              STATUS    PORTS
cadence-postgres-local            healthy   0.0.0.0:5432->5432/tcp
cadence-mongo-local               healthy   0.0.0.0:27017->27017/tcp
cadence-redis-local               healthy   0.0.0.0:6379->6379/tcp
cadence-minio-local               healthy   0.0.0.0:9000->9000/tcp, 0.0.0.0:9001->9001/tcp
cadence-pgadmin-local             running   0.0.0.0:5050->80/tcp
cadence-mongo-express-local       running   0.0.0.0:8081->8081/tcp
cadence-redis-commander-local     running   0.0.0.0:8082->8081/tcp
```

### 3. Configure Cadence Application

Add these connection strings to your `.env` file:

```bash
# Database connections
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:cadence_dev_password@localhost:5432/cadence_dev
CADENCE_MONGO_URL=mongodb://cadence:cadence_dev_password@localhost:27017/
CADENCE_REDIS_URL=redis://:cadence_dev_password@localhost:6379/0

# S3 / MinIO (plugin object storage)
CADENCE_S3_ENDPOINT_URL=http://localhost:9000
CADENCE_S3_ACCESS_KEY_ID=cadence
CADENCE_S3_SECRET_ACCESS_KEY=cadence_dev_password
CADENCE_S3_BUCKET_NAME=cadence-plugins
CADENCE_PLUGIN_S3_ENABLED=true
```

### 4. Run Migrations

```bash
cd ../../  # Back to cadence root
poetry run alembic upgrade head
```

---

## Service Details

### PostgreSQL

**Connection Details:**
- Host: `localhost`
- Port: `5432`
- Database: `cadence_dev`
- Username: `cadence`
- Password: `cadence_dev_password`

**Extensions Installed:**
- `uuid-ossp` - UUID generation
- `pgcrypto` - Encryption functions
- `hstore` - Key-value storage

**Direct Connection:**
```bash
psql -h localhost -U cadence -d cadence_dev
# Password: cadence_dev_password
```

### MongoDB

**Connection Details:**
- Host: `localhost`
- Port: `27017`
- Root Username: `cadence`
- Root Password: `cadence_dev_password`

**Sample Database:**
- `cadence_sample_org` - Pre-configured with collections and indexes

**Direct Connection:**
```bash
mongosh "mongodb://cadence:cadence_dev_password@localhost:27017/"
```

### Redis

**Connection Details:**
- Host: `localhost`
- Port: `6379`
- Password: `cadence_dev_password`
- Databases: `0-15` (default: 0 for cache, 1 for rate limiting)

**Memory Limit:** 512 MB with LRU eviction

**Direct Connection:**
```bash
redis-cli -a cadence_dev_password
```

---

## Admin UIs

### pgAdmin (PostgreSQL)

- **URL**: http://localhost:5050
- **Email**: `admin@cadence.local`
- **Password**: `admin`

The PostgreSQL server is pre-configured and will appear in the UI automatically.

### Mongo Express (MongoDB)

- **URL**: http://localhost:8081
- **Username**: `admin`
- **Password**: `admin`

### Redis Commander

- **URL**: http://localhost:8082
- **Username**: `admin`
- **Password**: `admin`

### MinIO Console (Object Storage)

- **URL**: http://localhost:9001
- **Username**: `cadence`
- **Password**: `cadence_dev_password`

The `cadence-plugins` bucket is created automatically on startup by the `minio-init` container.

---

## Common Commands

### Start Services
```bash
docker-compose -f database.yaml up -d
```

### Stop Services
```bash
docker-compose -f database.yaml down
```

### Stop and Remove Volumes (⚠️ Deletes all data)
```bash
docker-compose -f database.yaml down -v
```

### View Logs
```bash
# All services
docker-compose -f database.yaml logs -f

# Specific service
docker-compose -f database.yaml logs -f postgres
docker-compose -f database.yaml logs -f mongo
docker-compose -f database.yaml logs -f redis
```

### Restart Service
```bash
docker-compose -f database.yaml restart postgres
```

### Check Health Status
```bash
docker-compose -f database.yaml ps
```

---

## Troubleshooting

### Port Already in Use

If ports are already in use, you can change them in `database.yaml`:

```yaml
services:
  postgres:
    ports:
      - "5433:5432"  # Changed from 5432
```

### Connection Refused

1. **Check service is healthy:**
   ```bash
   docker-compose -f database.yaml ps
   ```

2. **Check logs for errors:**
   ```bash
   docker-compose -f database.yaml logs postgres
   ```

3. **Restart service:**
   ```bash
   docker-compose -f database.yaml restart postgres
   ```

### Reset Everything

To completely reset (⚠️ **deletes all data**):

```bash
docker-compose -f database.yaml down -v
docker volume prune -f
docker-compose -f database.yaml up -d
```

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is accepting connections
docker exec -it cadence-postgres-local pg_isready -U cadence

# Connect directly
docker exec -it cadence-postgres-local psql -U cadence -d cadence_dev
```

### MongoDB Connection Issues

```bash
# Check if MongoDB is running
docker exec -it cadence-mongo-local mongosh --eval "db.adminCommand('ping')"

# Connect directly
docker exec -it cadence-mongo-local mongosh -u cadence -p cadence_dev_password
```

### Redis Connection Issues

```bash
# Check if Redis is running
docker exec -it cadence-redis-local redis-cli -a cadence_dev_password ping

# Connect directly
docker exec -it cadence-redis-local redis-cli -a cadence_dev_password
```

### MinIO Connection Issues

```bash
# Check if MinIO is healthy
docker exec -it cadence-minio-local mc ready local

# List buckets
docker exec -it cadence-minio-local mc ls local/

# Re-run bucket initialization manually
docker-compose -f database.yaml run --rm minio-init
```

---

## Data Persistence

Data is persisted in named Docker volumes:

- `cadence-postgres-data-local` - PostgreSQL data
- `cadence-mongo-data-local` - MongoDB data
- `cadence-mongo-config-local` - MongoDB config
- `cadence-redis-data-local` - Redis data
- `cadence-pgadmin-data-local` - pgAdmin settings
- `cadence-minio-data-local` - MinIO object storage (plugin packages)

**To inspect volumes:**
```bash
docker volume ls | grep cadence
docker volume inspect cadence-postgres-data-local
```

**To backup data:**
```bash
# PostgreSQL
docker exec cadence-postgres-local pg_dump -U cadence cadence_dev > backup.sql

# MongoDB
docker exec cadence-mongo-local mongodump --username cadence --password cadence_dev_password --out /tmp/backup
docker cp cadence-mongo-local:/tmp/backup ./mongo-backup

# Redis
docker exec cadence-redis-local redis-cli -a cadence_dev_password --rdb /data/dump.rdb SAVE
docker cp cadence-redis-local:/data/dump.rdb ./redis-backup.rdb
```

---

## Resource Usage

Approximate resource consumption:

| Service | CPU | Memory | Disk |
|---------|-----|--------|------|
| PostgreSQL | ~5% | ~50 MB | 100 MB |
| MongoDB | ~5% | ~100 MB | 200 MB |
| Redis | ~2% | ~50 MB | 50 MB |
| MinIO | ~2% | ~50 MB | varies |
| pgAdmin | ~2% | ~100 MB | 50 MB |
| Mongo Express | ~2% | ~50 MB | 10 MB |
| Redis Commander | ~2% | ~50 MB | 10 MB |
| **Total** | **~20%** | **~450 MB** | **~420 MB+** |

---

## Network

All services run on a dedicated Docker network: `cadence-network-local`

Services can communicate using hostnames:
- PostgreSQL: `postgres:5432`
- MongoDB: `mongo:27017`
- Redis: `redis:6379`
- MinIO: `minio:9000`

---

## Production Differences

This local setup differs from production:

| Feature | Local | Production |
|---------|-------|------------|
| Passwords | Simple | Strong, rotated |
| Persistence | Docker volumes | External volumes/services |
| Backups | Manual | Automated |
| SSL/TLS | Disabled | Enabled |
| Replication | None | High availability |
| Monitoring | Basic | Full observability |
| Resources | Minimal | Scaled as needed |

See `../production/` for production configurations.

---

## Next Steps

1. ✅ Start databases: `docker-compose -f database.yaml up -d`
2. ✅ Configure `.env` file with connection strings
3. ✅ Run Alembic migrations: `poetry run alembic upgrade head`
4. ✅ Start Cadence API: `poetry run uvicorn cadence.main:app --reload`
5. ✅ Access admin UIs to verify data

---

## Support

If you encounter issues:

1. Check logs: `docker-compose -f database.yaml logs -f`
2. Verify health: `docker-compose -f database.yaml ps`
3. Consult troubleshooting section above
4. Check main Cadence documentation: `../../README.md`
