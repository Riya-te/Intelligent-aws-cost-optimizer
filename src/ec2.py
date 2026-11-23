
import boto3
from botocore.exceptions import ClientError, BotoCoreError
from datetime import datetime, timedelta, timezone


# ---------------- AWS SESSION ----------------

def get_aws_session():
    return boto3.Session(
        profile_name="new-account",
        region_name="ap-south-1"
    )


# ---------------- EC2 CLIENT ----------------

def get_ec2_client(region_name=None):
    session = get_aws_session()

    return session.client(
        "ec2",
        region_name=region_name or "ap-south-1"
    )


# ---------------- GET ALL INSTANCES ----------------

def get_all_instances(region_name=None):

    ec2 = get_ec2_client(region_name)

    try:
        paginator = ec2.get_paginator("describe_instances")
        instances = []

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
                        "AvailabilityZone": instance["Placement"]["AvailabilityZone"],
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


# ---------------- STOPPED INSTANCES ----------------

def get_stopped_instances(region_name=None):

    instances = get_all_instances(region_name)

    return [
        instance for instance in instances
        if instance["State"] == "stopped"
    ]


# ---------------- RUNNING INSTANCES ----------------

def get_running_instances(region_name=None):

    instances = get_all_instances(region_name)

    return [
        instance for instance in instances
        if instance["State"] == "running"
    ]


# ---------------- CLOUDWATCH CPU METRICS ----------------

def get_cpu_utilization(instance_id, region_name=None, days=7):

    session = get_aws_session()

    cloudwatch = session.client(
        "cloudwatch",
        region_name=region_name or "ap-south-1"
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
            Statistics=["Average"]
        )

        datapoints = response.get("Datapoints", [])

        if not datapoints:
            return None

        average_cpu = sum(
            point["Average"] for point in datapoints
        ) / len(datapoints)

        return round(average_cpu, 2)

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve CPU metrics for {instance_id}: {error}"
        ) from error
