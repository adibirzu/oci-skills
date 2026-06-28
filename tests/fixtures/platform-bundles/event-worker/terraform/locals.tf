locals {
  project_name = "fixture-event-worker"
  common_tags = {
    managed-by = "terraform"
    project    = local.project_name
  }
}
