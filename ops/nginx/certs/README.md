# Reverse Proxy TLS Certificates

When running `docker-compose.proxy.yml`, Nginx expects TLS assets at:

- `ops/nginx/certs/tls.crt`
- `ops/nginx/certs/tls.key`

Use valid production certificates on real environments.
Do not commit private keys or real certificates to git.

For local testing only, you can generate a temporary self-signed pair:

```bash
mkdir -p ops/nginx/certs
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout ops/nginx/certs/tls.key \
  -out ops/nginx/certs/tls.crt \
  -days 365 \
  -subj "/CN=localhost"
```
