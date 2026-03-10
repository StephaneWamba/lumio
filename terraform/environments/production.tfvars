# Production environment variables
# Use with: terraform apply -var-file="environments/production.tfvars"

aws_region   = "eu-central-1"
environment  = "production"
project_name = "lumio"

# VPC
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["eu-central-1a", "eu-central-1b"]

# RDS PostgreSQL
db_instance_class          = "db.t3.small"
db_allocated_storage       = 100
db_backup_retention_period = 30

# Redis
redis_engine_version = "7.0"
redis_node_type      = "cache.t3.small"

# ECS
ecs_app_container_port = 8000
ecs_app_desired_count  = 3
ecs_celery_desired_count = 2
ecs_ffmpeg_desired_count = 1
ecs_task_cpu    = 512
ecs_task_memory = 1024

# S3 Buckets
s3_raw_bucket_name       = "lumio-raw-uploads"
s3_processed_bucket_name = "lumio-processed-media"
s3_assets_bucket_name    = "lumio-assets"

# CloudFront
cloudfront_ttl = 86400

# Domain
domain_name = "api.lumio.io"

# Secrets - inject via GitHub Actions secrets
# certificate_arn        = retrieved from ACM
# django_secret_key      = from Secrets Manager
# db_password            = from Secrets Manager
# image_tag              = from CI/CD (github.sha)
