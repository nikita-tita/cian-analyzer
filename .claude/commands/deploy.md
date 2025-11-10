---
description: Deploy application to production using Docker
---

# Deploy Application

Deploy the Housler application using the automated deployment script.

## Options

Please select deployment mode:
1. **Development** - App + Redis only
2. **Production** - App + Redis + Nginx
3. **Full Stack** - App + Redis + Prometheus + Grafana

Execute the deployment by running the deploy script with the selected mode.

## Pre-deployment checks:
1. Ensure Docker and Docker Compose are installed
2. Verify .env file exists with proper configuration
3. Check that no other services are running on required ports
4. Backup any important data if needed

## Deployment steps:
1. Build Docker images
2. Start services with docker-compose
3. Wait for health checks to pass
4. Verify deployment success

After deployment, the application will be available at:
- Application: http://localhost:5000
- Health Check: http://localhost:5000/health
- Metrics: http://localhost:5000/metrics
