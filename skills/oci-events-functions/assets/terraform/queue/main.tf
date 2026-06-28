resource "oci_queue_queue" "worker" {
  compartment_id                   = var.compartment_id
  display_name                     = var.name
  custom_encryption_key_id         = var.custom_encryption_key_id
  retention_in_seconds             = 86400
  visibility_in_seconds            = 60
  timeout_in_seconds               = 20
  dead_letter_queue_delivery_count = 5

  freeform_tags = {
    managed-by = "terraform"
    workload   = "event-worker"
  }
}
