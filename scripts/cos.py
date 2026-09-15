"""Upload/download helpers for IBM COS (S3-compatible)."""
import json

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError


def _client(endpoint, access_key, secret_key, region="us-east-1"):
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4"),
    )


def upload(local_path, bucket, object_key, endpoint, access_key, secret_key, region="us-east-1"):
    s3 = _client(endpoint, access_key, secret_key, region)
    s3.upload_file(
        Filename=local_path,
        Bucket=bucket,
        Key=object_key,
        ExtraArgs={"ContentType": "application/json"},
    )


def upload_json(data, bucket, object_key, endpoint, access_key, secret_key, region="us-east-1"):
    s3 = _client(endpoint, access_key, secret_key, region)
    s3.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=json.dumps(data, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def download_json(bucket, object_key, endpoint, access_key, secret_key, region="us-east-1"):
    s3 = _client(endpoint, access_key, secret_key, region)
    try:
        resp = s3.get_object(Bucket=bucket, Key=object_key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404"):
            return None
        raise
    return json.loads(resp["Body"].read().decode("utf-8"))
