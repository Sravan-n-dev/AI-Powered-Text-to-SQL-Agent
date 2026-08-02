# Simulates hosting the FastAPI app on ECS via LocalStack's ECS emulation.
# This is illustrative IaC — LocalStack's free tier ECS support is
# limited (it doesn't actually run real containers the way AWS ECS
# does), so treat this as "the Terraform I'd use against real AWS",
# validated for syntax/plan correctness against LocalStack, not as a
# fully functional local container orchestrator. For actually running
# the app locally, use docker-compose (see README) — this Terraform is
# for demonstrating the migration path.

resource "aws_ecs_cluster" "app_cluster" {
  name = "${var.project_name}-cluster"
}

resource "aws_ecs_task_definition" "app_task" {
  family                   = "${var.project_name}-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "512"
  memory                   = "1024"

  container_definitions = jsonencode([
    {
      name  = "${var.project_name}-api"
      image = "${var.project_name}:latest"
      portMappings = [{ containerPort = 8000, hostPort = 8000 }]
    }
  ])
}
