# This Terraform configuration targets LocalStack, NOT real AWS.
# It exists to demonstrate IaC skills without incurring any AWS cost.
# Every `endpoints` block below points at localstack_endpoint instead
# of real AWS service URLs.

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ecs            = var.localstack_endpoint
    secretsmanager = var.localstack_endpoint
    logs           = var.localstack_endpoint
    iam            = var.localstack_endpoint
  }
}
