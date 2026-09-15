"""pysmoke-test entry point: load config, run checks, write JSON, upload to COS."""
import json
import logging
import sys
from datetime import datetime, timezone

import config
import cos

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pysmoke-test")


def _write_and_upload(results, results_key):
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
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


def run_airflow():
    from airflow.airflow_check import check_all
    from instances import build_instances

    instances_config = config.load_instances_config()
    instances = build_instances(instances_config, config.ENV_LIST)
    log.info("Built %d instances", len(instances))

    results = check_all(instances, timeout=config.HTTP_TIMEOUT)
    _write_and_upload(results, "instances")

    ko_count = sum(1 for r in results if r["error"] or not r["http"])
    log.info("Done: %d KO / %d total", ko_count, len(results))


def run_spark():
    from spark.spark_auth import get_spark_token
    from spark.spark_check import get_tenants

    token = get_spark_token(config.TARGET, timeout=config.HTTP_TIMEOUT)
    results = get_tenants(config.TARGET, token, config.ENV_LIST, timeout=config.HTTP_TIMEOUT)
    _write_and_upload(results, "tenants")

    ko_count = sum(1 for r in results if not r["all_healthy"])
    log.info("Done: %d KO / %d total", ko_count, len(results))


def main():
    log.info("Starting %s smoke tests (target=%s, env_list=%s)",
             config.SERVICE, config.TARGET, config.ENV_LIST)

    if config.SERVICE == "spark":
        run_spark()
    else:
        run_airflow()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log.exception("Fatal error")
        sys.exit(1)
