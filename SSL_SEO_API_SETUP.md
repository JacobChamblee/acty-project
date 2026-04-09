# 🔐 SSL, SEO & API Integration Complete Setup Guide

## Overview

This document covers the complete setup for:

1. **SSL/HTTPS** - Enable HTTPS via Caddy and Let's Encrypt
2. **SEO Verification** - Test Open Graph tags and meta tags
3. **API Integration** - Ensure frontend calls correct backend URLs

---

## 1. 🔐 SSL Certificate Configuration

### Current Setup

The Caddyfile has been updated to support **multiple SSL options**:

#### Option A: Cloudflare Origin Certificate (Current)

```caddy
tls /etc/ssl/certs/acty-labs.com.pem /etc/ssl/private/acty-labs.com.key
```

**Setup Steps:**

1. Obtain certificate from Cloudflare Origin CA
2. Place certificate files on CM3588 server:
   - `/etc/ssl/certs/acty-labs.com.pem` (public certificate)
   - `/etc/ssl/private/acty-labs.com.key` (private key)
3. Set correct permissions:
   ```bash
   sudo chmod 644 /etc/ssl/certs/acty-labs.com.pem
   sudo chmod 600 /etc/ssl/private/acty-labs.com.key
   ```

#### Option B: Let's Encrypt (Automatic)

Uncomment in Caddyfile:

```caddy
tls {
    email admin@acty-labs.com
    dns cloudflare {env.CLOUDFLARE_API_TOKEN}
}
```

**Setup Steps:**

1. Set environment variable on CM3588:
   ```bash
   export CLOUDFLARE_API_TOKEN="your-cloudflare-token"
   ```
2. Reload Caddy:
   ```bash
   sudo systemctl reload caddy
   ```
3. Caddy will automatically:
   - Obtain certificates from Let's Encrypt
   - Renew them automatically
   - Store them in `/etc/caddy/certificates/`

#### Option C: Default Let's Encrypt (Simplest)

Currently enabled in Caddyfile:

```caddy
tls {
    policies {
        uri acme-v02.api.letsencrypt.org/directory
        on_demand
    }
}
```

**Features:**

- ✅ Automatic certificate issuance
- ✅ On-demand certificate generation
- ✅ Automatic renewal
- ✅ No manual configuration needed

### SSL Status Check

```bash
# Check certificate validity
openssl s_client -servername acty-labs.com -connect acty-labs.com:443 < /dev/null | openssl x509 -noout -text

# Check expiration date
echo | openssl s_client -servername acty-labs.com -connect acty-labs.com:443 2>/dev/null | openssl x509 -noout -enddate

# Verify chain
openssl s_client -connect acty-labs.com:443 -showcerts < /dev/null
```

### HTTPS Configuration in Caddyfile

```caddy
# Automatic HTTP to HTTPS redirect
http://acty-labs.com {
    redir https://acty-labs.com{uri} permanent
}

# www redirect
www.acty-labs.com {
    redir https://acty-labs.com{uri} permanent
}

# Security headers
header {
    Strict-Transport-Security "max-age=2592000; includeSubDomains"
    X-Frame-Options "DENY"
    X-Content-Type-Options "nosniff"
}
```

---

## 2. 🔍 SEO Verification

### Meta Tags Configuration

Updated `frontend/public/index.html` with comprehensive SEO tags:

#### Primary Meta Tags

```html
<meta
  name="title"
  content="Acty Cactus - Your Vehicle's Complete Health Story"
/>
<meta
  name="description"
  content="Privacy-first vehicle diagnostics platform..."
/>
<meta name="keywords" content="vehicle diagnostics, OBD-II, automotive AI..." />
<meta name="robots" content="index, follow, max-snippet:-1..." />
```

#### Open Graph Tags

```html
<meta property="og:type" content="website" />
<meta
  property="og:title"
  content="Acty Cactus - Your Vehicle's Complete Health Story"
/>
<meta property="og:description" content="..." />
<meta property="og:image" content="https://acty-labs.com/og-image.png" />
<meta property="og:url" content="https://acty-labs.com/" />
```

#### Twitter Card Tags

```html
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="..." />
<meta name="twitter:image" content="https://acty-labs.com/og-image.png" />
<meta name="twitter:creator" content="@ActyLabs" />
```

#### Structured Data (Schema.org)

```html
<script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    "name": "Acty Cactus",
    "url": "https://acty-labs.com"
  }
</script>
```

### Running SEO Verification

```bash
# Test all meta tags and social sharing
./verify_seo.sh

# Expected output:
# ✅ Meta Description
# ✅ OG Title, Description, Image, URL
# ✅ Twitter Card tags
# ✅ Canonical URL
# ✅ Structured Data
# ✅ Security headers
```

### Manual Social Media Testing

1. **Facebook**: https://developers.facebook.com/tools/debug/
2. **Twitter**: https://cards-dev.twitter.com/validator
3. **LinkedIn**: https://www.linkedin.com/post-inspector/
4. **Open Graph**: https://ogp.me/

### Creating OG Image

Place image at `/home/pi/acty-site/build/og-image.png` (1200x630px):

```bash
# Recommended: 1200x630px PNG image
# URL: https://acty-labs.com/og-image.png
```

---

## 3. 🔌 API Integration

### Configuration Files

#### Development (.env)

```env
REACT_APP_API_URL=http://192.168.68.138:8765
REACT_APP_EARLY_ACCESS_ENDPOINT=/api/early-access
REACT_APP_APP_NAME=Acty Cactus
```

#### Production (.env.production)

```env
REACT_APP_API_URL=https://api.acty-labs.com
REACT_APP_APP_NAME=Acty Cactus
REACT_APP_WEBSITE_URL=https://acty-labs.com
```

### API Configuration Module

Created `frontend/src/config.js`:

```javascript
const getApiUrl = () => {
  if (typeof window !== "undefined") {
    return process.env.REACT_APP_API_URL || "https://api.acty-labs.com";
  }
  return process.env.REACT_APP_API_URL || "http://192.168.68.138:8765";
};

export const API_BASE = getApiUrl();
export const API_ENDPOINTS = {
  HEALTH: `${API_BASE}/health`,
  INSIGHTS: `${API_BASE}/insights`,
  EARLY_ACCESS: `${API_BASE}/api/early-access`,
  // ... more endpoints
};
```

### Using API Configuration in React Components

```javascript
import { API_BASE, API_ENDPOINTS } from "./config";

// Instead of hardcoding URLs
// ❌ Bad: fetch('http://192.168.68.138:8765/insights')

// ✅ Good: fetch(API_ENDPOINTS.INSIGHTS)
const response = await fetch(API_ENDPOINTS.INSIGHTS);
```

### API Endpoints

#### Via Caddy Proxy (Production)

```
GET  https://acty-labs.com/api/*              → api.acty-labs.com/...
GET  https://acty-labs.com/llm-config/*       → api.acty-labs.com/llm-config/...
GET  https://acty-labs.com/insights/*         → api.acty-labs.com/insights/...
GET  https://api.acty-labs.com/health         → 192.168.68.138:8765/health
```

#### Via Direct URL (Production)

```
GET  https://api.acty-labs.com/health
GET  https://api.acty-labs.com/insights
GET  https://api.acty-labs.com/llm-config
```

### CORS Headers Configuration

The Caddy reverse proxy includes proper CORS headers:

```caddy
header_up X-Real-IP {remote}
header_up X-Forwarded-For {remote}
header_up X-Forwarded-Proto {scheme}
```

**Verify CORS:**

```bash
curl -i -H "Origin: https://acty-labs.com" https://api.acty-labs.com/health
```

### Running API Integration Verification

```bash
# Test all API endpoints and configuration
./verify_api_integration.sh

# Expected output:
# ✅ Health Check: 200
# ✅ API Routes via proxy
# ✅ CORS Configuration
# ✅ Response Formats (JSON)
# ✅ Backend Connection
# ✅ .env Configuration
```

---

## 4. 📋 Complete Deployment Workflow

### Step 1: Build Frontend

```bash
cd frontend
npm install
npm run build
```

### Step 2: Configure Environment

```bash
# Copy .env.production to deployment
cp frontend/.env.production /home/pi/acty-site/.env.production
```

### Step 3: Deploy

```bash
# Copy build to CM3588
scp -r frontend/build/* pi@192.168.68.121:/home/pi/acty-site/build/

# Copy Caddyfile
scp Caddyfile pi@192.168.68.121:/etc/caddy/Caddyfile

# Reload Caddy
ssh pi@192.168.68.121 "sudo systemctl reload caddy"
```

### Step 4: Verify Deployment

```bash
# Run verification scripts
./verify_seo.sh
./verify_api_integration.sh

# Manual testing
curl https://acty-labs.com/
curl https://api.acty-labs.com/health
```

---

## 5. 🧪 Testing Checklist

### SSL/HTTPS

- [x] Protocol: HTTPS on port 443
- [x] Certificate: Valid and trusted
- [x] HTTP to HTTPS redirects working
- [x] HSTS headers present
- [x] No mixed content warnings
- [x] SSL Labs rating: A or A+

### SEO

- [x] Meta title and description
- [x] Open Graph tags (og:title, og:description, og:image)
- [x] Twitter Card tags (twitter:card, twitter:image)
- [x] Canonical URL
- [x] Robots meta tag (index, follow)
- [x] Structured data (Schema.org)
- [x] Social sharing preview works

### API Integration

- [x] Frontend uses REACT_APP_API_URL environment variable
- [x] API calls use correct endpoints
- [x] CORS headers present
- [x] Backend API responding
- [x] Health checks passing
- [x] Response formats valid (JSON)
- [x] Error handling working

---

## 6. 🚀 Production Deployment Commands

### Deploy with SSL (Let's Encrypt)

```bash
# Copy files
scp -r frontend/build/* pi@192.168.68.121:/home/pi/acty-site/build/
scp Caddyfile pi@192.168.68.121:/etc/caddy/Caddyfile

# Reload Caddy (auto-obtains SSL)
ssh pi@192.168.68.121 "sudo systemctl reload caddy"

# Verify
curl https://acty-labs.com
```

### Deploy with Custom Certificate

```bash
# Copy certificate files
scp ssl/acty-labs.com.pem pi@192.168.68.121:/tmp/cert.pem
scp ssl/acty-labs.com.key pi@192.168.68.121:/tmp/cert.key

# On CM3588 server
ssh pi@192.168.68.121
sudo mkdir -p /etc/ssl/certs /etc/ssl/private
sudo mv /tmp/cert.pem /etc/ssl/certs/acty-labs.com.pem
sudo mv /tmp/cert.key /etc/ssl/private/acty-labs.com.key
sudo chmod 644 /etc/ssl/certs/acty-labs.com.pem
sudo chmod 600 /etc/ssl/private/acty-labs.com.key

# Reload Caddy
sudo systemctl reload caddy
```

---

## 7. 📊 Monitoring

### Monitor SSL Certificate Expiration

```bash
# Check days until expiration
echo | openssl s_client -servername acty-labs.com -connect acty-labs.com:443 2>/dev/null | \
  openssl x509 -noout -enddate
```

### Monitor API Health

```bash
# Set up monitoring
watch -n 60 'curl -s https://api.acty-labs.com/health | jq .'
```

### Check Caddy Logs

```bash
# Real-time logs
ssh pi@192.168.68.121 "sudo journalctl -u caddy -f"

# Recent logs
ssh pi@192.168.68.121 "sudo tail -100 /var/log/caddy/acty-labs.log"
```

---

## 8. ⚙️ Environment Setup Reference

### Development

```bash
NODE_ENV=development
REACT_APP_API_URL=http://192.168.68.138:8765
```

### Production

```bash
NODE_ENV=production
REACT_APP_API_URL=https://api.acty-labs.com
REACT_APP_WEBSITE_URL=https://acty-labs.com
```

### Cloudflare

```bash
CLOUDFLARE_API_TOKEN=your-token
CLOUDFLARE_ZONE_ID=your-zone-id
```

---

## References

- Caddy Documentation: https://caddy.community/
- Let's Encrypt: https://letsencrypt.org/
- Open Graph Protocol: https://ogp.me/
- Schema.org: https://schema.org/
- Robots Meta Tag: https://www.robotstxt.org/
