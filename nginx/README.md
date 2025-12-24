# Nginx Configuration

## Production (housler.ru)

Production nginx config is managed directly on the server at:
`/etc/nginx/sites-enabled/housler.ru`

Features:
- HTTPS with Let's Encrypt (auto-renewal via certbot)
- HTTP to HTTPS redirect
- www to non-www redirect
- Security headers (HSTS, X-Frame-Options, CSP, etc.)
- Gzip compression
- Static file caching

## Local Development

The `nginx.conf` in this directory is for local Docker development only.
It is NOT used in production.

For production changes, SSH to server and edit:
```bash
ssh -i ~/.ssh/id_housler root@91.229.8.221
nano /etc/nginx/sites-enabled/housler.ru
nginx -t && systemctl reload nginx
```

## SSL Certificate Renewal

Certbot is configured for auto-renewal. Manual renewal:
```bash
certbot renew --dry-run
```
