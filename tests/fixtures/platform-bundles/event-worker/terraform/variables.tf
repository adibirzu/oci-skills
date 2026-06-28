variable "compartment_id" {
  description = "Target OCI compartment OCID. Supply through TF_VAR_compartment_id."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "OCI region identifier."
  type        = string
}

variable "oci_profile" {
  description = "OCI CLI/config profile; ignored by principal-based automation."
  type        = string
  default     = "DEFAULT"
}
