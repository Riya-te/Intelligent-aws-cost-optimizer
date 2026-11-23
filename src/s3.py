import json
import os
from datetime import timezone
from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client


def get_s3_client():
    """Create an S3 client using the configured AWS session."""
    return get_client("s3")


def get_all_buckets():
    """Retrieve S3 buckets and their configuration details."""
    s3 = get_s3_client()

    try:
        response = s3.list_buckets()
        buckets = []

        for bucket in response.get("Buckets", []):
            bucket_name = bucket["Name"]

            bucket_info = {
                "BucketName": bucket_name,
                "CreationDate": bucket["CreationDate"].isoformat(),
                "Region": None,
                "Versioning": "Unknown",
                "Encryption": "Unknown"
            }

            # Check bucket region
            try:
                location = s3.get_bucket_location(
                    Bucket=bucket_name
                )
                bucket_info["Region"] = (
                    location.get("LocationConstraint") or "us-east-1"
                )
            except ClientError:
                pass

            # Check versioning
            try:
                versioning = s3.get_bucket_versioning(
                    Bucket=bucket_name
                )
                bucket_info["Versioning"] = (
                    versioning.get("Status", "Disabled")
                )
            except ClientError:
                pass

            # Check encryption
            try:
                encryption = s3.get_bucket_encryption(
                    Bucket=bucket_name
                )
                rules = encryption.get(
                    "ServerSideEncryptionConfiguration", {}
                ).get("Rules", [])

                algorithms = [
                    rule.get(
                        "ApplyServerSideEncryptionByDefault", {}
                    ).get("SSEAlgorithm")
                    for rule in rules
                ]

                bucket_info["Encryption"] = (
                    ", ".join(filter(None, algorithms)) or "Unknown"
                )

            except ClientError as error:
                error_code = error.response.get(
                    "Error", {}
                ).get("Code")

                if error_code == "ServerSideEncryptionConfigurationNotFoundError":
                    bucket_info["Encryption"] = "Not configured"
                elif error_code in ("AccessDenied", "403"):
                    bucket_info["Encryption"] = "Access denied"

            buckets.append(bucket_info)

        return buckets

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve S3 buckets: {error}"
        ) from error


def get_bucket_count():
    """Return the total number of S3 buckets."""
    return len(get_all_buckets())

# S3-based notification history

ALERT_STATE_BUCKET = os.getenv(
    "ALERT_STATE_BUCKET",
    "intelligent-aws-cost-reports-642615934978"
)

ALERT_STATE_KEY = "alert-history/recommendation-alert-state.json"


def get_alert_history():
    """
    Retrieve previously stored recommendation alert history from S3.
    Returns an empty dictionary if no history exists yet.
    """

    s3 = get_s3_client()

    try:
        response = s3.get_object(
            Bucket=ALERT_STATE_BUCKET,
            Key=ALERT_STATE_KEY
        )

        content = response["Body"].read().decode("utf-8")

        return json.loads(content)

    except ClientError as error:
        error_code = error.response.get(
            "Error", {}
        ).get("Code")

        if error_code in ("NoSuchKey", "404", "NotFound"):
            return {}

        raise RuntimeError(
            f"Unable to retrieve alert history: {error}"
        ) from error

    except (BotoCoreError, json.JSONDecodeError) as error:
        raise RuntimeError(
            f"Unable to process alert history: {error}"
        ) from error


def save_alert_history(history):
    """
    Save recommendation alert history in S3.
    """

    if not isinstance(history, dict):
        raise ValueError("Alert history must be a dictionary.")

    s3 = get_s3_client()

    try:
        s3.put_object(
            Bucket=ALERT_STATE_BUCKET,
            Key=ALERT_STATE_KEY,
            Body=json.dumps(history, indent=4).encode("utf-8"),
            ContentType="application/json"
        )

        return True

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to save alert history: {error}"
        ) from error