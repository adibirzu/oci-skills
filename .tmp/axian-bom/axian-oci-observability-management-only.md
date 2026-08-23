# OCI Observability & Management response extract

**RFP:** AXIAN-IT & Network-OBS-2026  
**Scope of this extract:** Only responses materially delivered or complemented by
Oracle Cloud Infrastructure Observability & Management services. Oracle Communications
Unified Assurance (UA), ServiceNow, Enterprise Manager and product-team systems are
mentioned only where they form an integration or ownership boundary.  
**Response owner:** Observability & Security team.  
**Required co-owners:** Operations (Pablo) for OEM and ServiceNow operating workflows;
OCI AI Team (Alex Negrea) for the dedicated incident-commander agent.  
**Status convention:** Compliant means a documented OCI service supplies the stated
capability when configured. Partial means discovery, product-team input, licensing,
custom implementation, sizing or PoV evidence is still required.

## 1. Executive summary

OCI Observability & Management provides the cloud and hybrid observability complement
to the Group Unified Assurance core:

- **OCI Monitoring** measures OCI resources, custom platform metrics, alarms and the
  health of the monitoring platform itself.
- **OCI Logging** centralizes OCI service and custom logs.
- **Connector Hub** routes supported observability data to destinations such as Log
  Analytics, Object Storage, Streaming, Notifications and Functions.
- **OCI Log Analytics** provides central log ingestion, parsing, enrichment, clustering,
  investigation and dashboards. Its Kubernetes Monitoring Solution is proposed as the
  standard OKE operations view for logs, metrics and Kubernetes object state.
- **LoganAI** accelerates log/metric interpretation with summaries, explanations and
  follow-up questions. LoganAI is not the RFP’s agentic incident commander.
- **OCI APM** supplies application traces, service topology, browser monitoring and
  synthetic monitoring for priority digital services.
- **OCI Management Agent / Gateway** supplies supported hybrid collection for services
  that require it.
- **OCI Database Management and Operations Insights** are conditional database-team
  services for monitoring, performance, fleet capacity and SQL insights across supported
  database resources.
- **OCI Notifications and Events** support governed alarm distribution and event-driven
  integration. They do not replace the ServiceNow incident process.

Material OCI alarms, anomalies and evidence links are normalized into UA for
cross-domain correlation and service/customer impact. UA then uses its licensed native
ServiceNow Adapter directly; Oracle Integration/OIC is not part of the ticket path.

### Latest answered inputs affecting OCI O&M sizing and design

| Input | OCI Observability & Management response |
|---|---|
| Indicative telemetry volume | Record 2 TB/day as a planning input only; discovery must establish whether this is per OPCO or Group-wide and split it by logs, metrics, traces, events and full/low-resolution telemetry before OCI consumption or capacity is committed. |
| Retention | Configure 6–12 months by data class and residency zone using service retention plus Object/Archive Storage lifecycle tiers. Validate searchable-hot versus archive/replay requirements and cost. |
| Application and database estate | Support priority Java, .NET and PHP services with OCI APM/OpenTelemetry. Database Management and Operations Insights are conditional for supported Oracle/external resources; SQL Server, PostgreSQL and MariaDB coverage uses supported service telemetry or product-owned tools. |
| Kubernetes/container estate | OKE uses OCI Log Analytics Kubernetes Monitoring Solution plus Monitoring, Logging and APM. Tanzu/VKS, EKS, OpenShift and other platforms use supported OpenTelemetry/log collection and remain subject to platform-team access and compatibility validation. |
| Continuity | Design to the answered four-hour RTO and five-to-fifteen-minute RPO, with mandatory HA. Full Stack DR can orchestrate supported OCI application components; each data service and UA component still needs its own replication, restore and drill evidence. |
| Identity/residency | Federate AD/Azure SSO with MFA and role controls. Keep PII in-country or mask it before cross-border movement; use compartments, log groups, IAM, Vault, Audit and region-specific retention paths to enforce the approved model. |
| AI history and autonomy | At least one month of history is expected for AI. LoganAI remains analyst assistance. The requested zero-touch Dark NOC requires a dedicated OCI GenAI agent and a phased safety case; no state-changing action is enabled without bounded authority, tests, approval policy, rollback and audit. |
| ServiceNow | Integrate once with the Group ServiceNow Zurich ITSM instance using the native UA ServiceNow Adapter/API. Size and test for the indicative 50–300 tickets/day per OPCO, including idempotency, retry, outage recovery and bidirectional state synchronization. |

## 2. OCI service architecture fit

| OCI service | RFP fit | Architecture role | Adoption and owner |
|---|---|---|---|
| OCI Monitoring | Infrastructure monitoring; threshold alerts; platform self-monitoring; capacity/backlog alarms | Independent monitoring of OCI resources, custom integration-pipeline metrics, alarms and service-health indicators. Material alarms flow to UA. | Baseline. Observability & Security owns alarm standards; each product team owns its resource thresholds and remediation. |
| OCI Logging | Centralized logs and secure ingestion | Central OCI service/custom logging source; forwards selected data through Connector Hub. | Baseline. Observability & Security owns log groups, retention and routing; product teams own application log quality. |
| Connector Hub | Data ingestion, routing, archive and integration | Managed routing between supported logs/metrics/streams and Log Analytics, Object Storage, Streaming, Notifications or Functions. | Baseline. Delivery semantics, duplicate handling and route health are acceptance items. |
| OCI Log Analytics | Central log analysis, dashboards, anomaly investigation and hybrid collection | Parses, enriches, clusters and investigates selected OCI/on-premises logs; evidence links are attached to correlated UA incidents. | Baseline for selected logs. Data volume, retention, residency and parsers are sized during discovery. |
| Log Analytics Kubernetes Monitoring Solution | Cloud/container monitoring, OKE topology and workload investigation | Collects Kubernetes logs, metrics and object state for supported OKE versions and provides cluster, workload, node and pod views. | Proposed baseline for OKE. Platform team approves cluster access; Observability & Security owns the monitoring solution. Private clusters use the documented manual deployment path. |
| LoganAI | AI-assisted analysis and operator productivity | Explains/summarizes individual logs, multiple logs, clusters and charts, suggests follow-up questions, and can mix selected OCI Monitoring metrics with logs for analysis. | Conditional after realm/region, IAM, licensing, cost and residency review. Human validation required. |
| OCI Generative AI Agents / Responses API | Agentic incident coordination, structured reasoning, evidence synthesis and governed tool use | The dedicated incident coordinator uses the OCI Responses API for model interaction, structured outputs, conversation state and supported agent tools. Function Calling or MCP Calling connects only to approved tools; File Search/vector stores provide governed RAG over runbooks and evidence. | Partial/custom solution. OCI AI Team (Alex Negrea) owns the agent design with Observability & Security. Region/model availability, evaluation, retention, IAM and residency must be accepted. |
| OCI API Gateway | Governed API façade for agent tools and customer integrations | Provides private or approved public API endpoints, authentication/authorization, validation, transformation and throttling. It exposes a stable allowlisted façade to UA REST APIs, OCI service APIs, OEM/vendor APIs, ServiceNow/CMDB read APIs and approved Axian/third-party APIs. | Baseline for the custom agent integration plane when multiple APIs are exposed. Security owns endpoint policy; each product team owns its API contract and permissions. |
| OCI Functions | Bounded API adapters and tool execution | Implements schema validation, redaction, correlation-ID propagation, retries, timeouts and signed OCI/customer API calls behind API Gateway. Read-only tools are the default; any state-changing function requires explicit approval, pre/post-check and rollback. | Partial/custom development. CSS or a qualified partner implements adapters with the relevant product team; Observability & Security validates telemetry and controls. |
| OCI APM | Application/API/microservice monitoring, traces, topology and synthetics | Collects application traces and OpenTelemetry, maps service dependencies, and runs synthetic tests for priority journeys. Signals are correlated in UA. | Baseline for priority applications. Application teams own instrumentation, service IDs and SLOs. |
| OCI Management Agent / Gateway | Secure hybrid collection | Supported collection and communication path between OCI O&M services and selected cloud/on-premises targets. | Baseline where required. Observability & Security owns deployment standards; target/product teams approve access. Distinct from the OEM Management Agent. |
| OCI Database Management | Database monitoring, performance and fleet administration | Unified monitoring/performance console for supported OCI, external and Exadata database resources; approved alarms/metrics can contribute to UA incidents. | Conditional. Database team owns onboarding, credentials, privileges, administration and commercial scope. |
| OCI Operations Insights | Predictive capacity and performance analytics | Database/host capacity analysis, forecasting and SQL performance insights for supported cloud-, agent- or OEM-managed resources. | Conditional advanced analytics. Database/OEM team owns prerequisites and validates findings before operational routing. |
| Notifications and Events | Multi-channel alerting and event-driven integration | Distributes approved alarm notifications and resource-state events; can trigger bounded functions or automation entry points. | Baseline. UA and ServiceNow remain the incident-policy authorities. |
| Object Storage / Archive Storage | Retention, evidence and replay | Low-cost raw telemetry/evidence retention, lifecycle policies, historical replay and backfill. | Baseline. Retention and residency are set by data class and OPCO. |
| OCI IAM, Vault, Audit and Cloud Guard | RBAC, secrets, encryption, audit and security posture | Enforces least privilege and OPCO/environment isolation, protects credentials/keys, records OCI API activity and monitors cloud posture. | Baseline. Observability & Security owns controls; product teams own least-privilege access requests. |

## 3. Extracted RFP requirements and answers

| RFP section and requirement | State | OCI Observability & Management answer | Dependency / evidence |
|---|---|---|---|
| 4.2 Native monitoring to cover OPCO gaps | Compliant | Use OCI Monitoring, Logging, Log Analytics, APM and supported Management Agent collection where an OPCO gap exists. Keep existing tools and send material events to UA. | Discovery source catalogue and per-OPCO onboarding acceptance. |
| 5.1 Integrate with heterogeneous monitoring tools without forced replacement | Partial | OCI O&M accepts service/custom logs, custom metrics, OpenTelemetry and supported agent-based sources; Connector Hub and streaming routes complement the integration fabric. Proprietary OEM schemas still require UA adapters or partner integration. | Interface catalogue and PoV against priority tools. |
| 5.2 Physical/virtual, public/private/hybrid infrastructure monitoring | Compliant | OCI Monitoring covers OCI resources and custom metrics; Log Analytics and Management Agent/Gateway collect selected hybrid logs; Database Management covers supported database infrastructure. | Target support, private connectivity and agent approval. |
| 5.3 Use existing OEM tools | Partial | OEM remains the deep Oracle management plane. Approved OEM events/metrics, target IDs, blackouts and evidence links are exported to UA. OCI Operations Insights may onboard supported OEM-managed resources when selected by the database team. | OEM version/plug-ins, Management Pack entitlements and Operations (Pablo) approval. |
| 5.4 Applications, APIs, middleware, microservices and APM | Compliant | OCI APM and OpenTelemetry provide traces, topology, browser and synthetic telemetry. OCI Logging/Log Analytics provide application log investigation. | Application-team instrumentation, SLO and data-classification hand-off. |
| 5.5 Customer journeys, synthetics and SLO tracking | Partial | OCI APM synthetics and traces measure selected journeys and APIs; Monitoring alarms evaluate approved service indicators. Business/customer impact still depends on UA topology and source data. | Product-team journey definitions and allowed customer-data aggregation. |
| 5.6 Centralized logs, metrics and traces with retention by OPCO/data type | Compliant | Logging, Monitoring, Log Analytics, APM and Object Storage provide managed hot/analytical/archive tiers with compartment, log-group and lifecycle controls. | Final volume, retention, region and residency design. |
| 6.2 Group/OPCO dashboards and role-based views | Compliant | OCI dashboards, Log Analytics dashboards, Kubernetes Solution views and APM views provide service-specific visualisation; Group operational correlation remains in UA. | IAM/compartment model and versioned KPI catalogue. |
| 6.3 Threshold/anomaly alerts, notifications and escalation triggers | Compliant | Monitoring alarms, Log Analytics scheduled alerts/analytics, APM alarms and Notifications provide threshold/anomaly alerting and governed delivery. UA performs cross-domain dedupe/correlation before ServiceNow policy. | Alarm ownership, suppression and maintenance-window policy. |
| 6.4 Automatic ServiceNow tickets with enrichment and bidirectional status | Compliant | OCI evidence links and summaries enrich UA incidents. The licensed UA ServiceNow Adapter directly creates, updates and closes tickets. No OIC path is proposed. | ITSM and Operations (Pablo) approve mapping, correlation key, retry/idempotency and support model. |
| 6.5 Anomaly/trend analysis and operations intelligence | Compliant | Log Analytics clustering, link/cluster compare and anomaly workflows, Monitoring metrics, APM signals and Operations Insights forecasts provide domain analytics. UA supplies cross-domain correlation. | Use-case-specific success metrics and PoV. |
| 6.5 Agentic incident commander / war-room copilot | Partial | LoganAI can summarise/explain logs, clusters, charts and selected Monitoring metrics, but it is not an agent. A dedicated cross-domain incident agent must be built using OCI Generative AI/agent capabilities. | OCI AI Team (Alex Negrea) required; agent architecture, retrieval/tool contracts, citations, evaluation and human approval. |
| 6.5 Agentic automated evidence packaging | Partial | Log Analytics, APM, Monitoring and Object Storage provide governed evidence. A custom agent must retrieve authorised evidence plus UA, OEM and ServiceNow context and package it by resolver policy. | OCI AI Team, CSS/partner development, Operations and Security acceptance. |
| 6.6 Secure collection, backfill and pipeline monitoring | Compliant | Management Agent/Gateway, Logging, Connector Hub, Streaming and Object Storage support secure collection, routing, buffering/archive and replay. Monitoring tracks route/agent/queue health through available service and custom metrics. | Measured throughput, loss, parsing-error and replay tests. |
| 6.7 Parsing, enrichment, retention, masking and export | Partial | Log Analytics sources/parsers/enrichment, service connectors and storage lifecycle policies cover the OCI log path. The Group canonical telecom schema, entity reconciliation and data-residency decisions require custom design. | Data-governance design, parser tests and residency approval. |
| 6.10 Adaptive baselines, anomalies and silent degradation | Partial | Monitoring alarms, Log Analytics ML commands/analytics, APM and Operations Insights can detect domain-specific deviations. Telecom multi-dimensional modelling and accuracy must be validated with UA/data-science use cases. | Historical data, labels, false-positive/negative review and drift process. |
| 6.11 Capacity forecasting and time-to-threshold | Partial | Operations Insights forecasts supported database/host capacity; Monitoring provides metric alarms. Other telecom forecasts require UA and/or governed OCI Data Science models. | Database-team onboarding and use-case accuracy acceptance. |
| 7 HA, scalability, multi-tenancy, RBAC and audit | Partial | Managed OCI services supply regional service architecture, compartments, IAM policies, encryption and Audit. Final end-to-end availability and data isolation include UA, collectors and product-team integrations and require sizing. | Architecture, load, failure and isolation tests. |
| 7.2 Platform self-monitoring and backlog/capacity alerts | Compliant | Monitoring, Logging, APM and service/custom metrics monitor collectors, agents, routes, streams, OKE components and supporting services; alerts go to the independent operations path. | “Monitor the monitoring” dashboard and injected-failure test. |
| 8 Central analytics with distributed collection and hybrid deployment | Compliant | Management Agent/Gateway, private networking, Logging/Log Analytics, APM/OTel and Streaming implement distributed collection to centralized OCI analytics. | Network/port/proxy matrix and per-OPCO deployment pattern. |
| 9 Secure ingestion, IAM integration, encryption and audit | Compliant | IAM federation/policies, Vault, TLS/private networking, service encryption, Audit and Cloud Guard provide the OCI control framework. | Security design, policy review, key/secret rotation and evidence test. |
| 10.3 PoV: ingestion, AIOps, security and workflow evidence | Compliant | OCI services expose measurable ingestion, alarm, query and agent health evidence. The PoV must measure completeness/latency, OKE views, APM trace continuity, LoganAI human validation, UA ticket enrichment and security controls. | Signed acceptance metrics; no generic production claims before evidence. |
| 10.4 Support, patching and professional services | Partial | Oracle Support covers subscribed OCI services under their service terms. Custom parsers, agents, dashboards and integrations need named CSS/partner and Axian owners. | Support plan, escalation matrix, patch lifecycle and statements of work. |

## 4. OKE monitoring answer

The RFP explicitly includes cloud/container platforms, containers, application platforms,
central logs/metrics/traces and topology-aware operations. OCI Log Analytics Kubernetes
Monitoring Solution is therefore **required in the proposed OCI scope**, not merely an
optional add-on. For each approved OKE cluster it collects Kubernetes logs, metrics and
object state and exposes cluster, workload, node and pod views. It is combined with OCI
Monitoring for resource/platform alarms, OCI Logging for OCI service/custom logs,
Connector Hub for routing, and OCI APM/OpenTelemetry for application traces and
synthetics.

For private OKE API endpoints, use the documented manual deployment option for the
Kubernetes monitoring Helm/manifests. The platform team owns cluster access, upgrades,
capacity and remediation; Observability & Security owns monitoring configuration,
telemetry governance, alert quality and cross-domain forwarding to UA.

## 5. LoganAI versus the required agent

| Capability | LoganAI | Dedicated incident-commander agent |
|---|---|---|
| Explain and summarise logs/clusters/charts | Yes, inside Log Analytics | May consume reviewed Log Analytics evidence |
| Mix selected OCI Monitoring metrics with logs | Yes, for AI analysis | Retrieves authorised cross-domain evidence through controlled tools |
| Maintain end-to-end incident state | No | Custom requirement |
| Reconcile UA topology, OEM/APM and ServiceNow state | No | Custom requirement |
| Package evidence by resolver group | No | Custom requirement |
| Assign actions or draft stakeholder communications | Follow-up insight only; not the incident owner | Custom, advisory workflow |
| Execute production changes | No | Disabled by default; any future tool requires explicit allowlist, human approval and audit |
| Required owner | Observability & Security, with security/residency review | OCI AI Team (Alex Negrea) with Observability & Security, Operations and Security |

LoganAI is currently documented for the commercial OC1 realm and depends on OCI
Generative AI availability in a selected region. Enabling it may send log data from the
Log Analytics region to the chosen Generative AI region and incurs model usage. Realm,
region, IAM, quota, model licensing, cost and residency must be approved before use.

### GenAI and API communication path

The dedicated coordinator calls OCI Generative AI through the Responses API. Supported
Function Calling or MCP Calling selects an allowlisted tool, but the model never receives
direct network credentials. OCI API Gateway and OCI Functions form the controlled tool
façade: they authenticate and authorize the request, validate the schema, redact protected
data, apply rate/time/volume limits, propagate the incident correlation ID and call the
approved UA REST, OCI SDK/REST, OEM/vendor, ServiceNow/CMDB read or Axian/third-party API.
The tool result returns with source provenance for the evidence package. The native UA
ServiceNow Adapter remains the only ticket create/update/close path. Production mutations
remain disabled by default and require an exact approved plan, pre-check, post-check,
rollback and audit receipt.

## 6. OOTB gaps requiring CSS, partner or product-team development

| Gap | Required work | Owner |
|---|---|---|
| Group canonical event/entity/service schema | Design mappings, identity resolution, versioning, data-quality checks and controlled promotion. | CSS/qualified integration partner with Observability & Security and data governance. |
| Proprietary network/OEM collectors | Confirm supported interfaces; build/test parsers or adapters where uncovered. | Product team and OEM/vendor; CSS/partner implements the supported integration. |
| Axian-specific Log Analytics parsers and dashboards | Create, test and lifecycle-manage sources, parsers, labels, dashboards and alert queries. | Observability & Security with CSS/partner where required. |
| Application telemetry | Instrument applications and journeys; add service/resource attributes, trace propagation and SLOs. | Application/product teams; Observability & Security defines the standard. |
| Database Management/Ops Insights onboarding | Configure target connectivity, agents, credentials, privileges and commercial scope. | Database/Oracle platform team; Operations (Pablo) participates in operations acceptance. |
| Dedicated agentic incident commander | Build retrieval, tool contracts, cross-domain evidence model, citations, guardrails, evaluation, audit and approval UX. | OCI AI Team (Alex Negrea) with CSS/qualified AI partner; Observability & Security, Operations and Security accept. |
| Production sizing and SLO/DR commitments | Benchmark measured volume, cardinality, retention, query latency, failure, restore and failover. | Joint Oracle/CSS/partner team; Axian owners sign acceptance. |

## 7. Solution bill of materials (BOM)

This BOM is a solution and procurement baseline, not a binding commercial quote. Exact
service quantities and SKUs must be generated from measured discovery data and the
applicable Oracle agreement. The current 2 TB/day figure is a planning input only until
it is split by OPCO, region, telemetry type, searchable retention and archive retention.

| Layer / component | Status | Baseline quantity or sizing driver | Commercial / implementation note |
|---|---|---|---|
| Oracle Communications Unified Assurance Hyperscale core | Existing / Assurance dependency | One Group logical platform with production, non-production and DR capacity sized by event rate, topology size, service models, concurrent operators and OPCO isolation. | Supplied and licensed by the Assurance workstream; not priced in the OCI O&M estimate. |
| Unified Assurance collectors and source adapters | Required dependency | Collector capacity per OPCO, failure domain and source type; count from the approved telecom, infrastructure, OEM and application interface catalogue. | Assurance/product teams confirm supported collectors; uncovered proprietary interfaces require CSS/partner work. |
| Unified Assurance native ServiceNow Adapter | Required interface | One Group ServiceNow integration plus non-production test path; validate 50-300 tickets/day per OPCO, retries, idempotency and bidirectional state. | Verify UA adapter entitlement. This remains the only incident create/update/close path; no OIC SKU is included. |
| Oracle Enterprise Manager Cloud Control, repository and Management Agents | Existing / conditional | Reuse the approved OEM estate; validate OMS/repository HA, target count, plug-ins, agent versions, API/export load and DR. | Operations involvement (Pablo) is required. New OEM infrastructure is not assumed until discovery identifies a gap. |
| OEM Diagnostics, Tuning and other applicable Management Packs | Conditional | Quantity follows the applicable license metric and managed-target scope. Enable only the pack features selected by the database/OEM team. | Entitlement must be verified before use; no pack is assumed merely because OEM is installed. |
| OCI Monitoring | Required OCI O&M | Compartments, custom metric streams, dimensions, alarms, notification fan-out and query volume; separate Group and OPCO scopes. | Use the current Oracle rate card/Cost Estimator after metric cardinality and alarm design are known. |
| OCI Logging | Required OCI O&M | Daily service/custom log ingestion, active search retention, log groups and cross-region/residency routing. | Product teams own log quality; exclude unapproved raw payloads and duplicate ingestion. |
| Connector Hub | Required OCI O&M | Service connectors per source/destination/residency route, including Log Analytics, Object Storage, Streaming, Notifications and Functions. | Validate delivery semantics, duplicate handling, dead-letter/replay design and route-health monitoring. |
| OCI Log Analytics | Required OCI O&M | GB/day of selected analytical logs, searchable retention, entities, sources, parsers, scheduled tasks, dashboards and concurrent users. | Do not size from the full 2 TB/day figure without filtering and tiering. LoganAI/model usage is assessed separately. |
| Log Analytics Kubernetes Monitoring Solution | Required for approved OKE clusters | One deployment per cluster; size by clusters, nodes, pods, namespaces, log volume, object-state volume and retention. | Private OKE clusters use the supported manual deployment path; cluster access remains with the platform team. |
| LoganAI | Conditional | Enabled users, investigation frequency, selected logs/metrics and model calls after realm/region and residency validation. | Analyst assistance only; not the dedicated incident commander. Human validation and GenAI consumption apply. |
| OCI Application Performance Monitoring | Required for priority applications | APM domains by isolation model; size by application servers, spans, browser sessions, synthetic monitors/vantage points and retention. | Application teams instrument Java, .NET, PHP and APIs and provide service IDs, journeys and SLOs. |
| OCI Management Agent and Management Gateway | Required where hybrid collection applies | Agents per supported target and redundant gateways per disconnected/private network zone; include non-production and DR. | Distinct from OEM Management Agents. Validate proxy, ports, certificates, upgrade and failure-recovery procedures. |
| OCI Database Management | Conditional | Managed database/host count, deployment type, collection method, retention and administrative scope. | Database team supplies connectivity, credentials, privileges and commercial approval. |
| OCI Operations Insights | Conditional | Enabled database/host resources, historical capacity data, SQL insights scope and forecast horizon. | Database/OEM team validates prerequisites and operational use of findings. |
| OCI Notifications and Events | Required OCI O&M | Topics, subscriptions, event rules, endpoints, retry policy and regional/OPCO fan-out. | Used for governed notification and automation entry points; UA remains the incident-policy authority. |
| OCI Object Storage and Archive Storage | Required OCI O&M | Raw/evidence GB per day, 6-12 month retention by data class, lifecycle tiers, replay frequency, replication and retrieval expectations. | Apply residency, encryption, legal-hold and lifecycle rules before costing. |
| OCI Streaming and/or Queue | Conditional | Partition/throughput, message size, retention, consumer groups, backlog and replay requirements for routes needing buffering. | Include only where measured throughput or decoupling requirements exceed direct connector/function patterns. |
| OCI Generative AI project, Responses API and model inference | Required for the custom incident agent | One project per approved isolation/environment pattern; size by incidents, turns, input/output tokens, reasoning level, concurrency and one-month-plus evidence context. | OCI AI Team involvement (Alex Negrea) is required. Model/region, quota, retention, evaluation and residency must be accepted. |
| OCI Generative AI Conversations, Files and Vector Stores | Conditional agent capability | Conversation count/retention, runbook and evidence corpus size, vector-store growth, file ingestion and retrieval calls. | Include only the approved memory/RAG pattern; source provenance, deletion and access isolation are acceptance gates. |
| OCI API Gateway | Required for the governed tool plane | Private/approved public endpoints, requests, payload size, rate limits, custom domains, certificates and environment/region count. | Exposes only allowlisted UA, OCI, OEM/vendor, ServiceNow/CMDB-read and customer API contracts. |
| OCI Functions | Required for bounded API adapters | Function count, invocations, execution time, memory, concurrency, network access, retries and deployment environments. | CSS/partner develops schema validation, redaction and adapters. Read-only is default; mutations require approval and rollback evidence. |
| OCI IAM, Vault, Audit and Cloud Guard | Required security baseline | Compartments, groups/dynamic groups, policies, secrets/keys, rotation, audit retention, detector/target scope and OPCO isolation. | Observability & Security defines controls; product teams request least-privilege access to their resources. |
| Private networking, DNS, certificates and WAF where public exposure is approved | External dependency / conditional | Connectivity per OPCO and region, private endpoints, DRG/VPN/FastConnect capacity, DNS zones, certificates and WAF policies. | Network/security product teams provide these components. They are dependencies, not part of the OCI O&M service estimate. |

Reference configuration assumptions:

- Production and non-production are required; DR resources are duplicated in a second
  approved region only after service availability, residency and the stated RTO/RPO are
  validated.
- Retention is 6-12 months by data class, with searchable, analytical and archive tiers;
  at least one month of approved history is planned for AI use cases.
- All commercial quantities remain `TBD after discovery`; the Oracle Cloud Cost Estimator
  is evaluation guidance and the applicable Oracle quote/rate card is authoritative.

### Implementation and professional-services BOM

| Work package | Deliverable | Sizing / acceptance basis |
|---|---|---|
| Discovery and detailed design | Source inventory, volume/cardinality study, retention/residency classes, target architecture, security model and final commercial BOM. | All OPCOs and priority tools sampled; 2 TB/day and ticket-volume assumptions reconciled. |
| OCI observability foundation | Compartments, IAM, Vault, log groups, Monitoring, Logging, Connector Hub, Notifications, Object Storage and monitor-the-monitoring controls. | Infrastructure-as-code, least privilege, operational alarms and non-production validation. |
| Source onboarding and normalization | Supported agents/collectors, Log Analytics parsers, canonical IDs, enrichment, quality checks, replay and UA forwarding. | Priority interface catalogue; completeness, latency, duplicate and loss tests. |
| OKE and application observability | Kubernetes Monitoring Solution, APM/OpenTelemetry instrumentation, synthetic journeys, dashboards and SLO alarms. | Approved clusters and priority applications; trace continuity and failure-injection evidence. |
| OEM and native ServiceNow integration | OEM export/context mapping into UA and UA native ServiceNow Adapter workflow validation. | Operations (Pablo), OEM and ITSM acceptance; entitlement, idempotency, retry and outage-recovery tests. |
| Dashboards, alerts and runbooks | Group/OPCO views, alarm standards, suppression, maintenance windows, escalation policy and evidence links. | Versioned KPI/SLO catalogue and signed use-case acceptance. |
| Dedicated incident-commander agent | Responses API coordinator, governed RAG, API Gateway/Functions tools, citations, evidence package, guardrails, evaluation and approval UX. | OCI AI Team (Alex Negrea), CSS/qualified partner and Security acceptance; read-only PoV before any mutation discussion. |
| PoV, resilience and handover | Load, scale, HA/DR, security, data-residency and restore tests; runbooks, training, support and rollback package. | Signed acceptance metrics, four-hour RTO, five-to-fifteen-minute RPO and support/escalation readiness. |

## 8. Official Oracle references

- OCI Monitoring: https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm
- OCI Logging: https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm
- Connector Hub: https://docs.oracle.com/en-us/iaas/Content/connector-hub/overview.htm
- OCI Log Analytics: https://docs.oracle.com/en-us/iaas/log-analytics/doc/logging-analytics1.html
- Kubernetes Monitoring Solution: https://docs.oracle.com/en-us/iaas/log-analytics/doc/kubernetes-solution.html
- LoganAI: https://docs.oracle.com/en-us/iaas/log-analytics/doc/use-loganai.html
- LoganAI prerequisites: https://docs.oracle.com/en-us/iaas/log-analytics/doc/prerequisites-using-loganai.html
- OCI Application Performance Monitoring: https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm
- OCI Management Agent: https://docs.oracle.com/en-us/iaas/management-agents/home.htm
- OCI Database Management: https://docs.oracle.com/en-us/iaas/database-management/home.htm
- OCI Operations Insights: https://docs.oracle.com/en-us/iaas/operations-insights/home.htm
- OCI Notifications: https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm
- OCI Events: https://docs.oracle.com/en-us/iaas/Content/Events/home.htm
- Unified Assurance ServiceNow Adapter licensing: https://docs.oracle.com/en/industries/communications/unified-assurance/7.0/enterprise-licensing-info/licensing-information.html
- Enterprise Manager architecture: https://docs.oracle.com/en/enterprise-manager/cloud-control/enterprise-manager-cloud-control/13.5/emcon/enterprise-manager-architecture.html
- Enterprise Manager Management Pack licensing: https://docs.oracle.com/en/enterprise-manager/cloud-control/enterprise-manager-cloud-control/13.5/oemli/enterprise-database-management.html
- Building agents in OCI Generative AI: https://docs.oracle.com/en-us/iaas/Content/generative-ai/building-agents.htm
- OCI Responses API: https://docs.oracle.com/en-us/iaas/Content/generative-ai/responses-api.htm
- OCI API Gateway overview: https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayoverview.htm
- OCI Functions overview: https://docs.oracle.com/en-us/iaas/Content/Functions/Concepts/functionsoverview.htm
- Enterprise AI Agents in OCI Generative AI: https://docs.oracle.com/en-us/iaas/Content/generative-ai/agents.htm
- Estimating OCI monthly costs: https://docs.oracle.com/en-us/iaas/Content/Billing/Tasks/signingup_topic-Estimating_Costs.htm
