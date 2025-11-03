import os
import boto3
from botocore.exceptions import ClientError
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def s3_client():
    return boto3.client("s3", region_name=os.getenv("AWS_REGION"))

def upload_fileobj_to_s3(fileobj, bucket, key, extra_args=None):
    client = s3_client()
    extra_args = extra_args or {}
    try:
        client.upload_fileobj(fileobj, bucket, key, ExtraArgs=extra_args)
    except ClientError as e:
        logger.exception("S3 upload failed")
        raise
    return f"s3://{bucket}/{key}"

def get_s3_object(bucket, key):
    client = s3_client()
    return client.get_object(Bucket=bucket, Key=key)

def download_s3_text(bucket, key):
    obj = get_s3_object(bucket, key)
    return obj["Body"].read().decode("utf-8")
