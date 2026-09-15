"""Probe SparkaaS tenants and produce results matching the web app schema.

Ports get_sparkaas_instances / get_spark_tenants from the Airflow DAG
(spark_health_tasks.py), swapping xcom-passed values for direct calls.
"""
import logging

import requests

import config

log = logging.getLogger("pysmoke-test.spark")


def get_cluster_names(target, token, timeout=10):
    url = f"https://spark-cp-{target}{config.BASE_DOMAIN}/api/spark/v1/instances"
    headers = {"accept": "*/*", "Authorization": f"Bearer {token}"}

    response = requests.get(url, headers=headers, timeout=timeout)
    if not response.ok:
        log.warning("Spark instances HTTP %s: %s", response.status_code, response.text)
        return []

    instances = response.json()
    return [i["clusterName"] for i in instances if i["clusterName"] not in config.EXCLUDED_CLUSTERS]


def get_tenants(target, token, env_list, timeout=10):
    """Return tenants for `target`, filtered to `env_list`, in the web app schema."""
    cluster_names = get_cluster_names(target, token, timeout=timeout)
    log.info("Found %d Spark clusters (target=%s)", len(cluster_names), target)

    url = f"https://spark-cp-{target}{config.BASE_DOMAIN}/api/spark/v1/tenants"
    headers = {"accept": "*/*", "Authorization": f"Bearer {token}"}

    extracted_tenants = []
    for cluster_name in cluster_names:
        try:
            response = requests.get(url, params={"clusterName": cluster_name}, headers=headers, timeout=timeout)
            if not response.ok:
                log.warning("Spark tenants HTTP %s for cluster %s: %s", response.status_code, cluster_name, response.text)
                continue
            for tenant in response.json():
                extracted_tenants.append({
                    "display_name": tenant.get("displayName", ""),
                    "business_line": tenant.get("client", ""),
                    "environment": tenant.get("env", ""),
                    "ibm_account": tenant.get("ibmAccountId", ""),
                    "cluster_name": tenant.get("clusterName", ""),
                    "sparkaas_version": tenant.get("sparkaasVersion", ""),
                    "health_status": tenant.get("health", ""),
                    "sync_status": tenant.get("syncStatus", ""),
                    "spark_ui_url": tenant.get("sparkUiUrl", ""),
                    "tenant_name": tenant.get("tenantName", ""),
                    "sparkaas_doc": tenant.get("versionDocumentations", ""),
                    "is_deprecated_version": tenant.get("versionDeprecated", False),
                    "deprecated_msg": tenant.get("versionDeprecationMessage", ""),
                    "all_healthy": tenant.get("allHealthy", False),
                })
        except requests.RequestException as e:
            log.warning("Error fetching tenants for cluster %s: %s", cluster_name, e)

    tenants = [_to_web_schema(t) for t in extracted_tenants]
    return [t for t in tenants if t["env"] in env_list]


def _to_web_schema(tenant):
    """Map a Spark tenant to the schema monitoring-web-ui expects.

    "global_status" has no equivalent field in the Spark API response,
    so it is left null instead of being guessed.
    """
    return {
        "business_line": tenant["business_line"],
        "env": tenant["environment"],
        "tenant_name": tenant["tenant_name"],
        "status": tenant["health_status"],
        "sync_argo": tenant["sync_status"],
        "global_status": None,
        "all_healthy": tenant["all_healthy"],
        "version": tenant["sparkaas_version"],
        "deprecated": tenant["is_deprecated_version"],
        "ibm_account": tenant["ibm_account"],
        "iks_cluster": tenant["cluster_name"],
    }
