# Pre-Deployment Checklist

> Production readiness checklist for Acty Project deployment to cloud or homelab infrastructure

## 📋 Pre-Flight Checks

### Code Quality

- [ ] Run linter on backend: `black . && flake8 .`
- [ ] Run linter on frontend: `npm run lint` (if configured)
- [ ] No console.log() or debug prints in production code
- [ ] No commented-out code blocks (clean up or document why)
- [ ] All imports are used (no unused imports)
- [ ] Type hints present in Python (at least for public APIs)

### Security

- [ ] `.env` NOT committed (check: `git status | grep .env`)
- [ ] `.env.example` has placeholder values only (no real secrets)
- [ ] API keys rotated (Cloudflare, Anthropic, Supabase)
- [ ] Database passwords set to secure random strings
- [ ] No hardcoded credentials in code or config
- [ ] CORS properly configured (`CORSMiddleware` origins restricted)
- [ ] Rate limiting enabled on API endpoints
- [ ] HTTPS enforced (via Caddy or reverse proxy)

### Dependencies

- [ ] `pip freeze > requirements.txt` (backend pinned versions)
- [ ] `npm audit` run and vulnerabilities fixed
- [ ] No dev dependencies in production image
- [ ] Python requirement versions pinned (`==` not `>=`)
- [ ] No security warnings in `npm audit`

### Database

- [ ] PostgreSQL migrations applied: `alembic upgrade head`
- [ ] Database initialized with schema: `psql < scripts/init_db.sql`
- [ ] Backups configured (scheduled daily)
- [ ] Database user has least-privilege permissions (not root)
- [ ] Connection pooling configured (asyncpg, psycopg2)
- [ ] Database URL uses production connection string

### Docker & Infrastructure

- [ ] `docker-compose` tested locally: `docker compose up -d`
- [ ] All services pass healthchecks
- [ ] `docker compose logs` shows no errors
- [ ] Volumes mounted correctly (data/, models/, PostgreSQL storage)
- [ ] Container resource limits set (CPU, memory)
- [ ] Networks isolated (only necessary services talk to each other)
- [ ] Ports exposed only as needed (8765 for API, 3000 for web)

### Frontend Build

- [ ] `npm run build` succeeds without warnings
- [ ] Build artifacts in `frontend/build/` are minified
- [ ] Environment variables set: `REACT_APP_API_URL=https://api.acty-labs.com`
- [ ] Static assets load from correct paths (no /localhost/ hardcodes)
- [ ] HTML has proper meta tags (title, description, og:image for social)
- [ ] Service worker configured (if using PWA features)
- [ ] Build size analyzed: `npm run build -- --analyze`

### API & Backend

- [ ] FastAPI server starts: `python backend/api/server.py`
- [ ] Health endpoint responds: `curl http://localhost:8765/health`
- [ ] API documentation is complete: check `/docs` endpoint
- [ ] All endpoints have error handlers (500s shouldn't crash server)
- [ ] Logging configured (structured JSON logs for production)
- [ ] Request/response validation working (Pydantic models)
- [ ] CORS headers include only production domain

### Environment Configuration

- [ ] `.env` created from `.env.example` with real values
- [ ] Test `.env` connectivity: `python -c "import os; print(os.getenv('DATABASE_URL'))"`
- [ ] All required variables set (no empty or missing keys)
- [ ] Sensitive variables injected at runtime, not baked into Docker images
- [ ] Configuration documented in README

### Testing

- [ ] Backend unit tests pass: `pytest tests/ -v`
- [ ] API smoke tests pass (at least /health, /query endpoints)
- [ ] Database tests can connect and create tables
- [ ] Frontend CI linting passes (if configured)
- [ ] No known issues in git (clean `git status`)

### Documentation

- [ ] README has setup instructions (venv, pip install, etc.)
- [ ] README has deployment instructions (Docker, environment setup)
- [ ] API documentation generated (`/docs` endpoint readable)
- [ ] Architecture diagram updated (if applicable)
- [ ] Database schema documented (ER diagram or DDL comments)
- [ ] Environment variables documented (.env.example is readable)
- [ ] Known issues & limitations documented

### Git & Version Control

- [ ] Latest commit tagged: `git tag -a v1.0.0 -m "Production release"`
- [ ] All changes committed: `git status` is clean
- [ ] `.gitignore` is complete (venv/, node_modules/, .env, etc.)
- [ ] No large files (>100 MB) in git history
- [ ] Repository is private (or secrets redacted in public version)

---

## 🚀 Deployment Steps

### Local Verification (Before Push)

```bash
# 1. Code quality
black backend/ && flake8 backend/
cd frontend && npm run lint

# 2. Build Docker images
docker compose build

# 3. Start services
docker compose up -d

# 4. Run health checks
docker compose ps          # all should be healthy
curl http://localhost:8765/health
curl http://localhost:3000

# 5. Check logs for errors
docker compose logs -f api | head -20
```

### Staging Deployment (If Applicable)

```bash
# 1. Build and test in staging environment
# 2. Run smoke tests against staging API
# 3. Verify database migrations work
# 4. Test backup/restore cycle
```

### Production Deployment

```bash
# 1. Backup current database (if upgrading)
# 2. Pull latest code: git pull origin main
# 3. Update dependencies (if needed): pip install -r requirements.txt
# 4. Run migrations: alembic upgrade head (or docker exec)
# 5. Restart services: docker compose down && docker compose up -d
# 6. Monitor logs: docker compose logs -f
# 7. Verify health: curl https://api.acty-labs.com/health
```

### Post-Deployment Verification

- [ ] API responds from public domain (https://api.acty-labs.com)
- [ ] Website loads (https://acty-labs.com)
- [ ] Database queries work (check logs)
- [ ] No error spikes in logs (first 5 minutes)
- [ ] Performance acceptable (response times < 500ms)
- [ ] Monitoring/alerting active (if configured)

---

## 📊 Deployment Environments

### Development (`ENVIRONMENT=development`)

- PostgreSQL running locally or in Docker
- Ollama on 192.168.68.138 (accessible)
- API at http://localhost:8765
- Frontend at http://localhost:3000
- Debug logging enabled

### Production (`ENVIRONMENT=production`)

- PostgreSQL on 192.168.68.138 (docker or cloud)
- Ollama on 192.168.68.138 (shared inference)
- API at https://api.acty-labs.com (via Caddy)
- Frontend at https://acty-labs.com (via Caddy CM3588)
- Structured JSON logging, no debug output
- Error monitoring active (Sentry / monitoring tool)

---

## 🔧 Troubleshooting Deployment

### Services Won't Start

```bash
docker compose logs -f api              # check error
docker compose down && docker compose up    # restart with output
```

### Database Connection Failed

```bash
# Check PostgreSQL is running
docker compose ps postgres
# Verify DATABASE_URL in .env
# Check network connectivity
docker exec acty-api curl http://postgres:5432 -v
```

### Frontend Build Too Large

```bash
# Analyze bundle size
npm run build -- --analyze
# Check for large dependencies
npm ls | grep -i large-package-name
# Remove if unused
npm uninstall package-name
```

### API Returns 502 Bad Gateway

```bash
# Check if service is healthy
docker compose ps api
# Check application logs
docker compose logs api --tail=50
# Verify all environment variables are set
docker exec acty-api env | grep -E "DATABASE_URL|OLLAMA"
```

---

## 📝 Sign-Off

When all items are checked, the deployment is **production-ready**.

- **Prepared By**: ********\_\_\_\_********
- **Date**: ********\_\_\_\_********
- **Environment**: [ ] Development | [ ] Staging | [ ] Production

---

**Last Updated**: March 28, 2026  
**Status**: Ready for initial deployment
