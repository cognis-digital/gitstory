terraform {
  required_providers {
    docker = { source = "kreuzwerker/docker", version = "~> 3.0" }
  }
}
# Minimal container deploy. Swap the provider block for aws_ecs_service,
# azurerm_container_app, or google_cloud_run_v2_service as needed.
provider "docker" {}
resource "docker_image" "gitstory" { name = "ghcr.io/cognis-digital/gitstory:latest" }
resource "docker_container" "gitstory" {
  name  = "gitstory"
  image = docker_image.gitstory.image_id
  ports { internal = 8000 external = 8000 }
}
