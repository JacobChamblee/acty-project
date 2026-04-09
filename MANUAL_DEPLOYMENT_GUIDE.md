# 🚀 Acty Labs Production Deployment Guide

# Manual Deployment to CM3588 Server (192.168.68.121)

## Current Status ✅

- ✅ Website: https://acty-labs.com (responding with 200 OK)
- ✅ SSL: Valid certificates for both acty-labs.com and api.acty-labs.com
- ✅ API: https://api.acty-labs.com/health (responding with 200 OK)
- ✅ Backend: Direct API access working (192.168.68.138:8765)

## Manual Deployment Steps

### Step 1: Prepare Files Locally

```bash
# Ensure you're in the acty-project directory
cd /home/jacob/acty-project

# Verify build exists
ls -la frontend/build/
```

### Step 2: Copy Files to CM3588 Server

```bash
# SSH to CM3588 server
ssh pi@192.168.68.121

# Create directory structure
mkdir -p /home/pi/acty-site/build

# Exit SSH and copy files
exit
scp -r frontend/build/* pi@192.168.68.121:/home/pi/acty-site/build/
```

### Step 3: Update Caddy Configuration

```bash
# Copy the updated Caddyfile
scp Caddyfile pi@192.168.68.121:/tmp/Caddyfile.new

# SSH to server and update Caddyfile
ssh pi@192.168.68.121
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup
sudo cp /tmp/Caddyfile.new /etc/caddy/Caddyfile
```

### Step 4: Configure SSL Certificates

```bash
# On CM3588 server, ensure SSL certificates are in place
sudo mkdir -p /etc/ssl/certs /etc/ssl/private

# Copy certificates (replace with actual paths)
# sudo cp /path/to/acty-labs.com.pem /etc/ssl/certs/
# sudo cp /path/to/acty-labs.com.key /etc/ssl/private/

# Set permissions
sudo chmod 644 /etc/ssl/certs/acty-labs.com.pem
sudo chmod 600 /etc/ssl/private/acty-labs.com.key
```

### Step 5: Reload Caddy

```bash
# Reload Caddy configuration
sudo systemctl reload caddy

# Check status
sudo systemctl status caddy
```

### Step 6: Verify Deployment

```bash
# Test website
curl -I https://acty-labs.com

# Test API
curl -I https://api.acty-labs.com/health

# Check logs
sudo tail -f /var/log/caddy/acty-labs.log
```

## File Locations Summary

### Local Files (Development Machine)

- `frontend/build/` - React production build
- `Caddyfile` - Updated production Caddyfile
- `docker-compose.prod.yml` - Production Docker Compose

### Remote Files (CM3588 Server)

- `/home/pi/acty-site/build/` - Static files location
- `/etc/caddy/Caddyfile` - Caddy configuration
- `/etc/ssl/certs/acty-labs.com.pem` - SSL certificate
- `/etc/ssl/private/acty-labs.com.key` - SSL private key
- `/var/log/caddy/acty-labs.log` - Access logs

## Key Configuration Details

### Caddyfile Features

- Static file serving with SPA routing
- API proxy to backend server (192.168.68.138:8765)
- SSL/TLS with custom certificates
- Security headers (HSTS, XSS protection, etc.)
- Gzip compression
- Static asset caching

### SSL Configuration

- Uses Cloudflare Origin certificates
- Supports both acty-labs.com and api.acty-labs.com
- Automatic HTTP to HTTPS redirects
- www to non-www redirects

### Network Architecture

- CM3588 (192.168.68.121): Web server (Caddy)
- Backend Server (192.168.68.138): API services (FastAPI)
- External IP: 70.122.18.36 (Cloudflare)

## Troubleshooting

### Common Issues

1. **SSL Certificate Errors**: Check certificate paths and permissions
2. **502 Bad Gateway**: Backend server not responding
3. **404 Errors**: Static files not copied correctly
4. **Permission Denied**: Check file ownership and permissions

### Log Locations

- Caddy logs: `/var/log/caddy/acty-labs.log`
- System logs: `journalctl -u caddy`
- API logs: Check backend server logs

### Rollback Commands

```bash
# Restore previous Caddyfile
sudo cp /etc/caddy/Caddyfile.backup /etc/caddy/Caddyfile
sudo systemctl reload caddy

# Restore previous build
cp -r /home/pi/acty-site/build.backup/* /home/pi/acty-site/build/
```

## Post-Deployment Testing

### Automated Testing

```bash
# Run the monitoring script (requires SSH setup)
./monitor_production.sh
```

### Manual Testing Checklist

- [ ] Website loads: https://acty-labs.com
- [ ] API health: https://api.acty-labs.com/health
- [ ] SSL valid: Check in browser dev tools
- [ ] No console errors
- [ ] All assets load (CSS, JS, images)
- [ ] Navigation works
- [ ] Mobile responsive

## Success Metrics

- Response time < 3 seconds
- SSL Labs rating A+ or A
- All security headers present
- No JavaScript errors
- API calls successful
- Database operations work

---

**Ready for deployment!** The production configuration is prepared and tested locally. Execute the manual steps above to complete the deployment to CM3588.
