"""Runtime configuration: env vars + ConfigMap loader."""
import json
import os

TARGET = os.getenv("TARGET", "hprd")
ENV_LIST = [e.strip() for e in os.getenv("ENV_LIST", "dev,int,qual").split(",") if e.strip()]
SERVICE = os.getenv("SERVICE", "airflow")
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "10"))

INSTANCES_CONFIG_PATH = os.getenv("INSTANCES_CONFIG_PATH", "/etc/pysmoke-test/instances.json")
LOCAL_OUTPUT_PATH = os.getenv("LOCAL_OUTPUT_PATH", "/tmp/status.json")

COS_ENDPOINT = os.getenv("COS_ENDPOINT", "")
COS_BUCKET = os.getenv("COS_BUCKET_NAME", "")
COS_REGION = os.getenv("COS_REGION", "us-east-1")
COS_ACCESS_KEY_ID = os.getenv("COS_ACCESS_KEY_ID", "")
COS_SECRET_ACCESS_KEY = os.getenv("COS_SECRET_ACCESS_KEY", "")
COS_OBJECT_KEY = os.getenv("COS_OBJECT_KEY", f"monitoring-web/input/{SERVICE}/status.json")

BASE_DOMAIN = ".data.cloud.net.intra"

# Spark (Vault mTLS + OIDC client-credentials, mirrors the Airflow vault_helper)
VAULT_NS = os.getenv("VAULT_NS", "")
VAULT_URL = os.getenv("VAULT_URL", "")
VAULT_CLIENT_CERT = os.getenv("VAULT_CLIENT_CERT", "/client-cert/tls.crt")
VAULT_CLIENT_KEY = os.getenv("VAULT_CLIENT_KEY", "/client-cert/tls.key")
EXCLUDED_CLUSTERS = [c.strip() for c in os.getenv("EXCLUDED_CLUSTERS", "").split(",") if c.strip()]


def load_instances_config():
    with open(INSTANCES_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
