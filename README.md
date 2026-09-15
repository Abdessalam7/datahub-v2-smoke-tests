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

## Before deploying from this copy

- `scripts/cos.py`, `scripts/instances.py`, and `scripts/airflow/airflow_check.py`
  should be diffed against the internal GitLab `pysmoke-test` repo before
  relying on them here.
- `requirements.txt` versions should be reconciled with the real pinned
  versions if they differ.
