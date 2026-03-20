terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Configured via backend config vars during init
    # Backend state configuration is in environments/{staging,production}/backend.tfvars
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Environment = var.environment
      Project     = "lumio"
      ManagedBy   = "terraform"
    }
  }
}
