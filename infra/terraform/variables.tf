variable "aws_region" {
  description = "AWS region (points at LocalStack's fake endpoint, not real AWS)"
  type        = string
  default     = "us-east-1"
}

variable "localstack_endpoint" {
  description = "LocalStack's local endpoint. Real AWS is never touched."
  type        = string
  default     = "http://localhost:4566"
}

variable "project_name" {
  type    = string
  default = "text-to-sql-agent"
}
