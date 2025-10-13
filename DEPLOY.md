# SmartDrive API - Deployment Guide 🚀

**Step-by-step guide to deploy SmartDrive API on your production server**

---

## 📋 Prerequisites

Before you begin, ensure you have:

1. ✅ **Existing Pinecone index** with your document vectors (created on a different machine)
2. ✅ **Azure Blob Storage container** with full document texts
3. ✅ **Docker** and **docker-compose** installed on your server
4. ✅ **Credentials** for Pinecone and Azure Blob Storage
5. ✅ **Open port 8000** (or your chosen port)

---

## 🚀 Deployment Steps

### Step 1: Copy Files to Server

Copy these files to your server:

```bash
# Required files for API-only deployment
smartdrive-api/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .dockerignore
├── smartdrive_server.py
├── embeddings.py
├── config.py
└── document_storage.py
```

**Using SCP**:
```bash
scp -r smartdrive-api/ user@your-server:/opt/
```

**Using Git**:
```bash
ssh user@your-server
cd /opt
git clone https://github.com/yourusername/smartdrive-api.git
cd smartdrive-api
```

---

### Step 2: Create Configuration

1. **Copy the example env file**:
   ```bash
   cd /opt/smartdrive-api
   cp .env.example .env
   ```

2. **Edit `.env` with your credentials**:
   ```bash
   nano .env
   ```

3. **Set these REQUIRED variables**:
   ```env
   # API Key (generate a strong random key)
   MCPO_API_KEY=your_secret_api_key_here

   # Pinecone (from https://www.pinecone.io/)
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_INDEX_NAME=smartdrive
   PINECONE_HOST=smartdrive-xxxxx.svc.aped-xxxx-xxxx.pinecone.io

   # Azure Blob Storage (from Azure Portal)
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
   AZURE_STORAGE_CONTAINER_NAME=documents

   # Embedding Provider (MUST match what you used during indexing!)
   EMBEDDING_PROVIDER=local
   EMBEDDING_MODEL=all-MiniLM-L6-v2
   ```

4. **Generate a strong API key** (optional but recommended):
   ```bash
   openssl rand -hex 32
   # Copy output to MCPO_API_KEY in .env
   ```

---

### Step 3: Build and Start

1. **Build the Docker image**:
   ```bash
   docker-compose build
   ```

2. **Start the service**:
   ```bash
   docker-compose up -d
   ```

3. **Check the logs**:
   ```bash
   docker-compose logs -f
   ```

   You should see:
   ```
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:8000
   ```

---

### Step 4: Verify Deployment

1. **Health check**:
   ```bash
   curl http://localhost:8000/health
   ```
   Expected: HTTP 200 OK

2. **View API documentation**:
   - Open browser: `http://your-server-ip:8000/docs`
   - You should see Swagger UI with your tools

3. **Test search** (replace API key):
   ```bash
   curl -X POST http://localhost:8000/tools/search_onedrive \
     -H "Authorization: Bearer your_secret_api_key_here" \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "top_k": 3}'
   ```

---

### Step 5: Configure Firewall (Optional but Recommended)

**Allow port 8000** (or your chosen port):

**UFW (Ubuntu)**:
```bash
sudo ufw allow 8000/tcp
sudo ufw reload
```

**Firewalld (CentOS/RHEL)**:
```bash
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

---

### Step 6: Set Up Reverse Proxy (Production)

For production, use Nginx or Traefik with SSL:

**Nginx example** (`/etc/nginx/sites-available/smartdrive-api`):
```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and restart:
```bash
sudo ln -s /etc/nginx/sites-available/smartdrive-api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Add SSL with Certbot**:
```bash
sudo certbot --nginx -d api.yourdomain.com
```

---

## 🔧 Configuration Options

### Change Port

Edit [docker-compose.yml](docker-compose.yml):
```yaml
ports:
  - "9000:8000"  # Change 9000 to your desired port
```

### Adjust Resources

Edit [docker-compose.yml](docker-compose.yml):
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Increase for more performance
      memory: 4G       # Increase for more concurrent requests
```

### Enable Debug Logging

Add to `.env`:
```env
LOG_LEVEL=DEBUG
```

---

## 🔄 Maintenance

### View Logs
```bash
docker-compose logs -f
```

### Restart Service
```bash
docker-compose restart
```

### Update Deployment
```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose build
docker-compose up -d
```

### Backup Configuration
```bash
# Backup .env file
cp .env .env.backup.$(date +%Y%m%d)
```

### Clean Up Old Images
```bash
docker system prune -a
```

---

## 🌐 Integration with Open WebUI

### Option 1: Same Server (Recommended)

If Open WebUI is on the same server:

1. **Add to Open WebUI**:
   - Go to Settings → Functions → Add OpenAPI Server
   - **URL**: `http://localhost:8000`
   - **API Key**: Your `MCPO_API_KEY`

2. **Test**:
   - Ask Open WebUI: "Search my OneDrive for tax documents"

### Option 2: Different Server

If Open WebUI is on a different server:

1. **Ensure firewall allows access** from Open WebUI server
2. **Use full URL**: `http://your-smartdrive-server-ip:8000`
3. **Consider VPN** or private network for security

### Option 3: HTTPS/Domain (Production)

Set up Nginx with SSL (see Step 6 above), then:
- **URL**: `https://api.yourdomain.com`
- **API Key**: Your `MCPO_API_KEY`

---

## 🐛 Troubleshooting

### Container won't start

**Check logs**:
```bash
docker-compose logs
```

**Common issues**:
- Missing `.env` file → Copy from `.env.example`
- Invalid credentials → Double-check Pinecone/Azure credentials
- Port conflict → Change port in `docker-compose.yml`

### Can't connect from external server

1. **Check firewall**:
   ```bash
   sudo ufw status
   ```

2. **Check container is running**:
   ```bash
   docker ps | grep smartdrive-api
   ```

3. **Test from server itself first**:
   ```bash
   curl http://localhost:8000/health
   ```

### Search returns empty results

**Check Pinecone connection**:
```bash
docker-compose exec smartdrive-api python -c "
from pinecone import Pinecone
import os
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index(os.getenv('PINECONE_INDEX_NAME'), host=os.getenv('PINECONE_HOST'))
stats = index.describe_index_stats()
print('Total vectors:', stats['total_vector_count'])
print('Namespaces:', stats['namespaces'])
"
```

Expected output shows your vector count > 0.

### Authentication errors

**Verify API key**:
```bash
docker-compose exec smartdrive-api env | grep MCPO_API_KEY
```

**Test with correct header**:
```bash
curl -X POST http://localhost:8000/tools/search_onedrive \
  -H "Authorization: Bearer your_actual_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "top_k": 3}'
```

---

## 📊 Monitoring

### Check Container Status
```bash
docker-compose ps
```

### Resource Usage
```bash
docker stats smartdrive-api
```

### Disk Usage
```bash
docker system df
```

### View Health Check
```bash
docker inspect smartdrive-api | grep -A 10 Health
```

---

## 🔒 Security Checklist

- [ ] Changed default `MCPO_API_KEY` to strong random value
- [ ] Using HTTPS with valid SSL certificate (production)
- [ ] Firewall configured to restrict access
- [ ] `.env` file has restricted permissions (`chmod 600 .env`)
- [ ] Regular credential rotation scheduled
- [ ] Monitoring and logging enabled
- [ ] Backups of configuration files

---

## 💰 Cost Estimates

**Monthly operational costs**:

| Component | Cost |
|-----------|------|
| Server (2GB RAM, 1 CPU) | $5-10/month |
| Pinecone Serverless | ~$0.03/month (100K vectors) |
| Azure Blob Storage | ~$0.02/month (1GB) |
| **Total** | **$5-15/month** |

---

## 📞 Support

- **Issues**: Open a GitHub issue
- **Docs**: See [README.md](README.md)
- **Original Project**: [SmartDrive MCP](https://github.com/1818TusculumSt/smartdrive-mcp)

---

**You're all set! 🎉**

Your SmartDrive API is now deployed and ready to serve search requests from Open WebUI or any HTTP client.
