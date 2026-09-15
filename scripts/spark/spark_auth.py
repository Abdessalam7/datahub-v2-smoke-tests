"""Get a Spark API bearer token via Vault (ports Airflow's vault_helper.read_secret_and_get_token)."""
import hvac
import requests

import config


def get_spark_token(target, timeout=10):
    vault_client = hvac.Client(
        cert=(config.VAULT_CLIENT_CERT, config.VAULT_CLIENT_KEY),
        namespace=config.VAULT_NS,
        url=config.VAULT_URL,
    )
    vault_client.auth.cert.login()

    secret_path = f"secret/data/astronomer-a101731-aas/astronomer-a101731-dev-53d53716/cp-spark-{target}"
    secret = vault_client.read(path=secret_path)
    client_id = secret["data"]["data"]["client-id"]
    client_secret = secret["data"]["data"]["client-secret"]

    token_url = f"https://auth-{target}{config.BASE_DOMAIN}/auth/realms/ap27661/protocol/openid-connect/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "client_credentials",
    }
    response = requests.post(token_url, headers=headers, data=data, timeout=timeout)
    response.raise_for_status()
    return response.json()["access_token"]
