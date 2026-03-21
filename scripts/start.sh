#!/usr/bin/env bash
# start.sh — Restore all Lumio ECS services and start RDS
# Run when ready to develop/demo.
#
# Usage: bash scripts/start.sh

set -euo pipefail

REGION="eu-central-1"
CLUSTER="lumio"
RDS_ID="lumio-production-db"

# Desired counts — must match terraform/environments/production.tfvars
declare -A DESIRED=(
  ["lumio-app"]=3
  ["lumio-production-celery"]=2
  ["lumio-production-ffmpeg"]=1
  ["lumio-production-beat"]=1
)

echo "=== Lumio START ==="

# 1. Start RDS first (takes ~3 min — do it before ECS so app doesn't crash on boot)
echo ""
echo "Starting RDS $RDS_ID..."
RDS_STATUS=$(aws rds describe-db-instances \
  --db-instance-identifier "$RDS_ID" \
  --region "$REGION" \
  --query "DBInstances[0].DBInstanceStatus" \
  --output text)

if [ "$RDS_STATUS" = "stopped" ]; then
  aws rds start-db-instance \
    --db-instance-identifier "$RDS_ID" \
    --region "$REGION" \
    --no-cli-pager \
    --query "DBInstance.DBInstanceStatus" \
    --output text
  echo "  ✓ RDS starting — waiting for available..."
  aws rds wait db-instance-available \
    --db-instance-identifier "$RDS_ID" \
    --region "$REGION"
  echo "  ✓ RDS available"
elif [ "$RDS_STATUS" = "available" ]; then
  echo "  ↷ RDS already available"
else
  echo "  ↷ RDS is $RDS_STATUS — waiting for available..."
  aws rds wait db-instance-available \
    --db-instance-identifier "$RDS_ID" \
    --region "$REGION"
  echo "  ✓ RDS available"
fi

# 2. Scale ECS services back up
echo ""
echo "Scaling ECS services..."
for svc in "${!DESIRED[@]}"; do
  count="${DESIRED[$svc]}"
  aws ecs update-service \
    --cluster "$CLUSTER" \
    --service "$svc" \
    --desired-count "$count" \
    --region "$REGION" \
    --no-cli-pager \
    --query "service.{name:serviceName,desired:desiredCount}" \
    --output text
  echo "  ✓ $svc -> $count"
done

# 3. Wait for lumio-app to be stable
echo ""
echo "Waiting for lumio-app to stabilize..."
aws ecs wait services-stable \
  --cluster "$CLUSTER" \
  --services "lumio-app" \
  --region "$REGION"
echo "  ✓ lumio-app stable"

echo ""
echo "=== DONE ==="
echo "API:  http://lumio-production-alb-1639211656.eu-central-1.elb.amazonaws.com"
echo "Beat: running (drip, certs, analytics, re-engagement active)"
