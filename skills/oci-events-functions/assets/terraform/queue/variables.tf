variable "compartment_id" {
  type      = string
  sensitive = true
}

variable "name" {
  type = string
}

variable "custom_encryption_key_id" {
  type      = string
  sensitive = true
  default   = null
}
