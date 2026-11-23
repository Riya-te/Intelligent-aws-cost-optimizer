
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
