
from datetime import datetime, timezone

from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client


def get_ec2_client(region_name=None):
    """Create an EC2 client using the configured AWS session."""
    return get_client("ec2", region_name=region_name)


def get_all_snapshots(region_name=None):
    """Retrieve all EBS snapshots owned by your AWS account."""
    ec2 = get_ec2_client(region_name)

    try:
        paginator = ec2.get_paginator("describe_snapshots")
        snapshots = []

        for page in paginator.paginate(OwnerIds=["self"]):
            for snapshot in page.get("Snapshots", []):
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


def get_old_snapshots(days=30, region_name=None):
    """Identify snapshots older than the specified number of days."""
    if days < 0:
        raise ValueError("days cannot be negative")

    now = datetime.now(timezone.utc)
    old_snapshots = []

    for snapshot in get_all_snapshots(region_name):
        start_time = datetime.fromisoformat(snapshot["StartTime"])
        age = (now - start_time).days

        if age > days:
            snapshot["AgeInDays"] = age
            old_snapshots.append(snapshot)

    return old_snapshots
