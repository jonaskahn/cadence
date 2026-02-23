# Cadence DevOps

DevOps configurations and scripts for deploying Cadence databases and infrastructure.

---

## Directory Structure

```
devops/
├── local/              # Local development setup
│   ├── database.yaml   # Docker Compose for all databases
│   ├── config/         # Database configurations
│   ├── init-scripts/   # Initialization scripts
│   └── README.md       # Local setup documentation
│
└── production/         # Production deployment
    ├── database.yaml   # Production Docker Compose
    ├── config/         # Production configurations
    ├── scripts/        # Backup and maintenance scripts
    ├── backups/        # Backup storage
    ├── .env.example    # Environment template
    └── README.md       # Production documentation
```

---

## Quick Links

### [Local Development →](./local/README.md)
Set up databases for local development:
- PostgreSQL 18.2
- MongoDB 8.0.19
- Redis 8.6
- Admin UIs (pgAdmin, Mongo Express, Redis Commander)

**Start local stack:**
```bash
cd local
docker-compose -f database.yaml up -d
```

### [Production Deployment →](./production/README.md)
Production-ready database configuration with:
- SSL/TLS encryption
- Automated backups
- Resource optimization
- Security hardening

**Start production stack:**
```bash
cd production
cp .env.example .env
# Edit .env with strong passwords
docker-compose -f database.yaml up -d
```

---

## Latest Database Versions (February 2026)

| Database | Version | Released | Notes |
|----------|---------|----------|-------|
| **PostgreSQL** | 18.2 | Feb 12, 2026 | [Release Notes](https://www.postgresql.org/about/news/postgresql-181-177-1611-1515-1420-and-1323-released-3171/) |
| **MongoDB** | 8.0.19 | Feb 2026 | [Release Notes](https://www.mongodb.com/docs/manual/release-notes/8.0/) |
| **Redis** | 8.6 | Feb 8, 2026 | [Downloads](https://redis.io/downloads/) |

---

## Choosing Your Setup

### Use **Local** if:
- ✅ You're developing Cadence
- ✅ You need admin UIs for debugging
- ✅ You want simple setup with default passwords
- ✅ Data loss is acceptable

### Use **Production** if:
- ✅ You're deploying to production
- ✅ You need SSL/TLS encryption
- ✅ You need automated backups
- ✅ You need security hardening
- ✅ You need resource optimization

---

## Connection Strings

### Local (Development)
```bash
# PostgreSQL
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:cadence_dev_password@localhost:5432/cadence_dev

# MongoDB
CADENCE_MONGO_URL=mongodb://cadence:cadence_dev_password@localhost:27017/

# Redis
CADENCE_REDIS_URL=redis://:cadence_dev_password@localhost:6379/0
```

### Production
```bash
# PostgreSQL (SSL required)
CADENCE_POSTGRES_URL=postgresql+asyncpg://cadence:${POSTGRES_PASSWORD}@localhost:5432/cadence?ssl=require

# MongoDB (TLS required)
CADENCE_MONGO_URL=mongodb://cadence:${MONGO_ROOT_PASSWORD}@localhost:27017/?tls=true

# Redis (TLS recommended)
CADENCE_REDIS_URL=redis://:${REDIS_PASSWORD}@localhost:6379/0
```

---

## Common Commands

### Start Services
```bash
# Local
cd local && docker-compose -f database.yaml up -d

# Production
cd production && docker-compose -f database.yaml up -d
```

### Stop Services
```bash
docker-compose -f database.yaml down
```

### View Logs
```bash
docker-compose -f database.yaml logs -f
```

### Check Status
```bash
docker-compose -f database.yaml ps
```

### Run Migrations
```bash
# From cadence root directory
poetry run alembic upgrade head
```

---

## Resource Requirements

### Local Development

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| PostgreSQL | ~5% | ~50 MB | 100 MB |
| MongoDB | ~5% | ~100 MB | 200 MB |
| Redis | ~2% | ~50 MB | 50 MB |
| Admin UIs | ~6% | ~200 MB | 70 MB |
| **Total** | **~18%** | **~400 MB** | **~420 MB** |

### Production

| Component | CPU | Memory | Disk |
|-----------|-----|--------|------|
| PostgreSQL | 1-2 cores | 2-4 GB | 10-100 GB |
| MongoDB | 1-2 cores | 2-4 GB | 10-500 GB |
| Redis | 0.5-1 core | 1-2 GB | 1-10 GB |
| Backups | 0.5 core | 512 MB | 2x data size |
| **Total** | **3-5 cores** | **5-10 GB** | **Variable** |

---

## Backup & Recovery

### Local (No Automated Backups)

Manual backup:
```bash
cd local

# PostgreSQL
docker exec cadence-postgres-local pg_dump -U cadence cadence_dev > backup.sql

# MongoDB
docker exec cadence-mongo-local mongodump -u cadence -p cadence_dev_password -o /tmp/backup
docker cp cadence-mongo-local:/tmp/backup ./mongo-backup
```

### Production (Automated Daily Backups)

Backups run automatically at 2 AM daily. See [production README](./production/README.md#automated-backups) for details.

---

## Security

### Local Development

- Default passwords (DO NOT use in production)
- No SSL/TLS (plain text connections)
- Admin UIs exposed (port 5050, 8081, 8082)
- No firewall restrictions

### Production

- Strong passwords required
- SSL/TLS enforced
- No admin UIs exposed
- Firewall rules required
- Regular security updates
- Audit logging enabled

---

## Troubleshooting

### Port Conflicts

If ports are already in use:

1. **Check what's using the port:**
   ```bash
   lsof -i :5432
   lsof -i :27017
   lsof -i :6379
   ```

2. **Change ports in `database.yaml`:**
   ```yaml
   ports:
     - "15432:5432"  # Changed from 5432
   ```

3. **Update connection strings accordingly**

### Container Won't Start

```bash
# Check logs for errors
docker-compose -f database.yaml logs <service-name>

# Remove and recreate
docker-compose -f database.yaml down
docker-compose -f database.yaml up -d
```

### Data Corruption

```bash
# Stop services
docker-compose -f database.yaml down

# Restore from backup
# (see backup/recovery section)

# Start services
docker-compose -f database.yaml up -d
```

---

## Migration Guides

### Local → Production

See [Production README - Migration Section](./production/README.md#migration-from-local-to-production)

### Managed Services → Self-Hosted

1. Export data from managed service
2. Configure production environment
3. Import data to self-hosted databases
4. Update connection strings
5. Test thoroughly before switching

### Self-Hosted → Managed Services

Consider managed services for:
- Automatic backups
- High availability
- Managed updates
- Scaling capabilities
- Professional support

---

## Monitoring

### Local (Built-in Health Checks)

```bash
# Check all services
docker-compose -f database.yaml ps
```

### Production (Prometheus + Grafana)

Add exporters to collect metrics:
- postgres-exporter (port 9187)
- mongodb-exporter (port 9216)
- redis-exporter (port 9121)

See [Production README - Monitoring](./production/README.md#monitoring)

---

## Performance Tuning

### PostgreSQL

Adjust based on workload:
- **OLTP** (many short queries): Lower `work_mem`, higher `shared_buffers`
- **OLAP** (few long queries): Higher `work_mem`, enable parallel queries

### MongoDB

- Use indexes for all queries
- Enable sharding for large datasets
- Configure appropriate cache size

### Redis

- Use appropriate eviction policy
- Enable persistence based on data durability needs
- Consider Redis Cluster for scaling

---

## Support

### Documentation
- [Local Setup Guide](./local/README.md)
- [Production Deployment Guide](./production/README.md)
- [Main Cadence Documentation](../../README.md)

### Issues
- Check logs first: `docker-compose -f database.yaml logs -f`
- Verify health: `docker-compose -f database.yaml ps`
- Search existing issues
- Create new issue with logs attached

---

## Contributing

When adding new database configurations:

1. Update both `local/` and `production/` directories
2. Add documentation to relevant READMEs
3. Test thoroughly in both environments
4. Update this root README with any new sections

---

## License

See [LICENSE](../../LICENSE) file.

---

**Cadence DevOps** - Infrastructure made simple.
