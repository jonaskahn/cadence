# Cadence Production - Database Setup

This directory contains production-ready Docker Compose configuration for Cadence databases with security hardening, automated backups, and high availability considerations.

## ⚠️ Important Notice

**This configuration is intended for production use.** Please ensure:

1. All passwords are strong and unique
2. SSL/TLS certificates are properly configured
3. Firewall rules are in place
4. Backups are tested regularly
5. Monitoring and alerting are configured
6. Resource limits are adjusted for your workload

**For managed services**, consider using:
- AWS RDS (PostgreSQL), DocumentDB (MongoDB), ElastiCache (Redis)
- Azure Database for PostgreSQL, Cosmos DB, Azure Cache for Redis
- Google Cloud SQL, Cloud Firestore, Memorystore

---

## What's Included

### Databases (Latest Stable Versions - February 2026)
- **PostgreSQL 18.2** - Primary relational database with production optimizations
- **MongoDB 8.0.19** - Per-tenant conversation storage with TLS support
- **Redis 8.6** - Caching, pub/sub, and rate limiting with AOF persistence

### Backup Services
- **Automated PostgreSQL backups** - Daily dumps with 30-day retention
- **Automated MongoDB backups** - Daily dumps of all Cadence databases
- **Configurable schedules** - Via cron expressions

### Security Features
- TLS/SSL encryption for all database connections
- Strong password requirements
- Disabled dangerous commands (Redis)
- ACL support (Redis 6.0+)
- Connection limits and authentication
- No administrative UIs exposed (security by default)

---

## Quick Start

### 1. Prerequisites

```bash
# Ensure Docker and Docker Compose are installed
docker --version
docker-compose --version

# Create data directory
sudo mkdir -p /var/lib/cadence/{postgres,mongo,mongo-config,redis}
sudo chown -R $USER:$USER /var/lib/cadence
```

### 2. Configure Environment

```bash
cd devops/production

# Copy environment template
cp .env.example .env

# Edit .env with your strong passwords
nano .env

# ⚠️ IMPORTANT: Set strong passwords for:
# - POSTGRES_PASSWORD
# - MONGO_ROOT_PASSWORD
# - REDIS_PASSWORD
```

### 3. SSL/TLS Certificates

Generate self-signed certificates (for testing) or use your own:

```bash
# PostgreSQL
openssl req -new -x509 -days 365 -nodes \
    -text -out /var/lib/cadence/postgres/server.crt \
    -keyout /var/lib/cadence/postgres/server.key \
    -subj "/CN=cadence-postgres"

# MongoDB
cat /path/to/mongodb.crt /path/to/mongodb.key > /var/lib/cadence/mongo/mongodb.pem

# Redis
openssl req -new -x509 -days 365 -nodes \
    -out /var/lib/cadence/redis/redis.crt \
    -keyout /var/lib/cadence/redis/redis.key \
    -subj "/CN=cadence-redis"
```

### 4. Start Services

```bash
docker-compose -f database.yaml up -d
```

### 5. Verify Services

```bash
docker-compose -f database.yaml ps

# Check logs
docker-compose -f database.yaml logs -f
```

### 6. Initialize Databases

```bash
# PostgreSQL - Run migrations
docker exec -it cadence-postgres-prod psql -U cadence -d cadence < /path/to/schema.sql

# Or use Alembic from your application
cd ../../
poetry run alembic upgrade head
```

---

## Service Details

### PostgreSQL 18.2

**Latest Features:**
- Improved query performance
- Enhanced partitioning
- Better parallel query execution
- JSON improvements

**Production Configuration:**
- Shared buffers: 1GB (25% of RAM)
- Effective cache size: 3GB (75% of RAM)
- Max connections: 200
- Statement timeout: 30s
- Idle transaction timeout: 60s
- SSL enabled by default
- Slow query logging: > 1s
- Autovacuum optimized for production
- Parallel query workers: 8
- WAL compression enabled

**Connection:**
```bash
# Direct connection (SSL required)
psql "sslmode=require host=localhost port=5432 dbname=cadence user=cadence"

# Connection string for Cadence
postgresql+asyncpg://cadence:PASSWORD@localhost:5432/cadence?ssl=require
```

### MongoDB 8.0.19

**Latest Features:**
- Queryable Encryption improvements
- Time Series Collections enhancements
- Better aggregation performance
- Improved change streams

**Production Configuration:**
- WiredTiger cache: 2GB (50% of RAM)
- Max connections: 500
- TLS required for all connections
- Journal compression: snappy
- Slow query threshold: 1s
- Directory per database enabled
- Replica set ready (configuration required)

**Connection:**
```bash
# Direct connection (TLS required)
mongosh "mongodb://cadence:PASSWORD@localhost:27017/?tls=true&tlsCAFile=/path/to/ca.pem"

# Connection string for Cadence
mongodb://cadence:PASSWORD@localhost:27017/?tls=true
```

### Redis 8.6

**Latest Features:**
- Improved memory efficiency
- Better pub/sub performance
- Enhanced ACL system
- IO threading improvements

**Production Configuration:**
- Max memory: 2GB with LRU eviction
- Max clients: 10,000
- Persistence: AOF + RDB snapshots
- AOF fsync: everysec
- Dangerous commands disabled (FLUSHALL, FLUSHDB, KEYS)
- Active defragmentation enabled
- Lazy freeing enabled
- Slow log threshold: 10ms

**Connection:**
```bash
# Direct connection
redis-cli -h localhost -p 6379 -a PASSWORD --tls

# Connection string for Cadence
redis://:PASSWORD@localhost:6379/0
```

---

## Automated Backups

### PostgreSQL Backups

**Schedule:** Daily at 2:00 AM (configurable via `BACKUP_SCHEDULE`)

**Location:** `./backups/postgres/`

**Format:** Compressed SQL dump (`.sql.gz`)

**Retention:** 30 days (configurable via `BACKUP_RETENTION_DAYS`)

**Manual Backup:**
```bash
docker exec cadence-postgres-prod \
    pg_dump -U cadence cadence | gzip > backup_$(date +%Y%m%d).sql.gz
```

**Restore:**
```bash
gunzip -c backup_20260218.sql.gz | \
    docker exec -i cadence-postgres-prod psql -U cadence -d cadence
```

### MongoDB Backups

**Schedule:** Daily at 2:00 AM

**Location:** `./backups/mongo/`

**Format:** Compressed archive (`.tar.gz`) with mongodump

**Retention:** 30 days

**Manual Backup:**
```bash
docker exec cadence-mongo-prod \
    mongodump --username cadence --password PASSWORD \
    --out /tmp/backup --gzip

docker cp cadence-mongo-prod:/tmp/backup ./backup_$(date +%Y%m%d)
tar -czf backup_$(date +%Y%m%d).tar.gz backup_$(date +%Y%m%d)
```

**Restore:**
```bash
tar -xzf backup_20260218.tar.gz
docker cp backup_20260218 cadence-mongo-prod:/tmp/restore
docker exec cadence-mongo-prod \
    mongorestore --username cadence --password PASSWORD \
    /tmp/restore --gzip
```

### Redis Backups

Redis uses AOF (Append Only File) + RDB snapshots for persistence. Data is automatically persisted to `./backups/redis/`.

**Manual RDB snapshot:**
```bash
docker exec cadence-redis-prod redis-cli -a PASSWORD BGSAVE
docker cp cadence-redis-prod:/data/dump.rdb ./backup_$(date +%Y%m%d).rdb
```

---

## High Availability

### PostgreSQL Replication

To enable streaming replication:

1. **Primary Server** (`postgresql.conf`):
   ```conf
   wal_level = replica
   max_wal_senders = 10
   wal_keep_size = 1GB
   ```

2. **Replica Server** (`postgresql.conf`):
   ```conf
   hot_standby = on
   max_standby_streaming_delay = 30s
   ```

3. **Configure replication** (pg_hba.conf on primary):
   ```
   host replication cadence replica_ip/32 md5
   ```

4. **Start replica**:
   ```bash
   pg_basebackup -h primary_host -D /var/lib/postgresql/data -U cadence -P --wal-method=stream
   ```

### MongoDB Replica Set

To configure a replica set:

1. **Update `database.yaml`**:
   ```yaml
   command: mongod --config /etc/mongod.conf --replSet cadence-rs
   ```

2. **Initialize replica set**:
   ```javascript
   mongosh
   rs.initiate({
     _id: "cadence-rs",
     members: [
       { _id: 0, host: "mongo1:27017" },
       { _id: 1, host: "mongo2:27017" },
       { _id: 2, host: "mongo3:27017" }
     ]
   })
   ```

### Redis Sentinel

For Redis high availability:

1. **Deploy Redis Sentinel** (separate compose file)
2. **Configure Sentinel** to monitor master
3. **Update Cadence** connection string to use Sentinel

---

## Security Best Practices

### 1. Strong Passwords

```bash
# Generate strong passwords
openssl rand -base64 32

# Update .env file with generated passwords
```

### 2. Firewall Configuration

```bash
# Allow only application servers
sudo ufw allow from APP_SERVER_IP to any port 5432
sudo ufw allow from APP_SERVER_IP to any port 27017
sudo ufw allow from APP_SERVER_IP to any port 6379
```

### 3. SSL/TLS Enforcement

- Use valid certificates from a trusted CA
- Never use self-signed certificates in production
- Configure Cadence to use `sslmode=require` (PostgreSQL)
- Enable TLS verification in MongoDB and Redis clients

### 4. Regular Updates

```bash
# Update Docker images monthly
docker-compose -f database.yaml pull
docker-compose -f database.yaml up -d
```

### 5. Audit Logging

- Enable PostgreSQL audit extension (pg_audit)
- Enable MongoDB audit log (Enterprise edition)
- Monitor Redis slow log and command logs

---

## Monitoring

### Health Checks

All services have built-in health checks:

```bash
# Check all services
docker-compose -f database.yaml ps

# Individual health checks
docker exec cadence-postgres-prod pg_isready
docker exec cadence-mongo-prod mongosh --eval "db.adminCommand('ping')"
docker exec cadence-redis-prod redis-cli -a PASSWORD ping
```

### Metrics Collection

**Prometheus Exporters:**

```yaml
# Add to database.yaml
postgres-exporter:
  image: quay.io/prometheuscommunity/postgres-exporter:latest
  environment:
    DATA_SOURCE_NAME: "postgresql://cadence:PASSWORD@postgres:5432/cadence?sslmode=require"
  ports:
    - "9187:9187"

mongodb-exporter:
  image: percona/mongodb_exporter:latest
  environment:
    MONGODB_URI: "mongodb://cadence:PASSWORD@mongo:27017"
  ports:
    - "9216:9216"

redis-exporter:
  image: oliver006/redis_exporter:latest
  environment:
    REDIS_ADDR: "redis:6379"
    REDIS_PASSWORD: "${REDIS_PASSWORD}"
  ports:
    - "9121:9121"
```

### Log Aggregation

Forward logs to centralized logging:

```yaml
logging:
  driver: "syslog"
  options:
    syslog-address: "tcp://logstash:5000"
    tag: "cadence-postgres"
```

---

## Resource Tuning

### For 8 GB RAM System

```bash
# PostgreSQL
POSTGRES_SHARED_BUFFERS=2GB
POSTGRES_EFFECTIVE_CACHE_SIZE=6GB

# MongoDB
MONGO_CACHE_SIZE_GB=4

# Redis
REDIS_MAX_MEMORY=2gb
```

### For 16 GB RAM System

```bash
# PostgreSQL
POSTGRES_SHARED_BUFFERS=4GB
POSTGRES_EFFECTIVE_CACHE_SIZE=12GB

# MongoDB
MONGO_CACHE_SIZE_GB=8

# Redis
REDIS_MAX_MEMORY=4gb
```

### For 32 GB RAM System

```bash
# PostgreSQL
POSTGRES_SHARED_BUFFERS=8GB
POSTGRES_EFFECTIVE_CACHE_SIZE=24GB

# MongoDB
MONGO_CACHE_SIZE_GB=16

# Redis
REDIS_MAX_MEMORY=8gb
```

---

## Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check logs
docker logs cadence-postgres-prod

# Test connection
docker exec -it cadence-postgres-prod psql -U cadence -d cadence

# Check SSL configuration
docker exec cadence-postgres-prod ls -la /var/lib/postgresql/*.{crt,key}
```

### MongoDB Authentication Errors

```bash
# Check logs
docker logs cadence-mongo-prod

# Test connection
docker exec -it cadence-mongo-prod mongosh -u cadence -p PASSWORD

# Check TLS configuration
docker exec cadence-mongo-prod ls -la /etc/ssl/mongodb/
```

### Redis Memory Issues

```bash
# Check memory usage
docker exec cadence-redis-prod redis-cli -a PASSWORD INFO memory

# Check eviction stats
docker exec cadence-redis-prod redis-cli -a PASSWORD INFO stats | grep evicted
```

### Backup Failures

```bash
# Check backup logs
cat ./backups/postgres/postgres_backup.log
cat ./backups/mongo/mongo_backup.log

# Test backup script manually
docker exec cadence-postgres-backup-prod /backup.sh
```

---

## Migration from Local to Production

1. **Backup local data:**
   ```bash
   cd ../local
   docker-compose -f database.yaml exec postgres pg_dump -U cadence cadence_dev > local_backup.sql
   ```

2. **Restore to production:**
   ```bash
   cd ../production
   cat local_backup.sql | docker exec -i cadence-postgres-prod psql -U cadence -d cadence
   ```

3. **Update connection strings** in Cadence `.env` file

4. **Run migrations** if schema changes are needed

---

## Disaster Recovery

### Full System Recovery

1. **Stop all services:**
   ```bash
   docker-compose -f database.yaml down
   ```

2. **Restore data volumes:**
   ```bash
   # PostgreSQL
   sudo rm -rf /var/lib/cadence/postgres/*
   sudo tar -xzf postgres_backup.tar.gz -C /var/lib/cadence/postgres/

   # MongoDB
   sudo rm -rf /var/lib/cadence/mongo/*
   sudo tar -xzf mongo_backup.tar.gz -C /var/lib/cadence/mongo/

   # Redis
   sudo cp redis_backup/dump.rdb /var/lib/cadence/redis/
   ```

3. **Restart services:**
   ```bash
   docker-compose -f database.yaml up -d
   ```

4. **Verify data integrity:**
   ```bash
   docker-compose -f database.yaml logs -f
   ```

---

## Cost Optimization

### Managed Services Comparison

| Service | Self-Hosted (EC2) | AWS Managed | Azure Managed | GCP Managed |
|---------|-------------------|-------------|---------------|-------------|
| PostgreSQL | $50-100/mo | $200-400/mo (RDS) | $180-350/mo | $170-340/mo |
| MongoDB | $50-100/mo | $250-500/mo (DocumentDB) | $220-450/mo (Cosmos) | $200-420/mo |
| Redis | $30-60/mo | $150-300/mo (ElastiCache) | $140-280/mo | $130-270/mo |
| **Total** | **$130-260/mo** | **$600-1200/mo** | **$540-1080/mo** | **$500-1030/mo** |

**Recommendation:** Use managed services for production unless you have dedicated DevOps resources.

---

## Support

For production issues:

1. Check logs: `docker-compose -f database.yaml logs -f`
2. Verify health: `docker-compose -f database.yaml ps`
3. Consult troubleshooting section
4. Review main Cadence documentation
5. Contact support: support@your-company.com

---

## Sources

- [PostgreSQL 18.2 Release](https://www.postgresql.org/about/news/postgresql-181-177-1611-1515-1420-and-1323-released-3171/)
- [MongoDB 8.0 Release](https://www.mongodb.com/docs/manual/release-notes/8.0/)
- [Redis 8.6 Downloads](https://redis.io/downloads/)

---

**Cadence Production Databases** - Secure, reliable, and production-ready.
