# Materialized by the owning domain skills before plan/apply.
locals {
  platform_components = [
    "queue-with-dlq",
    "function-consumer",
    "service-metrics",
    "devops-delivery"
  ]
}
