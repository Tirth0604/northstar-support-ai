# Deployment
Compose starts PostgreSQL 16, Redis 7, FastAPI, and Nginx. Backend startup runs Alembic and idempotent demo seed; named volumes persist database, Redis, uploads, and vectors.

For Render/Railway, deploy both Dockerfiles, provision managed PostgreSQL, set a strong JWT secret/exact origins, mount durable `/app/data`, and use release migrations. For multiple replicas replace local vectors with pgvector/Qdrant and uploads with object storage. AWS/DigitalOcean equivalents use ECS/App Platform, RDS/managed PostgreSQL, managed Redis, S3/Spaces, KMS/Secrets Manager, TLS, backups/PITR, alerting, and least-privilege networks. Do not seed production.
