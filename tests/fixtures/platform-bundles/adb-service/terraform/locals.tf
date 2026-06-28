locals {
  project_name = "fixture-adb-service"
  common_tags = {
    managed-by = "terraform"
    project    = local.project_name
  }
}
