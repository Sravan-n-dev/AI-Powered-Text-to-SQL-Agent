# Simulates AWS Secrets Manager via LocalStack. In real production this
# would hold DB credentials / API keys; here it demonstrates the pattern
# without any real secret ever touching a real AWS account.

resource "aws_secretsmanager_secret" "db_credentials" {
  name = "${var.project_name}-db-credentials"
}

resource "aws_secretsmanager_secret_version" "db_credentials_value" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = "t2sql"
    password = "t2sql_password" # placeholder only — never commit real secrets
  })
}
