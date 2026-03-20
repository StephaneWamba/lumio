variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-central-1"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "lumio"
}

# VPC & Networking
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
}

variable "availability_zones" {
  description = "Availability zones"
  type        = list(string)
}

# RDS
variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "Allocated storage for RDS in GB"
  type        = number
  default     = 20
}

variable "db_backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

# ElastiCache Redis
variable "redis_engine_version" {
  description = "Redis engine version"
  type        = string
  default     = "7.0"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

# ECS
variable "ecs_app_container_port" {
  description = "Container port for Django app"
  type        = number
  default     = 8000
}

variable "ecs_app_desired_count" {
  description = "Desired number of app task replicas"
  type        = number
  default     = 2
}

variable "ecs_celery_desired_count" {
  description = "Desired number of Celery task replicas"
  type        = number
  default     = 2
}

variable "ecs_ffmpeg_desired_count" {
  description = "Desired number of FFmpeg task replicas"
  type        = number
  default     = 1
}

variable "ecs_task_cpu" {
  description = "Task CPU units (256, 512, 1024, 2048, 4096)"
  type        = number
  default     = 512
}

variable "ecs_task_memory" {
  description = "Task memory in MB"
  type        = number
  default     = 1024
}

# S3
variable "s3_raw_bucket_name" {
  description = "S3 bucket for raw uploads"
  type        = string
}

variable "s3_processed_bucket_name" {
  description = "S3 bucket for processed media"
  type        = string
}

variable "s3_assets_bucket_name" {
  description = "S3 bucket for assets"
  type        = string
}

# CloudFront
variable "cloudfront_ttl" {
  description = "CloudFront default TTL in seconds"
  type        = number
  default     = 86400
}

# Domain
variable "domain_name" {
  description = "Domain name for API"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS"
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Docker image tag (git SHA from CI/CD)"
  type        = string
}

# Secret values (should be stored in Secrets Manager)
variable "django_secret_key" {
  description = "Django SECRET_KEY"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "RDS master password"
  type        = string
  sensitive   = true
}

variable "resend_api_key" {
  description = "Resend API key for transactional email"
  type        = string
  sensitive   = true
}
