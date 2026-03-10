# Terraform outputs - Phase 0 scaffold, expanded in Phase 1

output "api_endpoint" {
  description = "API endpoint URL"
  value       = "https://api.lumio.io"
}

output "health_check_url" {
  description = "Health check endpoint"
  value       = "https://api.lumio.io/health/"
}

# Outputs to be added in Phase 1:
# - RDS endpoint
# - Redis endpoint
# - CloudFront domain
# - ECS cluster name
# - ALB DNS name
