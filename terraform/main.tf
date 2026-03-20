# Lumio LMS - Production Infrastructure
# All AWS resources defined inline (no modules)
# Region: eu-central-1 | Account: 674544924217

# ---------------------------------------------------------------------------
# Locals
# ---------------------------------------------------------------------------
locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = {
    Project     = "lumio"
    Environment = var.environment
  }

  account_id = "674544924217"
  ecr_base   = "${local.account_id}.dkr.ecr.${var.aws_region}.amazonaws.com"
}

# ---------------------------------------------------------------------------
# VPC
# ---------------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-vpc" })
}

# ---------------------------------------------------------------------------
# Subnets
# ---------------------------------------------------------------------------
resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone       = var.availability_zones[count.index]
  map_public_ip_on_launch = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-public-${count.index + 1}"
    Tier = "public"
  })
}

resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = var.availability_zones[count.index]

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-private-${count.index + 1}"
    Tier = "private"
  })
}

# ---------------------------------------------------------------------------
# Internet Gateway + Public Route Table
# ---------------------------------------------------------------------------
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-igw" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-rt-public" })
}

resource "aws_route_table_association" "public" {
  count = 2

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# ---------------------------------------------------------------------------
# NAT Gateway + Private Route Table
# ---------------------------------------------------------------------------
resource "aws_eip" "nat" {
  domain = "vpc"

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nat-eip" })

  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  allocation_id = aws_eip.nat.id
  subnet_id     = aws_subnet.public[0].id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-nat" })

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main.id
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-rt-private" })
}

resource "aws_route_table_association" "private" {
  count = 2

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

# ---------------------------------------------------------------------------
# Security Groups
# ---------------------------------------------------------------------------

# ALB: accepts HTTP/HTTPS from the world
resource "aws_security_group" "alb" {
  name        = "${local.name_prefix}-alb-sg"
  description = "Allow inbound HTTP/HTTPS to ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb-sg" })
}

# App: accepts port 8000 from ALB only
resource "aws_security_group" "app" {
  name        = "${local.name_prefix}-app-sg"
  description = "Allow inbound 8000 from ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description             = "Django app port"
    from_port               = 8000
    to_port                 = 8000
    protocol                = "tcp"
    security_groups         = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-app-sg" })
}

# RDS: accepts PostgreSQL only from app sg
resource "aws_security_group" "rds" {
  name        = "${local.name_prefix}-rds-sg"
  description = "Allow PostgreSQL from app SG"
  vpc_id      = aws_vpc.main.id

  ingress {
    description             = "PostgreSQL"
    from_port               = 5432
    to_port                 = 5432
    protocol                = "tcp"
    security_groups         = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-rds-sg" })
}

# Redis: accepts Redis port only from app sg
resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Allow Redis from app SG"
  vpc_id      = aws_vpc.main.id

  ingress {
    description             = "Redis"
    from_port               = 6379
    to_port                 = 6379
    protocol                = "tcp"
    security_groups         = [aws_security_group.app.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-redis-sg" })
}

# ---------------------------------------------------------------------------
# S3 Buckets
# ---------------------------------------------------------------------------

# --- Raw Uploads ---
resource "aws_s3_bucket" "raw_uploads" {
  bucket = var.s3_raw_bucket_name

  tags = merge(local.common_tags, { Name = var.s3_raw_bucket_name, Purpose = "raw-uploads" })
}

resource "aws_s3_bucket_versioning" "raw_uploads" {
  bucket = aws_s3_bucket.raw_uploads.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw_uploads" {
  bucket = aws_s3_bucket.raw_uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw_uploads" {
  bucket                  = aws_s3_bucket.raw_uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Processed Media ---
resource "aws_s3_bucket" "processed_media" {
  bucket = var.s3_processed_bucket_name

  tags = merge(local.common_tags, { Name = var.s3_processed_bucket_name, Purpose = "processed-media" })
}

resource "aws_s3_bucket_versioning" "processed_media" {
  bucket = aws_s3_bucket.processed_media.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "processed_media" {
  bucket = aws_s3_bucket.processed_media.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "processed_media" {
  bucket                  = aws_s3_bucket.processed_media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# --- Assets ---
resource "aws_s3_bucket" "assets" {
  bucket = var.s3_assets_bucket_name

  tags = merge(local.common_tags, { Name = var.s3_assets_bucket_name, Purpose = "assets" })
}

resource "aws_s3_bucket_versioning" "assets" {
  bucket = aws_s3_bucket.assets.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "assets" {
  bucket = aws_s3_bucket.assets.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "assets" {
  bucket                  = aws_s3_bucket.assets.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ---------------------------------------------------------------------------
# CloudFront (Processed Media)
# ---------------------------------------------------------------------------
resource "aws_cloudfront_origin_access_control" "processed_media" {
  name                              = "${local.name_prefix}-processed-media-oac"
  description                       = "OAC for Lumio processed media bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "processed_media" {
  enabled             = true
  comment             = "Lumio processed media CDN"
  default_root_object = ""

  origin {
    domain_name              = aws_s3_bucket.processed_media.bucket_regional_domain_name
    origin_id                = "s3-processed-media"
    origin_access_control_id = aws_cloudfront_origin_access_control.processed_media.id
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "s3-processed-media"
    viewer_protocol_policy = "redirect-to-https"

    # Use managed caching policy: CachingOptimized
    cache_policy_id = "658327ea-f89d-4fab-a63d-7e88639e58f6"

    # Require signed URLs — responses to unsigned requests will be 403
    trusted_key_groups = ["fa06b1a0-d9ae-447e-a3c6-af196ff09f02"]
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  price_class = "PriceClass_100"

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-cf-processed-media" })
}

# S3 bucket policy granting CloudFront OAC read access
resource "aws_s3_bucket_policy" "processed_media" {
  bucket = aws_s3_bucket.processed_media.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowCloudFrontOAC"
        Effect = "Allow"
        Principal = {
          Service = "cloudfront.amazonaws.com"
        }
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.processed_media.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.processed_media.arn
          }
        }
      }
    ]
  })

  depends_on = [aws_s3_bucket_public_access_block.processed_media]
}

# ---------------------------------------------------------------------------
# RDS PostgreSQL 16
# ---------------------------------------------------------------------------
resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-db-subnet-group" })
}

resource "aws_db_instance" "main" {
  identifier        = "${local.name_prefix}-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = var.db_instance_class
  allocated_storage = var.db_allocated_storage

  db_name  = "lumio"
  username = "lumio"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az                = false
  publicly_accessible     = false
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = var.db_backup_retention_period

  storage_encrypted = true

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-db" })
}

# ---------------------------------------------------------------------------
# ElastiCache Redis 7
# ---------------------------------------------------------------------------
resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-redis-subnet-group" })
}

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${local.name_prefix}-redis"
  engine               = "redis"
  engine_version       = var.redis_engine_version
  node_type            = var.redis_node_type
  num_cache_nodes      = 1
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-redis" })
}

# ---------------------------------------------------------------------------
# IAM Roles for ECS
# ---------------------------------------------------------------------------

# Task Execution Role (ECR pull, CloudWatch logs)
data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "${local.name_prefix}-ecs-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-ecs-execution-role" })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy_attachment" "ecs_execution_cloudwatch" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

resource "aws_iam_role_policy_attachment" "ecs_execution_s3" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

# Task Role (runtime permissions for the app)
resource "aws_iam_role" "ecs_task_role" {
  name               = "${local.name_prefix}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-ecs-task-role" })
}

resource "aws_iam_role_policy_attachment" "ecs_task_s3" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_role_policy_attachment" "ecs_task_cloudwatch" {
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchLogsFullAccess"
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "lumio_app" {
  name              = "/ecs/lumio-app"
  retention_in_days = 30

  tags = merge(local.common_tags, { Name = "/ecs/lumio-app" })
}

resource "aws_cloudwatch_log_group" "lumio_celery" {
  name              = "/ecs/lumio-celery"
  retention_in_days = 30

  tags = merge(local.common_tags, { Name = "/ecs/lumio-celery" })
}

resource "aws_cloudwatch_log_group" "lumio_ffmpeg" {
  name              = "/ecs/lumio-ffmpeg"
  retention_in_days = 30

  tags = merge(local.common_tags, { Name = "/ecs/lumio-ffmpeg" })
}

# ---------------------------------------------------------------------------
# Application Load Balancer
# ---------------------------------------------------------------------------
resource "aws_lb" "main" {
  name               = "${local.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = false

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-alb" })
}

resource "aws_lb_target_group" "app" {
  name        = "${local.name_prefix}-app-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health/"
    protocol            = "HTTP"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-app-tg" })
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ---------------------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------------------

# NOTE: cluster name is hardcoded to "lumio" — CI/CD workflow references it by this exact name
resource "aws_ecs_cluster" "main" {
  name = "lumio"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.common_tags, { Name = "lumio" })
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

# ---------------------------------------------------------------------------
# Shared container environment variables (interpolated at apply time)
# ---------------------------------------------------------------------------
locals {
  shared_environment = [
    { name = "DJANGO_SETTINGS_MODULE", value = "config.settings.production" },
    { name = "DJANGO_SECRET_KEY",      value = var.django_secret_key },
    { name = "DB_HOST",                value = aws_db_instance.main.address },
    { name = "DB_PORT",                value = "5432" },
    { name = "DB_NAME",                value = "lumio" },
    { name = "DB_USER",                value = "lumio" },
    { name = "DB_PASSWORD",            value = var.db_password },
    { name = "REDIS_URL",              value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379/0" },
    { name = "AWS_REGION",             value = var.aws_region },
    { name = "S3_RAW_BUCKET",          value = var.s3_raw_bucket_name },
    { name = "S3_PROCESSED_BUCKET",    value = var.s3_processed_bucket_name },
    { name = "S3_ASSETS_BUCKET",       value = var.s3_assets_bucket_name },
    { name = "CLOUDFRONT_DOMAIN",      value = aws_cloudfront_distribution.processed_media.domain_name },
    { name = "RESEND_API_KEY",              value = var.resend_api_key },
    { name = "CLOUDFRONT_KEY_PAIR_ID",      value = var.cloudfront_key_pair_id },
    { name = "CLOUDFRONT_PRIVATE_KEY_B64",  value = var.cloudfront_private_key_b64 },
  ]
}

# ---------------------------------------------------------------------------
# ECS Task Definition — lumio-app
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "app" {
  family                   = "lumio-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "lumio-app"
      image     = "${local.ecr_base}/lumio-app:${var.image_tag}"
      essential = true

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = local.shared_environment

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.lumio_app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health/ || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "lumio-app" })
}

# ---------------------------------------------------------------------------
# ECS Task Definition — lumio-celery
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "celery" {
  family                   = "lumio-celery"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "lumio-celery"
      image     = "${local.ecr_base}/lumio-celery:${var.image_tag}"
      essential = true

      environment = local.shared_environment

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.lumio_celery.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "celery"
        }
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "lumio-celery" })
}

# ---------------------------------------------------------------------------
# ECS Task Definition — lumio-ffmpeg
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "ffmpeg" {
  family                   = "lumio-ffmpeg"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "lumio-ffmpeg"
      image     = "${local.ecr_base}/lumio-ffmpeg:${var.image_tag}"
      essential = true

      environment = local.shared_environment

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.lumio_ffmpeg.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ffmpeg"
        }
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "lumio-ffmpeg" })
}

# ---------------------------------------------------------------------------
# ECS Services
# ---------------------------------------------------------------------------

# NOTE: service name is hardcoded to "lumio-app" — CI/CD workflow references it by this exact name
resource "aws_ecs_service" "app" {
  name            = "lumio-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.ecs_app_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "lumio-app"
    container_port   = 8000
  }

  # Allow rolling updates without downtime
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy_attachment.ecs_execution_policy,
  ]

  tags = merge(local.common_tags, { Name = "lumio-app" })
}

resource "aws_ecs_service" "celery" {
  name            = "${local.name_prefix}-celery"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.celery.arn
  desired_count   = var.ecs_celery_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [aws_iam_role_policy_attachment.ecs_execution_policy]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-celery" })
}

resource "aws_ecs_service" "ffmpeg" {
  name            = "${local.name_prefix}-ffmpeg"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ffmpeg.arn
  desired_count   = var.ecs_ffmpeg_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = false
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  depends_on = [aws_iam_role_policy_attachment.ecs_execution_policy]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-ffmpeg" })
}
