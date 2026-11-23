
from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client



def get_ec2_client(region_name=None):
    """Create an EC2 client using the shared AWS session."""
    return get_client("ec2", region_name=region_name)


    return get_client("ec2")


def get_all_volumes(region_name=None):
    """Retrieve EBS volumes with pagination."""
    ec2 = get_ec2_client(region_name)

    try:
        paginator = ec2.get_paginator("describe_volumes")
        volumes = []

        for page in paginator.paginate():
            for volume in page.get("Volumes", []):
                volumes.append({
                    "VolumeId": volume["VolumeId"],
                    "Size": volume["Size"],
                    "State": volume["State"],
                    "VolumeType": volume["VolumeType"],
                    "AvailabilityZone": volume["AvailabilityZone"],
                    "CreateTime": volume["CreateTime"].isoformat(),
                    "Encrypted": volume.get("Encrypted", False),
                    "SnapshotId": volume.get("SnapshotId"),
                    "Iops": volume.get("Iops"),
                    "Tags": {
                        tag["Key"]: tag["Value"]
                        for tag in volume.get("Tags", [])
                    }
                })

        return volumes

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve EBS volumes: {error}"
        ) from error


def get_unattached_volumes(region_name=None):
    """Identify EBS volumes not attached to an EC2 instance."""
    volumes = get_all_volumes(region_name)

    return [
        volume for volume in volumes
        if volume["State"] == "available"
    ]


def calculate_unattached_storage(volumes):
    """Calculate total unattached EBS storage in GB."""
    return sum(volume["Size"] for volume in volumes)
