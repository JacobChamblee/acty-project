# 🚀 Acty Labs Production Deployment Checklist

# CM3588 Server (192.168.68.121) + Backend Server (192.168.68.138)

## Pre-Deployment Preparation ✅

- [x] Build optimized React production bundle (`npm run build` in frontend/)
- [x] Test build locally with `serve -s build -l 3000`
- [x] Verify API endpoints work with production URLs
- [x] Update Caddyfile with production configuration
- [x] Prepare SSL certificates (Cloudflare Origin certificates)
- [x] Test docker-compose.prod.yml configuration

## SSL Certificate Setup 🔐

- [ ] Place SSL certificates on CM3588 server:
  - `/etc/ssl/certs/acty-labs.com.pem`
  - `/etc/ssl/private/acty-labs.com.key`
  - `/etc/ssl/certs/api.acty-labs.com.pem` (if separate)
  - `/etc/ssl/private/api.acty-labs.com.key` (if separate)
- [ ] Set correct permissions: `chmod 644` for certs, `chmod 600` for keys
- [ ] Verify certificate validity and chain

## Deployment Execution 📦

- [ ] Run deployment script: `./deploy_production.sh`
- [ ] Verify files copied to CM3588: `/home/pi/acty-site/build/`
- [ ] Confirm Caddyfile updated: `/etc/caddy/Caddyfile`
- [ ] Reload Caddy: `sudo systemctl reload caddy`
- [ ] Check Caddy service status: `sudo systemctl status caddy`

## Backend Services Setup ⚙️

- [ ] Ensure backend services running on 192.168.68.138:8765
- [ ] Verify PostgreSQL database connectivity
- [ ] Confirm Grafana and pgAdmin accessible
- [ ] Test API health endpoint: `http://192.168.68.138:8765/health`

## DNS and Domain Configuration 🌐

- [ ] Verify DNS A record: `acty-labs.com → 70.122.18.36`
- [ ] Confirm Cloudflare SSL/TLS settings
- [ ] Check www redirect: `www.acty-labs.com → acty-labs.com`
- [ ] Verify API subdomain: `api.acty-labs.com`

## End-to-End Testing 🧪

- [ ] Test main website: `https://acty-labs.com`
  - [ ] Page loads successfully
  - [ ] No mixed content warnings
  - [ ] All assets load (CSS, JS, images)
  - [ ] Navigation works correctly
- [ ] Test API endpoints: `https://api.acty-labs.com`
  - [ ] `/health` returns 200 OK
  - [ ] API calls work from frontend
  - [ ] CORS headers correct
- [ ] Test SSL certificates:
  - [ ] Valid certificate chain
  - [ ] No certificate errors
  - [ ] HSTS headers present
- [ ] Test security headers:
  - [ ] X-Frame-Options: DENY
  - [ ] X-XSS-Protection: 1; mode=block
  - [ ] Content-Security-Policy present
  - [ ] Strict-Transport-Security present

## Performance and Monitoring 📊

- [ ] Run monitoring script: `./monitor_production.sh`
- [ ] Check response times (< 2 seconds)
- [ ] Verify Caddy logs: `/var/log/caddy/acty-labs.log`
- [ ] Monitor backend service logs
- [ ] Set up log rotation and monitoring alerts
- [ ] Configure performance monitoring (Grafana)

## Post-Deployment Verification ✅

- [ ] Test all user flows end-to-end
- [ ] Verify data persistence (database operations)
- [ ] Test error handling and edge cases
- [ ] Confirm mobile responsiveness
- [ ] Validate accessibility compliance

## Rollback Plan (if needed) 🔄

- [ ] Keep previous Caddyfile backup
- [ ] Maintain previous build backup
- [ ] Document rollback commands:
  - `sudo cp /etc/caddy/Caddyfile.backup /etc/caddy/Caddyfile`
  - `sudo systemctl reload caddy`
  - `cp -r /home/pi/acty-site/build.backup/* /home/pi/acty-site/build/`

## Emergency Contacts 📞

- Server Admin: pi@192.168.68.121 (SSH)
- Backend Server: pi@192.168.68.138 (SSH)
- Domain Registrar: Cloudflare account
- SSL Certificate Provider: Cloudflare Origin CA

## Success Criteria 🎯

- [ ] Website loads in < 3 seconds
- [ ] All API calls successful
- [ ] SSL certificate valid (A+ rating)
- [ ] No console errors in browser
- [ ] All security headers present
- [ ] Monitoring and logging active
- [ ] User authentication works
- [ ] Data operations functional

---

**Deployment Command:** `./deploy_production.sh`
**Monitoring Command:** `./monitor_production.sh`
**Caddy Logs:** `ssh pi@192.168.68.121 'sudo journalctl -u caddy -f'`
