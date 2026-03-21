#!/usr/bin/env bash
# stop.sh — Scale all Lumio ECS services to 0 and stop RDS + ElastiCache
# Run when not developing to avoid AWS costs.
# S3, ECR, VPC, ALB, CloudFront are NOT touched (negligible cost).
#
# Usage: bash scripts/stop.sh

set -euo pipefail

REGION="eu-central-1"
CLUSTER="lumio"
RDS_ID="lumio-production-db"
REDIS_ID="lumio-production-redis"

SERVICES=(
  "lumio-app"
  "lumio-production-celery"
  "lumio-production-ffmpeg"
  "lumio-production-beat"
)

echo "=== Lumio STOP ==="

# 1. Scale all ECS services to 0
echo ""
echo "Scaling ECS services to 0..."
for svc in "${SERVICES[@]}"; do
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$svc" \
    --desired-count 0 \
    --region "$REGION" \
    --no-cli-pager \
    --query "service.{name:serviceName,desired:desiredCount}" \
    --output text
  echo "  ✓ $svc -> 0"
done

# 2. Stop RDS instance (free while stopped; auto-restarts after 7 days)
echo ""
echo "Stopping RDS $RDS_ID..."
RDS_STATUS=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_ID" \
  --region "$REGION" \
  --query "DBInstances[0].DBInstanceStatus" \
  --output text)

if [ "$RDS_STATUS" = "available" ]; then
  aws rds stop-db-instance \
    --db-instance-identifier "$RDS_ID" \
    --region "$REGION" \
    --no-cli-pager \
    --query "DBInstance.DBInstanceStatus" \
    --output text
  echo "  ✓ RDS stopping (takes ~1 min)"
else
  echo "  ↷ RDS is already $RDS_STATUS, skipping"
fi

# 3. Stop ElastiCache replication group (if serverless, skip — no stop API)
echo ""
echo "ElastiCache ($REDIS_ID): no stop API on provisioned clusters."
echo "  → To fully eliminate Redis cost, run: bash scripts/destroy-redis.sh"
echo "  → Leaving running (~\$1.50/day for cache.t3.small)"

echo ""
echo "=== DONE ==="
echo "ECS: all services at 0 tasks (no Fargate charges)"
echo "RDS: stopping (~\$0 while stopped)"
echo "Restart with: bash scripts/start.sh"
