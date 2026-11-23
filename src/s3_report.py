
import json
from datetime import datetime, timezone
from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client

BUCKET_NAME = "intelligent-aws-cost-reports-642615934978"


def upload_report(report_data):
    """Upload a JSON cost report to S3."""

    s3 = get_client("s3")

    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d-%H-%M-%S"
    )

    file_name = f"reports/cost-report-{timestamp}.json"

    try:
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=file_name,
            Body=json.dumps(report_data, indent=4, default=str),
            ContentType="application/json",
            ServerSideEncryption="AES256"
        )

        print(f"Report uploaded successfully: {file_name}")
        return file_name

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to upload report: {error}"
        ) from error


def get_latest_report():
    """Retrieve the latest JSON report from S3."""

    s3 = get_client("s3")

    try:
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix="reports/"
        )

        objects = response.get("Contents", [])

        if not objects:
            return None

        latest = max(objects, key=lambda obj: obj["LastModified"])

        result = s3.get_object(
            Bucket=BUCKET_NAME,
            Key=latest["Key"]
        )

        return json.loads(result["Body"].read().decode("utf-8"))

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve report: {error}"
        ) from error
