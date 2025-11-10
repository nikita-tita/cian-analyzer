---
description: Deploy to production housler.ru
---

Deploy the current branch to production server.

Steps:
1. Check for uncommitted changes
2. Push to GitHub
3. Pull on server
4. Update dependencies if needed
5. Restart service
6. Verify deployment

Run: `bash scripts/deploy.sh`
