# KB & Workflow Ingestion — Sanitize by Construction

This pack ships **reusable knowledge only** — generalized fixes, command shapes,
and workflows. It must **never** contain real tenancy data. This is the contract
for adding any KB entry or workflow, especially knowledge *mined from a real
project or live tenancy* (e.g. distilled from another `~/dev` repo's `KB.md`).

> **The rule:** distill the *pattern*, not the *instance*. A reader in any
> tenancy must be able to apply it; nothing may fingerprint the account it came
> from. If a value identifies a specific tenancy, compartment, host, user, or
> resource, replace it with a `<PLACEHOLDER>` token before it lands here.

## What counts as tenancy data (replace every one)

| Class | Real → | Use instead | Enforced by |
|---|---|---|---|
| OCIDs | `ocid1.<type>.oc1…` | `<COMPARTMENT_OCID>`, `<OKE_CLUSTER_OCID>`, … | `redact.py` (gate) |
| Public / private IPs | routable or `10.x`/`172.16-31`/`192.168` | `<LB_PUBLIC_IP>`, `<WORKER_PRIV_IP>` | `redact.py --strict` |
| API-key fingerprint | `aa:bb:…:ff` | `<API_KEY_FINGERPRINT>` | `redact.py` (gate) |
| Install / data keys, auth tokens | `isk_…`, base64 datakeys, PEM blocks | `<APM_PRIVATE_DATAKEY>`, `<INSTALL_KEY>` | `redact.py` (gate) |
| Tenancy / OCIR namespace | bare token after `<region>.ocir.io/` | `<region>.ocir.io/<namespace>/`, `${OCIR_TENANCY}` | `redact.py` (gate, `ocir_namespace`) |
| Email (PII) | a real person's address | `<EMAIL>`, or an `example.com` address | `redact.py` (gate, allowlists example.com/noreply) |
| **Compartment / cluster / bucket names** | `prod-logging`, `octo-…-oke` | `<COMPARTMENT_NAME>`, `<OKE_CLUSTER_NAME>` | **this contract** (regex can't tell a real name from a generic word) |
| **Region as identity** | a single home region that pins the account | keep only if generic to the fix; else `<REGION>` | **this contract** |
| **MQL / LQL dimension *values*** | real metric dimensions, entity names, principals | generic placeholders or the *shape* only | **this contract** |
| **Profile names** | `~/.oci/config` profile that names an account | `<PROFILE>` / a named context like `dev` | **this contract** |

The bottom four classes are **not regex-detectable** — a real compartment name
looks like any other word. The gate cannot catch them; this contract and human
review are the only control. When in doubt, generalize.

## Ingestion procedure

1. **Distill.** Rewrite the fix as a tenancy-agnostic pattern: symptom → root
   cause → fix, in terms any reader can apply. Drop the war story.
2. **Placeholder every tenant specific.** Walk the table above top to bottom.
   Replace OCIDs/IPs/namespaces/keys/emails *and* the human-judgement classes
   (names, regions, dimension values, profiles).
3. **Cite an official Oracle doc.** Every `## KB-<n>` entry must carry a
   `**See:**` line linking a `docs.oracle.com` page, and that URL must be
   registered in [oracle-docs.md](oracle-docs.md). No citation → not admissible.
   (Enforced by `tests/test_doc_links.py`.)
4. **Run the gate before committing.**
   ```bash
   python3 scripts/redact.py --check <file>            # exit 0 required
   python3 scripts/redact.py --strict --summary <file> # also surfaces RFC1918 topology
   python3 -m pytest -q                                # doc-link + KB-citation lint
   ```
5. **Review for the un-catchable classes.** Re-read the entry asking: *does any
   word here name a specific tenancy, compartment, cluster, host, person, or
   metric?* If yes, generalize it. The gate will not save you here.

## KB entry shape

Append from the next number (`grep '^## KB-' references/KB.md | tail -1`):

```markdown
## KB-<n> — <generalized title> (<domain-tag>)
**Symptom:** <what the reader observes, no tenant specifics>
**Root cause:** <the general mechanism>
**Fix:** <commands with `<PLACEHOLDER>` tokens; run mutations via run_action>
**See:** [<official page>](<docs.oracle.com URL registered in oracle-docs.md>)
```

Use an existing `<domain-tag>` (`iam`, `security`, `observability-db`,
`networking-compute`, `cost`, `log-analytics`, `resource-manager`,
`events-functions`) so `scripts/kb_lookup.py "<symptom>" <tag>` finds it.

## Why this matters

The pack's entire premise is "ships no OCIDs/IPs/secrets" — it is installed into
other people's tenancies. One leaked namespace or compartment name fingerprints
the source account and breaks that promise. The redaction gate is the backstop
for secret-shaped values; this contract is the control for everything that looks
like ordinary text but still identifies a tenancy.
