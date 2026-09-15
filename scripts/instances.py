"""Build the flat list of instances to probe from the ConfigMap JSON.

The JSON is the raw airflowctl_inst_list_json variable from Airflow,
which is a flat array of instance objects.
"""


def build_instances(instances_config, env_list):
    """
    Walk the airflowctl_inst_list_json array and return a flat list of dicts:
        [{"business_line": ..., "env": ..., "url": ..., "version": ...}, ...]
    Filtered on env_list.
    """
    instances = []
    for item in instances_config:
        env = item.get("env", "")
        if env not in env_list:
            continue

        # url field already comes as "astronomer-xxx-env-uid.data.cloud.net.intra"
        # we strip the domain to keep only the slug, matching the existing JSON format
        full_url = item.get("url", "")
        url_slug = full_url.replace("https://", "").replace(".data.cloud.net.intra", "")

        instances.append({
            "business_line": item.get("customer", {}).get("name", "unknown"),
            "env": env,
            "url": url_slug,
            "version": item.get("version", "x.y.z"),
        })
    return instances
