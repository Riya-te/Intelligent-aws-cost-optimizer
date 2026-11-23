
from datetime import datetime, timezone
from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client


def get_ec2_client():
    """Create an EC2 client using the configured AWS session."""
    return get_client("ec2")


def get_all_snapshots():
    """Retrieve all EBS snapshots owned by your AWS account."""
    ec2 = get_ec2_client()

    try:
        response = ec2.describe_snapshots(OwnerIds=["self"])
        snapshots = []

        for snapshot in response.get("Snapshots", []):
            snapshots.append({
                "SnapshotId": snapshot["SnapshotId"],
                "VolumeId": snapshot.get("VolumeId"),
                "StartTime": snapshot["StartTime"].isoformat(),
                "State": snapshot["State"],
                "VolumeSize": snapshot["VolumeSize"],
                "Description": snapshot.get("Description", ""),
                "Encrypted": snapshot.get("Encrypted", False)
            })

        return snapshots

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve EBS snapshots: {error}"
        ) from error


def get_old_snapshots(days=30):
    """Identify snapshots older than the specified number of days."""
    now = datetime.now(timezone.utc)
    old_snapshots = []

    for snapshot in get_all_snapshots():
        start_time = datetime.fromisoformat(snapshot["StartTime"])
        age = (now - start_time).days

        if age > days:
            snapshot["AgeInDays"] = age
            old_snapshots.append(snapshot)

    return old_snapshots
