"""pysmoke-test entry point: load config, run checks, write JSON, upload to COS."""
import json
import logging
import sys
from datetime import datetime, timezone

import config
import cos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pysmoke-test")


def _append_history(tech, results_key, results, generated_at):
    day = generated_at[:10]
    history_key = f"monitoring-web/history/{tech}/{day}.json"

    events = cos.download_json(
        bucket=config.COS_BUCKET,
        object_key=history_key,
        endpoint=config.COS_ENDPOINT,
        access_key=config.COS_ACCESS_KEY_ID,
        secret_key=config.COS_SECRET_ACCESS_KEY,
        region=config.COS_REGION,
    )
    if not isinstance(events, list):
        events = []

    events.append({"ts": generated_at, results_key: results})

    cos.upload_json(
        events,
        bucket=config.COS_BUCKET,
        object_key=history_key,
        endpoint=config.COS_ENDPOINT,
        access_key=config.COS_ACCESS_KEY_ID,
        secret_key=config.COS_SECRET_ACCESS_KEY,
        region=config.COS_REGION,
    )
    log.info("Appended history event to s3://%s/%s (%d events)", config.COS_BUCKET, history_key, len(events))


def _write_and_upload(results, results_key, tech):
    previous = cos.download_json(
        bucket=config.COS_BUCKET,
        object_key=config.COS_OBJECT_KEY,
        endpoint=config.COS_ENDPOINT,
        access_key=config.COS_ACCESS_KEY_ID,
        secret_key=config.COS_SECRET_ACCESS_KEY,
        region=config.COS_REGION,
    )
    if isinstance(previous, dict) and previous.get(results_key) == results:
        log.info("No change since last run, skipping upload")
        return

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    payload = {
        "generated_at": generated_at,
        results_key: results,
    }

    with open(config.LOCAL_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("Wrote %s", config.LOCAL_OUTPUT_PATH)

    cos.upload(
        local_path=config.LOCAL_OUTPUT_PATH,
        bucket=config.COS_BUCKET,
        object_key=config.COS_OBJECT_KEY,
        endpoint=config.COS_ENDPOINT,
        access_key=config.COS_ACCESS_KEY_ID,
        secret_key=config.COS_SECRET_ACCESS_KEY,
        region=config.COS_REGION,
    )
    log.info("Uploaded to s3://%s/%s", config.COS_BUCKET, config.COS_OBJECT_KEY)

    _append_history(tech, results_key, results, generated_at)


def run_airflow():
    from airflow.airflow_check import check_all
    from instances import build_instances

    instances_config = config.load_instances_config()
    instances = build_instances(instances_config, config.ENV_LIST)
    log.info("Built %d instances", len(instances))

    results = check_all(instances, timeout=config.HTTP_TIMEOUT)
    _write_and_upload(results, "instances", "airflow")

    ko_count = sum(1 for r in results if r["error"] or not r["http"])
    log.info("Done: %d KO / %d total", ko_count, len(results))


def run_dags():
    from airflow.dags_check import check_all
    from instances import build_instances

    instances_config = config.load_instances_config()
    instances = build_instances(instances_config, config.ENV_LIST)
    log.info("Built %d instances", len(instances))

    auth = (config.AIRFLOW_DAG_USERNAME, config.AIRFLOW_DAG_PASSWORD)
    results = check_all(
        instances, auth,
        timeout=config.HTTP_TIMEOUT,
        queued_threshold_seconds=config.QUEUED_THRESHOLD_SECONDS,
    )
    _write_and_upload(results, "dags", "dags")

    ko_count = sum(1 for r in results if not r["ok"])
    log.info("Done: %d KO / %d total", ko_count, len(results))


def run_spark():
    from spark.spark_auth import get_spark_token
    from spark.spark_check import get_tenants

    token = get_spark_token(config.TARGET, timeout=config.HTTP_TIMEOUT)
    results = get_tenants(config.TARGET, token, config.ENV_LIST, timeout=config.HTTP_TIMEOUT)
    _write_and_upload(results, "tenants", "spark")

    ko_count = sum(1 for r in results if not r["all_healthy"])
    log.info("Done: %d KO / %d total", ko_count, len(results))


def main():
    log.info("Starting %s smoke tests (target=%s, env_list=%s)",
             config.SERVICE, config.TARGET, config.ENV_LIST)

    if config.SERVICE == "spark":
        run_spark()
    elif config.SERVICE == "dags":
        run_dags()
    else:
        run_airflow()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)
