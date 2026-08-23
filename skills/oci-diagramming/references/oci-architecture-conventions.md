# OCI architecture conventions

## Structure

- Name and nest only real boundaries: organization/tenancy, compartment, region,
  availability domain, fault domain, VCN, subnet, cluster, namespace, workload.
- For one-AD regions, show fault-domain distribution rather than inventing ADs.
- Use regional subnets unless a design specifically requires AD-scoped subnets.
- Label public/private reachability, ingress/egress, routes, gateways, NSG/firewall
  policy points, key ownership, and administrative access paths.
- Separate logical service relationships from physical/deployment topology.

## Draw.io layers

Use bottom-to-top layers: `Boundaries`, `Network`, `Workloads`, `Observability`,
`Security`, `Annotations`. Lock stable lower layers. Duplicate/hide layers for
as-is/to-be alternatives and export different detail levels without flattening
the editable source.

## Flow semantics

| Flow | Visual |
|---|---|
| synchronous data | solid charcoal arrow |
| control/configuration | dashed gray arrow |
| telemetry | short-dashed Oracle-red arrow |
| replication/backup | heavier green arrow |
| response/callback | open dashed blue arrow |
| trust boundary | red dashed enclosure/line, not a data arrow |

## OCI observability pipeline

Show separately: sources; collection (agents, OTel Collector, service logs);
transport/buffer (Service Connector Hub, Streaming); processing (parse, redact,
normalize, enrich, sample, route); OCI Monitoring/Logging/Logging Analytics/APM;
Object Storage retention; Notifications/Events/Functions or ITSM response; and
customer-managed/SIEM/OpenTelemetry exports. Do not imply that one service
automatically performs every stage.

## AI and GPU monitoring

Include model/API latency, time-to-first-token, tokens, errors, throttling, safety
outcomes, evaluation quality, agent/tool spans, retrieval evidence, GPU utilization,
memory, temperature/power, interconnect/network, node/OKE health, capacity and cost.
Mark prompt/response capture as opt-in and redacted; trace IDs must correlate tiers
without storing secrets or customer content by default.

## Authoritative sources

- Oracle OCI Architecture Icons and diagrams: https://docs.oracle.com/en-us/iaas/Content/General/Reference/graphicsfordiagrams.htm
- Layered Draw.io technique: https://blogs.oracle.com/cloud-infrastructure/layered-architecture-diagrams-drawio
- OCI Architecture Center: https://docs.oracle.com/en/solutions/
- OCI security architecture: https://www.oracle.com/a/ocom/docs/oracle-cloud-infrastructure-security-architecture.pdf
- OCI Network Firewall examples: https://docs.oracle.com/en-us/iaas/Content/Resources/Assets/whitepapers/learn-oci-network-firewall-with-examples.pdf
- OCI IAM OAuth/OIDC flows: https://docs.oracle.com/en-us/iaas/Content/Resources/Assets/whitepapers/oci-iam-oauth-flows-best-practices.pdf
- Hybrid DR: https://docs.oracle.com/en/solutions/design-dr/implement-dr-using-hybrid-deployment1.html
- Redis architecture: https://docs.oracle.com/en/solutions/deploy-redis-cluster/

