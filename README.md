# SmartDrive API 🚀

**Crawlerless REST API deployment for SmartDrive semantic search**

This is a production-ready MCPO-based REST API that connects to **existing** Pinecone + Azure Blob Storage indexes. Perfect for deploying on Open WebUI servers or any production environment where you want to expose SmartDrive as a standard HTTP API.

---

## 🎯 What This Is

- **100% API-only**: No crawler, no indexing, no OneDrive access
- **MCPO-based**: Exposes your MCP server as OpenAPI/REST endpoints
- **Lightweight**: ~500MB Docker image vs 2GB+ with crawler dependencies
- **Production-ready**: Health checks, logging, authentication, auto-restart

---

## ⚡ Quick Start

### Prerequisites

1. **Existing indexes** (created on a different machine):
   - Pinecone index with your document vectors
   - Azure Blob Storage container with full document texts
2. **Docker** and **docker-compose** installed
3. **Credentials** for Pinecone and Azure Blob Storage

### Setup

1. **Clone this repo** (or copy these files to your server)

2. **Create `.env` file**:
   ```bash
   cp .env.api.example .env
   nano .env  # Edit with your credentials
   ```

3. **Set required variables**:
   ```env
   # API Authentication
   MCPO_API_KEY=your_secret_api_key_here

   # Pinecone (existing index)
   PINECONE_API_KEY=your_pinecone_api_key
   PINECONE_INDEX_NAME=smartdrive
   PINECONE_HOST=smartdrive-xxxxx.svc.aped-xxxx-xxxx.pinecone.io

   # Azure Blob Storage (existing container)
   AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
   AZURE_STORAGE_CONTAINER_NAME=documents

   # Embedding Provider (MUST match indexing!)
   EMBEDDING_PROVIDER=local
   EMBEDDING_MODEL=all-MiniLM-L6-v2
   ```

4. **Build and run**:
   ```bash
   docker-compose -f docker-compose.api.yml up -d
   ```

5. **Test the API**:
   ```bash
   # Check health
   curl http://localhost:8000/health

   # View interactive docs
   open http://localhost:8000/docs

   # Search OneDrive
   curl -X POST http://localhost:8000/tools/search_onedrive \
     -H "Authorization: Bearer your_secret_api_key_here" \
     -H "Content-Type: application/json" \
     -d '{"query": "tax forms", "top_k": 5}'
   ```

---

## 📡 API Endpoints

### Base URL
```
http://localhost:8000
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check (no auth required) |
| GET | `/docs` | Interactive Swagger UI |
| GET | `/openapi.json` | OpenAPI schema |
| POST | `/tools/search_onedrive` | Hybrid semantic + keyword search |
| POST | `/tools/read_document` | Retrieve full document by doc_id |

### Authentication

All tool endpoints require Bearer token authentication:
```bash
Authorization: Bearer your_secret_api_key_here
```

---

## 🔍 API Usage Examples

### Search OneDrive

**Request**:
```bash
curl -X POST http://localhost:8000/tools/search_onedrive \
  -H "Authorization: Bearer your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "tax forms 2024",
    "top_k": 5
  }'
```

**Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "🔍 Found 5 results for: 'tax forms 2024'\n\n**Result 1** (Score: 0.892)...",
      "annotations": null
    }
  ],
  "isError": false
}
```

### Read Full Document

**Request**:
```bash
curl -X POST http://localhost:8000/tools/read_document \
  -H "Authorization: Bearer your_secret_api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "doc_abc123def456"
  }'
```

**Response**:
```json
{
  "content": [
    {
      "type": "text",
      "text": "📄 **Document ID:** doc_abc123def456\n📊 **Size:** 15,234 characters\n\n**Full Text:**\n..."
    }
  ],
  "isError": false
}
```

---

## 🐳 Docker Commands

```bash
# Build and start
docker-compose -f docker-compose.api.yml up -d

# View logs
docker-compose -f docker-compose.api.yml logs -f

# Restart
docker-compose -f docker-compose.api.yml restart

# Stop
docker-compose -f docker-compose.api.yml down

# Rebuild after changes
docker-compose -f docker-compose.api.yml build --no-cache
docker-compose -f docker-compose.api.yml up -d

# Check status
docker-compose -f docker-compose.api.yml ps
```

---

## 🔧 Configuration

### Embedding Provider Matching

**CRITICAL**: Your API embedding provider **MUST match** what you used during indexing!

| Indexing Used | API Config |
|---------------|------------|
| Local (all-MiniLM-L6-v2) | `EMBEDDING_PROVIDER=local`<br>`EMBEDDING_MODEL=all-MiniLM-L6-v2` |
| Voyage AI (voyage-3-large) | `EMBEDDING_PROVIDER=voyage`<br>`VOYAGE_API_KEY=...`<br>`VOYAGE_MODEL=voyage-3-large` |
| Pinecone Inference | `EMBEDDING_PROVIDER=pinecone`<br>`EMBEDDING_MODEL=llama-text-embed-v2` |
| Custom API | `EMBEDDING_PROVIDER=api`<br>`EMBEDDING_API_URL=...`<br>`EMBEDDING_API_KEY=...` |

### Resource Limits

Adjust in [docker-compose.api.yml](docker-compose.api.yml:34-42):

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 2G
    reservations:
      cpus: '0.5'
      memory: 512M
```

### Port Configuration

Change port 8000 to something else:

```yaml
ports:
  - "9000:8000"  # Host:Container
```

---

## 🌐 Integration with Open WebUI

1. **Deploy SmartDrive API** on your server:
   ```bash
   docker-compose -f docker-compose.api.yml up -d
   ```

2. **Add to Open WebUI** as an OpenAPI server:
   - Go to Open WebUI → Settings → Functions
   - Add OpenAPI server:
     - **URL**: `http://your-server-ip:8000`
     - **API Key**: Your `MCPO_API_KEY` value
   - Save and test

3. **Use in Open WebUI**:
   - Ask: "Search my OneDrive for tax documents"
   - Open WebUI will call your SmartDrive API automatically

---

## 🔒 Security Best Practices

1. **Change default API key**:
   ```env
   MCPO_API_KEY=$(openssl rand -hex 32)
   ```

2. **Use HTTPS in production**:
   - Add reverse proxy (Nginx/Traefik)
   - Get SSL certificate (Let's Encrypt)

3. **Restrict network access**:
   - Firewall rules
   - Docker network isolation
   - VPN/private network only

4. **Rotate credentials regularly**:
   - API keys
   - Pinecone API keys
   - Azure Storage keys

---

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Should return HTTP 200 OK.

### Logs

```bash
# Live logs
docker-compose -f docker-compose.api.yml logs -f

# Last 100 lines
docker-compose -f docker-compose.api.yml logs --tail=100

# Specific service logs
docker logs smartdrive-api -f
```

### Resource Usage

```bash
# Check container stats
docker stats smartdrive-api

# Check disk usage
docker system df
```

---

## 🐛 Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose -f docker-compose.api.yml logs

# Common issues:
# - Missing .env file
# - Invalid Pinecone/Azure credentials
# - Port 8000 already in use
```

### Authentication errors

```bash
# Verify API key is set
docker-compose -f docker-compose.api.yml exec smartdrive-api env | grep MCPO_API_KEY

# Check request header:
# Authorization: Bearer your_secret_api_key_here
```

### Search returns no results

**Possible causes**:
1. **Empty index**: No documents indexed yet
2. **Wrong embedding provider**: Must match indexing config
3. **Dimension mismatch**: Check Pinecone index dimensions vs embedding model

```bash
# Check Pinecone connection
docker-compose -f docker-compose.api.yml exec smartdrive-api python -c "
from pinecone import Pinecone
import os
pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
index = pc.Index(os.getenv('PINECONE_INDEX_NAME'), host=os.getenv('PINECONE_HOST'))
print(index.describe_index_stats())
"
```

### Azure Blob Storage errors

```bash
# Test connection
docker-compose -f docker-compose.api.yml exec smartdrive-api python -c "
from azure.storage.blob import BlobServiceClient
import os
client = BlobServiceClient.from_connection_string(os.getenv('AZURE_STORAGE_CONNECTION_STRING'))
container = client.get_container_client(os.getenv('AZURE_STORAGE_CONTAINER_NAME'))
print('Container exists:', container.exists())
"
```

---

## 📁 File Structure

```
smartdrive-api/
├── Dockerfile.api              # API-optimized Dockerfile
├── docker-compose.api.yml      # API-specific compose config
├── requirements-api.txt        # Minimal dependencies (no crawler)
├── .env.api.example           # API-only environment template
├── README.API.md              # This file
│
├── smartdrive_server.py       # MCP server (core)
├── embeddings.py              # Query embedding encoding
├── config.py                  # Configuration management
├── document_storage.py        # Azure Blob Storage interface
│
└── (crawler files not included in Docker image)
```

---

## 🚀 Performance

**Benchmarks** (typical production workload):

- **Memory**: 200-500MB idle, 1-1.5GB peak during searches
- **CPU**: <5% idle, 20-50% during embedding encoding
- **Startup time**: 5-10 seconds
- **Search latency**:
  - Pinecone query: 50-200ms
  - Azure Blob fetch: 50-100ms
  - Embedding encode: 100-500ms (local) / 200-800ms (API)
  - **Total**: 200ms - 1.6s per search

**Scaling**:
- Single container handles 10-50 concurrent requests
- For high traffic, deploy multiple containers behind load balancer

---

## 💰 Cost Estimate

**Monthly costs** (typical production):

| Service | Cost |
|---------|------|
| Pinecone Serverless | ~$0.03/month (100K vectors) |
| Azure Blob Storage | ~$0.02/month (1GB) |
| Azure Compute (VM) | $5-20/month (depends on size) |
| Voyage AI queries | ~$0.10-1.00/month (if used) |
| **Total** | **$5-25/month** |

---

## 🤝 Support

- **GitHub Issues**: [Your repo issues](https://github.com/yourusername/smartdrive-api/issues)
- **Documentation**: See [README.md](README.md) for full SmartDrive docs
- **Original MCP Server**: [SmartDrive MCP](https://github.com/1818TusculumSt/smartdrive-mcp)

---

## 📄 License

MIT License - Same as SmartDrive MCP

---

**Built with**:
- [MCPO](https://github.com/open-webui/mcpo) - MCP-to-OpenAPI proxy
- [MCP](https://modelcontextprotocol.io/) - Model Context Protocol by Anthropic
- [Pinecone](https://www.pinecone.io/) - Vector database
- [Azure Blob Storage](https://azure.microsoft.com/en-us/services/storage/blobs/) - Document storage
