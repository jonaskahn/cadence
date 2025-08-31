# Production Deployment

This guide covers deploying Cadence in production environments with considerations for security, scalability, and
reliability.

## Production Checklist

Before deploying to production, ensure you have:

- [ ] **Environment Configuration** properly set
- [ ] **API Keys** securely configured
- [ ] **Plugin Validation** enabled
- [ ] **Monitoring** and logging configured
- [ ] **Backup Strategy** implemented
- [ ] **Security Measures** in place
- [ ] **Performance Testing** completed
- [ ] **Disaster Recovery** plan ready

## Deployment Options

### 1. Docker Deployment (Recommended)

The most reliable and scalable deployment method:

```yaml
# docker-compose.prod.yml
version: "3.8"

services:
  cadence:
    build: .
    image: cadence:latest
    container_name: cadence-prod
    restart: unless-stopped
    ports:
      - "8000:8000"
    environment:
      - CADENCE_APP_NAME=Cadence 🤖 Multi-agents AI Framework
      - CADENCE_DEBUG=false
      - CADENCE_DEFAULT_LLM_PROVIDER=openai
      - CADENCE_OPENAI_API_KEY=${OPENAI_API_KEY}
      - CADENCE_PLUGINS_DIR=/opt/cadence/plugins
      - CADENCE_API_HOST=0.0.0.0
      - CADENCE_API_PORT=8000
      - CADENCE_REDIS_URL=redis://redis:6379/0
      - CADENCE_SESSION_TIMEOUT=3600
      - CADENCE_MAX_AGENT_HOPS=25
      - CADENCE_MAX_TOOL_HOPS=50
    volumes:
      - ./plugins:/opt/cadence/plugins:ro
      - cadence-logs:/var/log/cadence
    depends_on:
      - redis
    networks:
      - cadence-network

  redis:
    image: redis:7-alpine
    container_name: cadence-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
      - ./redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: redis-server /usr/local/etc/redis/redis.conf
    networks:
      - cadence-network

  nginx:
    image: nginx:alpine
    container_name: cadence-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      - cadence-logs:/var/log/nginx
    depends_on:
      - cadence
    networks:
      - cadence-network

volumes:
  cadence-logs:
  redis-data:

networks:
  cadence-network:
    driver: bridge
```

### 2. Kubernetes Deployment

For container orchestration environments:

```yaml
# k8s/cadence-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cadence
  labels:
    app: cadence
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cadence
  template:
    metadata:
      labels:
        app: cadence
    spec:
      containers:
        - name: cadence
          image: cadence:latest
          ports:
            - containerPort: 8000
          env:
            - name: CADENCE_APP_NAME
              value: "Cadence 🤖 Multi-agents AI Framework"
            - name: CADENCE_DEBUG
              value: "false"
            - name: CADENCE_DEFAULT_LLM_PROVIDER
              value: "openai"
            - name: CADENCE_OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: cadence-secrets
                  key: openai-api-key
            - name: CADENCE_PLUGINS_DIR
              value: "/opt/cadence/plugins"
            - name: CADENCE_API_HOST
              value: "0.0.0.0"
            - name: CADENCE_API_PORT
              value: "8000"
            - name: CADENCE_REDIS_URL
              value: "redis://cadence-redis:6379/0"
          volumeMounts:
            - name: plugins
              mountPath: /opt/cadence/plugins
              readOnly: true
            - name: logs
              mountPath: /var/log/cadence
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "2Gi"
              cpu: "1000m"
          livenessProbe:
            httpGet:
              path: /api/v1/health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/v1/status
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
      volumes:
        - name: plugins
          persistentVolumeClaim:
            claimName: cadence-plugins-pvc
        - name: logs
          emptyDir: {}
```

### 3. Traditional Server Deployment

For VPS or bare metal servers:

```bash
#!/bin/bash
# deploy.sh

# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3.13 python3.13-venv python3.13-pip nginx redis-server

# Create application user
sudo useradd -r -s /bin/false cadence

# Create application directory
sudo mkdir -p /opt/cadence
sudo chown cadence:cadence /opt/cadence

# Clone repository
sudo -u cadence git clone https://github.com/jonaskahn/cadence.git /opt/cadence/app

# Create virtual environment
sudo -u cadence python3.13 -m venv /opt/cadence/venv

# Install dependencies
sudo -u cadence /opt/cadence/venv/bin/pip install -r /opt/cadence/app/requirements.txt

# Create systemd service
sudo tee /etc/systemd/system/cadence.service > /dev/null <<EOF
[Unit]
Description=Cadence 🤖 Multi-agents AI Framework
After=network.target redis.service

[Service]
Type=simple
User=cadence
Group=cadence
WorkingDirectory=/opt/cadence/app
Environment=PATH=/opt/cadence/venv/bin
ExecStart=/opt/cadence/venv/bin/python -m cadence
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable cadence redis
sudo systemctl start redis cadence

# Configure Nginx
sudo tee /etc/nginx/sites-available/cadence > /dev/null <<EOF
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/cadence /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## Security Configuration

### 1. SSL/TLS Setup

```nginx
# nginx.conf with SSL
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

### 2. Firewall Configuration

```bash
# UFW firewall setup
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 3. API Key Security

```bash
# Use environment variables (never hardcode)
export CADENCE_OPENAI_API_KEY="your-secure-key"

# Or use Docker secrets
echo "your-secure-key" | docker secret create openai-api-key -

# Or use Kubernetes secrets
kubectl create secret generic cadence-secrets \
  --from-literal=openai-api-key="your-secure-key"
```

## Monitoring and Observability

### 1. Health Checks

```python
# Custom health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "plugins": len(plugin_manager.get_available_plugins()),
        "memory_usage": psutil.virtual_memory().percent,
        "cpu_usage": psutil.cpu_percent()
    }
```

### 2. Logging Configuration

```python
# logging.conf
[loggers]
cadence = INFO
cadence.plugins = INFO
cadence.api = INFO

[handlers]
console = StreamHandler
file = FileHandler

[formatters]
detailed = Formatter
```

### 3. Metrics Collection

```python
# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

request_count = Counter('cadence_requests_total', 'Total requests')
request_duration = Histogram('cadence_request_duration_seconds', 'Request duration')
active_connections = Gauge('cadence_active_connections', 'Active connections')
```

## Performance Optimization

### 1. Caching Strategy

```python
# Redis caching configuration
CADENCE_REDIS_URL = redis://localhost:6379/0
CADENCE_CACHE_TTL = 3600
CADENCE_SESSION_CACHE_TTL = 7200
```

### 2. Connection Pooling

```python
# Database connection pooling
CADENCE_DB_POOL_SIZE = 20
CADENCE_DB_MAX_OVERFLOW = 30
CADENCE_DB_POOL_TIMEOUT = 30
```

### 3. Resource Limits

```python
# Memory and CPU limits
CADENCE_MAX_MEMORY_USAGE = 2048  # MB
CADENCE_MAX_CPU_USAGE = 80  # Percentage
CADENCE_MAX_CONCURRENT_REQUESTS = 100
```

## Backup and Recovery

### 1. Data Backup Strategy

```bash
#!/bin/bash
# backup.sh

# Backup Redis data
redis-cli BGSAVE
cp /var/lib/redis/dump.rdb /backup/redis-$(date +%Y%m%d).rdb

# Backup plugin configurations
tar -czf /backup/plugins-$(date +%Y%m%d).tar.gz /opt/cadence/plugins

# Backup logs
tar -czf /backup/logs-$(date +%Y%m%d).tar.gz /var/log/cadence

# Cleanup old backups (keep 30 days)
find /backup -name "*.rdb" -mtime +30 -delete
find /backup -name "*.tar.gz" -mtime +30 -delete
```

### 2. Disaster Recovery Plan

```bash
#!/bin/bash
# restore.sh

# Restore Redis data
cp /backup/redis-$(date +%Y%m%d).rdb /var/lib/redis/dump.rdb
sudo systemctl restart redis

# Restore plugins
tar -xzf /backup/plugins-$(date +%Y%m%d).tar.gz -C /

# Restart Cadence service
sudo systemctl restart cadence
```

## Testing and Validation

### 1. Load Testing

```bash
# Install Apache Bench
sudo apt install apache2-utils

# Run load test
ab -n 1000 -c 10 http://localhost:8000/api/v1/status

# Install wrk for more advanced testing
sudo apt install wrk

# Run stress test
wrk -t12 -c400 -d30s http://localhost:8000/api/v1/status
```

### 2. Health Monitoring

```bash
# Monitor system resources
htop
iotop
nethogs

# Monitor application logs
tail -f /var/log/cadence/cadence.log
journalctl -u cadence -f

# Monitor API endpoints
curl -f http://localhost:8000/api/v1/health
```

## Scaling Strategies

### 1. Horizontal Scaling

```yaml
# Kubernetes HPA
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: cadence-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: cadence
  minReplicas: 3
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### 2. Load Balancing

```nginx
# Nginx load balancer
upstream cadence_backend {
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
    server 127.0.0.1:8003;
}

server {
    location / {
        proxy_pass http://cadence_backend;
    }
}
```

## Troubleshooting

### Common Production Issues

**High Memory Usage:**

```bash
# Check memory usage
ps aux --sort=-%mem | head -10

# Check for memory leaks
valgrind --tool=memcheck python -m cadence.main
```

**Slow Response Times:**

```bash
# Check database performance
redis-cli --latency

# Check network latency
ping your-domain.com

# Profile application
python -m cProfile -o profile.stats cadence/main.py
```

**Plugin Failures:**

```bash
# Check plugin logs
tail -f /var/log/cadence/plugins.log

# Validate plugin structure
python -c "from cadence_sdk.utils import validate_plugin_structure; print('Valid')"
```

## Next Steps

- **[Environment Configuration](environment.md)** - Configuration management
