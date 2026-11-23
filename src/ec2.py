
from datetime import datetime, timedelta, timezone

from botocore.exceptions import ClientError, BotoCoreError

from src.aws_session import get_client


DEFAULT_REGION = "ap-south-1"


def get_ec2_client(region_name=None):
    """Return an EC2 client using the shared AWS session."""
    return get_client("ec2", region_name or DEFAULT_REGION)


def get_all_instances(region_name=None):
    """Retrieve all EC2 instances with their basic details."""

    ec2 = get_ec2_client(region_name)
    instances = []

    try:
        paginator = ec2.get_paginator("describe_instances")

        for page in paginator.paginate():
            for reservation in page.get("Reservations", []):
                for instance in reservation.get("Instances", []):

                    tags = {
                        tag["Key"]: tag["Value"]
                        for tag in instance.get("Tags", [])
                    }

                    instances.append({
                        "InstanceId": instance["InstanceId"],
                        "Name": tags.get("Name", "Unnamed"),
                        "State": instance["State"]["Name"],
                        "InstanceType": instance["InstanceType"],
                        "AvailabilityZone": instance.get(
                            "Placement", {}
                        ).get("AvailabilityZone"),
                        "LaunchTime": instance["LaunchTime"].isoformat(),
                        "Platform": instance.get(
                            "PlatformDetails", "Linux/UNIX"
                        ),
                        "Tags": tags
                    })

        return instances

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve EC2 instances: {error}"
        ) from error


def get_stopped_instances(region_name=None):
    """Return stopped EC2 instances."""
    return [
        instance
        for instance in get_all_instances(region_name)
        if instance["State"] == "stopped"
    ]


def get_running_instances(region_name=None):
    """Return running EC2 instances."""
    return [
        instance
        for instance in get_all_instances(region_name)
        if instance["State"] == "running"
    ]


def get_cpu_metrics(instance_id, region_name=None, days=7):
    """
    Retrieve and summarize EC2 CPU utilization from CloudWatch.

    Returns average, minimum, maximum and number of data points.
    Returns None when no metrics are available.
    """

    cloudwatch = get_client(
        "cloudwatch",
        region_name or DEFAULT_REGION
    )

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)

    try:
        response = cloudwatch.get_metric_statistics(
            Namespace="AWS/EC2",
            MetricName="CPUUtilization",
            Dimensions=[
                {
                    "Name": "InstanceId",
                    "Value": instance_id
                }
            ],
            StartTime=start_time,
            EndTime=end_time,
            Period=3600,
            Statistics=["Average", "Minimum", "Maximum"]
        )

        datapoints = response.get("Datapoints", [])

        if not datapoints:
            return None

        average_values = [
            point["Average"] for point in datapoints
        ]

        return {
            "InstanceId": instance_id,
            "AverageCPU": round(
                sum(average_values) / len(average_values), 2
            ),
            "MinimumCPU": round(
                min(point["Minimum"] for point in datapoints), 2
            ),
            "MaximumCPU": round(
                max(point["Maximum"] for point in datapoints), 2
            ),
            "DatapointCount": len(datapoints),
            "PeriodHours": 1,
            "ObservationDays": days
        }

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve CPU metrics for {instance_id}: {error}"
        ) from error


def get_cpu_utilization(instance_id, region_name=None, days=7):
    """
    Backward-compatible function.

    Returns average CPU utilization as a float,
    or None when CloudWatch has no metrics.
    """

    metrics = get_cpu_metrics(
        instance_id,
        region_name=region_name,
        days=days
    )

    if metrics is None:
        return None

    return metrics["AverageCPU"]
