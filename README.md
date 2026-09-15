# datahub-v2-smoke-tests

Smoke tests for Datahub v2 services (Airflow, Spark). Collects health/status per
client instance and uploads a JSON snapshot to IBM COS at
`monitoring-web/input/<SERVICE>/status.json`, consumed by
[datahub-v2-web-ui](https://github.com/Abdessalam7/datahub-v2-web-ui).

## Layout

```
scripts/
  main.py            entry point: dispatches on SERVICE env var
  config.py          env-var driven runtime config
  cos.py             S3/COS upload helper
  instances.py       builds the Airflow instance list from the ConfigMap JSON
  utils.py           standalone JSON/status helpers (not currently wired into main.py)
  airflow/
    airflow_check.py probes Airflow's /api/v1/health per instance
  spark/
    spark_auth.py    Vault mTLS + OIDC client-credentials token exchange
    spark_check.py   lists Spark clusters/tenants and maps them to the web app schema
```

Run with `SERVICE=airflow` (default) or `SERVICE=spark`, plus `TARGET`/`ENV_LIST`
matching the target environment split (e.g. `TARGET=hprd ENV_LIST=dev,int,qual` or
`TARGET=prod ENV_LIST=prod,pprd`). Spark also needs `VAULT_NS`, `VAULT_URL`, and a
client certificate mounted at `/client-cert/tls.crt` / `/client-cert/tls.key`
(see `config.py` for all env vars and defaults).

## Provenance note

This repo was assembled from a mix of sources during a design/implementation
session with Claude, alongside screenshots of the real production files:

- **Verified against the real file (screenshots)**: `scripts/config.py`,
  `scripts/main.py`, `scripts/utils.py`.
- **Authored for this session, targeting the real repo structure**:
  `scripts/spark/spark_auth.py`, `scripts/spark/spark_check.py`.
- **Reconstructed, not verified against the real file** — high confidence since
  their call signatures match the verified `main.py`/`config.py` exactly, but
  worth diffing against your actual GitLab `pysmoke-test` repo before relying on
  them: `scripts/cos.py`, `scripts/instances.py`, `scripts/airflow/airflow_check.py`.
- `requirements.txt` is inferred (`requests`, `boto3`, `hvac`) — merge with your
  real pinned versions if they differ.

Diff the reconstructed files against the real GitLab repo before deploying from
this copy.
