"""Probe every DAG on an Airflow instance and flag ones stuck queued past a threshold.

Only the latest dagRun per DAG is fetched (no task-instance/SLA data) — "delayed"
here means "scheduled to start, still queued after N seconds", the queued-too-long
pattern this check exists for, not an Airflow SLA miss.
"""
import logging
from datetime import datetime, timezone

import requests

log = logging.getLogger("pysmoke-test.dags")

API_BASE = "/api/v1"
PAGE_SIZE = 100


def _get(url, auth, timeout, params=None):
    response = requests.get(url, auth=auth, timeout=timeout, params=params)
    response.raise_for_status()
    return response.json()


def _list_dags(base_url, auth, timeout):
    """Return [(dag_id, is_paused), ...] for every DAG, paginating past PAGE_SIZE."""
    dags = []
    offset = 0
    while True:
        data = _get(
            f"{base_url}{API_BASE}/dags", auth, timeout,
            params={"limit": PAGE_SIZE, "offset": offset},
        )
        page = data.get("dags", [])
        dags.extend((d["dag_id"], d.get("is_paused", False)) for d in page)
        offset += len(page)
        if not page or offset >= data.get("total_entries", 0):
            break
    return dags


def _latest_run(base_url, dag_id, auth, timeout):
    data = _get(
        f"{base_url}{API_BASE}/dags/{dag_id}/dagRuns", auth, timeout,
        params={"limit": 1, "order_by": "-execution_date"},
    )
    runs = data.get("dag_runs", [])
    return runs[0] if runs else None


def _is_delayed(run, queued_threshold_seconds):
    if not run or run.get("state") != "queued" or not run.get("execution_date"):
        return False
    scheduled_at = datetime.fromisoformat(run["execution_date"].replace("Z", "+00:00"))
    age = (datetime.now(timezone.utc) - scheduled_at).total_seconds()
    return age > queued_threshold_seconds


def _empty_row(instance, **overrides):
    row = {
        "business_line": instance["business_line"],
        "env": instance["env"],
        "url": instance["url"],
        "dag_id": None,
        "is_paused": None,
        "state": None,
        "execution_date": None,
        "start_date": None,
        "delayed": False,
        "ok": True,
        "error": None,
    }
    row.update(overrides)
    return row


def check_instance(instance, auth, timeout=10, queued_threshold_seconds=600):
    """Probe every DAG on one Airflow instance. Rows are self-contained and appended
    immediately — nothing from this instance's raw API responses is kept afterward.
    """
    base_url = f"https://{instance['url']}.data.cloud.net.intra"

    try:
        dags = _list_dags(base_url, auth, timeout)
    except requests.RequestException as e:
        log.warning("Failed to list DAGs for %s: %s", instance["url"], e)
        return [_empty_row(instance, ok=False, error=str(e))]

    log.info("%s (%s): %d dags found, fetching latest run for each", instance["url"], instance["business_line"], len(dags))

    rows = []
    for i, (dag_id, is_paused) in enumerate(dags, start=1):
        if i % 20 == 0:
            log.info("%s: %d/%d dags checked", instance["url"], i, len(dags))
        if is_paused:
            rows.append(_empty_row(instance, dag_id=dag_id, is_paused=True))
            continue

        try:
            run = _latest_run(base_url, dag_id, auth, timeout)
        except requests.RequestException as e:
            rows.append(_empty_row(instance, dag_id=dag_id, is_paused=False, ok=False, error=str(e)))
            continue

        state = run.get("state") if run else None
        delayed = _is_delayed(run, queued_threshold_seconds)
        rows.append(_empty_row(
            instance, dag_id=dag_id, is_paused=False,
            state=state,
            execution_date=run.get("execution_date") if run else None,
            start_date=run.get("start_date") if run else None,
            delayed=delayed,
            ok=(state != "failed" and not delayed),
        ))

    return rows


def check_all(instances, auth, timeout=10, queued_threshold_seconds=600):
    results = []
    for i, instance in enumerate(instances, start=1):
        log.info("[%d/%d] Checking %s (%s/%s)", i, len(instances), instance["url"], instance["business_line"], instance["env"])
        rows = check_instance(instance, auth, timeout=timeout, queued_threshold_seconds=queued_threshold_seconds)
        ko = sum(1 for r in rows if not r["ok"])
        log.info("[%d/%d] Done %s: %d dags, %d KO", i, len(instances), instance["url"], len(rows), ko)
        results.extend(rows)
    return results
