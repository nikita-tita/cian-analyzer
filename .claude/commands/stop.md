---
description: Stop all running services
---

# Stop Services

Stop all running Docker containers for the application.

This will:
1. Gracefully stop all containers
2. Preserve data in volumes
3. Keep images for quick restart

To completely remove containers and volumes, use docker-compose down -v
