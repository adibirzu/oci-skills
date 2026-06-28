# IAM requirements for fixture-event-worker

- Grant the delivery dynamic group only the resource-family verbs needed by the selected components.
- Scope every statement to the project compartment; never use `manage all-resources in tenancy`.
- Grant runtime principals read access to named Vault secrets, not secret contents in source or state output.
- Validate policy syntax and effective permissions before the first plan.
