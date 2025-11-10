---
description: Deploy to production housler.ru or locally with Docker
---

# Deploy Application

Deploy the Housler application to production or locally.

## Production Deployment (housler.ru)

Deploy current branch to production server:

```bash
bash scripts/deploy.sh
```

**What it does:**
1. Checks for uncommitted changes
2. Pushes to GitHub
3. Pulls on production server
4. Updates dependencies if needed
5. Restarts service
6. Verifies deployment
7. Shows recent logs

## Local Docker Deployment

For local development/testing with Docker:

```bash
bash scripts/auto-deploy.sh 1  # Development
bash scripts/auto-deploy.sh 2  # Production mode
bash scripts/auto-deploy.sh 3  # Full Stack with monitoring
```

**Deployment modes:**
1. **Development** - App + Redis only
2. **Production** - App + Redis + Nginx
3. **Full Stack** - App + Redis + Prometheus + Grafana

**Pre-deployment checks:**
- Docker and Docker Compose installed
- .env file exists with proper configuration
- No services running on required ports
- Backup if needed

**After deployment:**
- Application: http://localhost:5000
- Health Check: http://localhost:5000/health
- Metrics: http://localhost:5000/metrics

## Documentation

- Production setup: [PRODUCTION_SETUP.md](../PRODUCTION_SETUP.md)
- Local deployment: [CLAUDE_CODE_DEPLOY.md](../CLAUDE_CODE_DEPLOY.md)
- Quick guide: [QUICK_DEPLOY_GUIDE.md](../QUICK_DEPLOY_GUIDE.md)
