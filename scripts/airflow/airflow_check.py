"""Probe Airflow /api/v1/health and produce a result matching the web app schema."""
import requests


HEALTH_PATH = "/api/v1/health"
BASE_DOMAIN = ".data.cloud.net.intra"


def check(instance, timeout=10):
    """
    Probe one instance and return a dict in the format expected by the web app:
        {
            "business_line", "env", "url", "version",
            "http", "dag_processor", "scheduler", "trigger", "meta_db",
            "error"
        }
    """
    result = {
        "business_line": instance["business_line"],
        "env": instance["env"],
        "url": instance["url"],
        "version": instance["version"],
        "http": False,
        "dag_processor": False,
        "scheduler": False,
        "trigger": False,
        "meta_db": False,
        "error": None,
    }

    full_url = f"https://{instance['url']}{BASE_DOMAIN}{HEALTH_PATH}"

    try:
        r = requests.get(full_url, timeout=timeout)
        result["http"] = r.ok
        if not r.ok:
            result["error"] = f"HTTP {r.status_code}"
            return result

        data = r.json()
        result["scheduler"] = _is_healthy(data, "scheduler")
        result["dag_processor"] = _is_healthy(data, "dag_processor")
        result["trigger"] = _is_healthy(data, "triggerer")
        result["meta_db"] = _is_healthy(data, "metadatabase")

    except Exception as e:
        result["error"] = str(e)

    return result


def _is_healthy(data, key):
    return data.get(key, {}).get("status", "").lower() == "healthy"


def check_all(instances, timeout=10):
    return [check(i, timeout=timeout) for i in instances]
