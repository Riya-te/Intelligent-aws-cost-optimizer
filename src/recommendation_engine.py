
import json
import hashlib

from src.s3 import get_alert_history, save_alert_history
from src.notification import send_cost_alert
from src.ec2 import get_running_instances, get_cpu_metrics
from src.ebs import get_unattached_volumes
from src.eip import get_unused_elastic_ips
from src.snapshot import get_old_snapshots
from src.cost_explorer import analyze_cost_anomalies


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

LOW_CPU_THRESHOLD = 10.0
MAX_CPU_THRESHOLD = 40.0
MIN_DATAPOINTS = 24


# ---------------------------------------------------------
# EC2 UTILIZATION ANALYSIS
# ---------------------------------------------------------

def analyze_ec2_utilization(region_name=None, days=7):
    """
    Analyze running EC2 instances using CloudWatch CPU metrics.

    Generates recommendations only.
    Does not stop, resize, or modify EC2 instances.
    """

    recommendations = []

    instances = get_running_instances(region_name)

    for instance in instances:
        instance_id = instance["InstanceId"]

        try:
            metrics = get_cpu_metrics(
                instance_id,
                region_name=region_name,
                days=days
            )

            if metrics is None:
                recommendations.append({
                    "resource_id": instance_id,
                    "resource_name": instance["Name"],
                    "resource_type": "EC2",
                    "status": "insufficient_data",
                    "message": "No CloudWatch CPU metrics available.",
                    "action": "Collect more monitoring data."
                })
                continue

            average_cpu = metrics["AverageCPU"]
            maximum_cpu = metrics["MaximumCPU"]
            datapoints = metrics["DatapointCount"]

            if datapoints < MIN_DATAPOINTS:
                recommendations.append({
                    "resource_id": instance_id,
                    "resource_name": instance["Name"],
                    "resource_type": "EC2",
                    "status": "insufficient_data",
                    "average_cpu": average_cpu,
                    "maximum_cpu": maximum_cpu,
                    "datapoints": datapoints,
                    "message": (
                        f"Only {datapoints} hourly data points available. "
                        f"At least {MIN_DATAPOINTS} are required."
                    ),
                    "action": "Continue collecting CloudWatch metrics."
                })
                continue

            if (
                average_cpu < LOW_CPU_THRESHOLD
                and maximum_cpu < MAX_CPU_THRESHOLD
            ):
                recommendations.append({
                    "resource_id": instance_id,
                    "resource_name": instance["Name"],
                    "resource_type": "EC2",
                    "status": "potentially_underutilized",
                    "average_cpu": average_cpu,
                    "maximum_cpu": maximum_cpu,
                    "datapoints": datapoints,
                    "message": (
                        "EC2 instance shows consistently low CPU "
                        "utilization during the observation period."
                    ),
                    "action": (
                        "Review workload requirements and memory, "
                        "network and application metrics before "
                        "considering a smaller instance."
                    )
                })

        except Exception as error:
            recommendations.append({
                "resource_id": instance_id,
                "resource_name": instance.get("Name", instance_id),
                "resource_type": "EC2",
                "status": "analysis_error",
                "message": str(error),
                "action": "Check AWS permissions and CloudWatch access."
            })

    return recommendations


# ---------------------------------------------------------
# UNATTACHED EBS ANALYSIS
# ---------------------------------------------------------

def analyze_unattached_ebs(region_name=None):
    """
    Identify unattached EBS volumes that may incur
    ongoing storage charges.

    Does not delete or modify volumes.
    """

    recommendations = []

    try:
        volumes = get_unattached_volumes(region_name)

        for volume in volumes:
            recommendations.append({
                "resource_id": volume["VolumeId"],
                "resource_name": volume.get("Tags", {}).get(
                    "Name", volume["VolumeId"]
                ),
                "resource_type": "EBS",
                "status": "unattached_volume_review",
                "size_gb": volume["Size"],
                "volume_type": volume["VolumeType"],
                "availability_zone": volume["AvailabilityZone"],
                "encrypted": volume["Encrypted"],
                "message": (
                    "EBS volume is unattached and may still "
                    "incur storage charges."
                ),
                "action": (
                    "Review whether the volume is still required. "
                    "Check backup and retention requirements before "
                    "considering deletion."
                )
            })

    except Exception as error:
        recommendations.append({
            "resource_id": "EBS_SCAN",
            "resource_type": "EBS",
            "status": "analysis_error",
            "message": str(error),
            "action": "Check EC2 DescribeVolumes permissions."
        })

    return recommendations


# ---------------------------------------------------------
# UNUSED ELASTIC IP ANALYSIS
# ---------------------------------------------------------

def analyze_unused_elastic_ips(region_name=None):
    """
    Identify Elastic IPs that are not associated with resources.

    Does not release or modify Elastic IPs.
    """

    recommendations = []

    try:
        elastic_ips = get_unused_elastic_ips(region_name)

        for ip in elastic_ips:
            recommendations.append({
                "resource_id": (
                    ip.get("AllocationId") or ip.get("PublicIp")
                ),
                "resource_name": ip.get("PublicIp"),
                "resource_type": "Elastic IP",
                "status": "unused_elastic_ip_review",
                "public_ip": ip.get("PublicIp"),
                "allocation_id": ip.get("AllocationId"),
                "message": (
                    "Elastic IP is not associated with an AWS resource "
                    "and may incur unnecessary charges."
                ),
                "action": (
                    "Review whether this Elastic IP is still required. "
                    "Release it only after confirming it is no longer needed."
                )
            })

    except Exception as error:
        recommendations.append({
            "resource_id": "EIP_SCAN",
            "resource_type": "Elastic IP",
            "status": "analysis_error",
            "message": str(error),
            "action": "Check EC2 DescribeAddresses permissions."
        })

    return recommendations


# ---------------------------------------------------------
# OLD SNAPSHOT ANALYSIS
# ---------------------------------------------------------

def analyze_old_snapshots(region_name=None, days=30):
    """
    Identify old EBS snapshots for retention review.

    Does not delete snapshots.
    """

    recommendations = []

    try:
        snapshots = get_old_snapshots(
            days=days,
            region_name=region_name
        )

        for snapshot in snapshots:
            recommendations.append({
                "resource_id": snapshot["SnapshotId"],
                "resource_name": snapshot["SnapshotId"],
                "resource_type": "EBS Snapshot",
                "status": "old_snapshot_review",
                "volume_id": snapshot.get("VolumeId"),
                "size_gb": snapshot["VolumeSize"],
                "age_days": snapshot["AgeInDays"],
                "encrypted": snapshot["Encrypted"],
                "message": (
                    f"EBS snapshot is {snapshot['AgeInDays']} days old "
                    "and requires retention review."
                ),
                "action": (
                    "Review backup retention policies and recovery "
                    "requirements before considering deletion."
                )
            })

    except Exception as error:
        recommendations.append({
            "resource_id": "SNAPSHOT_SCAN",
            "resource_type": "EBS Snapshot",
            "status": "analysis_error",
            "message": str(error),
            "action": "Check EC2 DescribeSnapshots permissions."
        })

    return recommendations


# ---------------------------------------------------------
# AWS COST ANOMALY ANALYSIS
# ---------------------------------------------------------

def analyze_aws_cost_anomalies(
    days=30,
    baseline_days=14,
    percentage_threshold=50.0,
    standard_deviations=2.0,
    minimum_increase=1.0
):
    """
    Convert Cost Explorer anomaly findings into standard
    recommendation records.

    Missing billing data is reported separately.
    This function does not change AWS resources.
    """

    recommendations = []

    try:
        result = analyze_cost_anomalies(
            days=days,
            baseline_days=baseline_days,
            percentage_threshold=percentage_threshold,
            standard_deviations=standard_deviations,
            minimum_increase=minimum_increase
        )

        analysis_status = result.get("analysis_status", "completed")

        if analysis_status == "insufficient_data":
            recommendations.append({
                "resource_id": "COST_ANOMALY_ANALYSIS",
                "resource_name": "AWS Cost Explorer",
                "resource_type": "AWS Cost Anomaly",
                "status": "cost_anomaly_insufficient_data",
                "analysis_date": result.get("analysis_date"),
                "message": result.get(
                    "warning",
                    "Cost Explorer billing data is incomplete."
                ),
                "action": (
                    "Wait for billing data to become available, "
                    "then run the analysis again."
                )
            })

            return recommendations

        for anomaly in result.get("anomalies", []):

            service = anomaly["service"]

            recommendations.append({
                "resource_id": service,
                "resource_name": service,
                "resource_type": "AWS Cost Anomaly",
                "status": "cost_anomaly_detected",
                "service": service,
                "date": anomaly["date"],
                "currency": anomaly["currency"],
                "actual_cost": anomaly["actual_cost"],
                "baseline_average": anomaly["baseline_average"],
                "baseline_stddev": anomaly["baseline_stddev"],
                "increase": anomaly["increase"],
                "percentage_increase": anomaly[
                    "percentage_increase"
                ],
                "statistical_limit": anomaly["statistical_limit"],
                "message": anomaly["message"],
                "action": anomaly["action"]
            })

    except Exception as error:
        recommendations.append({
            "resource_id": "COST_ANOMALY_SCAN",
            "resource_name": "AWS Cost Explorer",
            "resource_type": "AWS Cost Anomaly",
            "status": "analysis_error",
            "message": str(error),
            "action": (
                "Check Cost Explorer API permissions, "
                "billing data availability and AWS configuration."
            )
        })

    return recommendations


# ---------------------------------------------------------
# RECOMMENDATION SUMMARY
# ---------------------------------------------------------

def get_recommendation_summary(recommendations):
    """Return counts grouped by recommendation status."""

    summary = {
        "potentially_underutilized": 0,
        "insufficient_data": 0,
        "unattached_volume_review": 0,
        "unused_elastic_ip_review": 0,
        "old_snapshot_review": 0,
        "cost_anomaly_detected": 0,
        "cost_anomaly_insufficient_data": 0,
        "analysis_error": 0,
        "total_recommendations": len(recommendations)
    }

    for recommendation in recommendations:
        status = recommendation.get("status")

        if status in summary and status != "total_recommendations":
            summary[status] += 1

    return summary


# ---------------------------------------------------------
# DUPLICATE-SAFE SNS NOTIFICATIONS
# ---------------------------------------------------------

def send_recommendation_notifications(recommendations):
    """
    Send SNS alerts for new or changed EC2 and cost anomaly findings.

    Uses S3 alert history and SHA256 fingerprints to suppress
    duplicate notifications.

    Saves alert history only after successful SNS publishing.
    """

    actionable = [
        item for item in recommendations
        if item.get("status") in (
            "potentially_underutilized",
            "cost_anomaly_detected"
        )
    ]

    if not actionable:
        return {
            "sent": False,
            "reason": "No actionable recommendations found.",
            "notified_instances": 0,
            "notified_cost_anomalies": 0,
            "notified_resources": 0
        }

    history = get_alert_history() or {}
    previous_alerts = history.get("alerts", {}) or {}

    new_alerts = []

    for item in actionable:

        resource_id = item.get("resource_id")

        if not resource_id:
            continue

        resource_type = item.get("resource_type", "Unknown")

        # Preserve existing EC2 history keys so previously
        # notified EC2 resources are not alerted again merely
        # because this feature was added.
        if resource_type == "EC2":
            alert_key = resource_id
        else:
            alert_key = f"{resource_type}:{resource_id}"

        fingerprint_data = {
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": item.get("status"),
            "action": item.get("action", "")
        }

        # Include the relevant measurements in the fingerprint.
        for field in (
            "average_cpu",
            "maximum_cpu",
            "actual_cost",
            "baseline_average",
            "increase",
            "percentage_increase",
            "date"
        ):
            if field in item:
                fingerprint_data[field] = item[field]

        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_data,
                sort_keys=True
            ).encode("utf-8")
        ).hexdigest()

        if previous_alerts.get(alert_key) != fingerprint:
            new_alerts.append(
                (item, alert_key, fingerprint)
            )

    if not new_alerts:
        return {
            "sent": False,
            "reason": "Duplicate alerts suppressed.",
            "notified_instances": 0,
            "notified_cost_anomalies": 0,
            "notified_resources": 0
        }

    ec2_count = sum(
        1 for item, _, _ in new_alerts
        if item.get("resource_type") == "EC2"
    )

    anomaly_count = sum(
        1 for item, _, _ in new_alerts
        if item.get("status") == "cost_anomaly_detected"
    )

    message = [
        "INTELLIGENT AWS COST OPTIMIZER",
        "COST OPTIMIZATION ALERT",
        "",
        f"New or changed findings: {len(new_alerts)}",
        f"EC2 findings: {ec2_count}",
        f"Cost anomalies: {anomaly_count}"
    ]

    for item, _, _ in new_alerts:

        message.extend([
            "",
            f"Resource type: {item.get('resource_type', 'Unknown')}",
            f"Resource ID: {item.get('resource_id', 'Unknown')}",
            f"Resource name: {item.get('resource_name', 'Unknown')}",
            f"Status: {item.get('status', 'Unknown')}",
            f"Finding: {item.get('message', '')}"
        ])

        if item.get("resource_type") == "EC2":

            message.extend([
                f"Average CPU: {item.get('average_cpu', 'N/A')}%",
                f"Maximum CPU: {item.get('maximum_cpu', 'N/A')}%",
                f"Datapoints: {item.get('datapoints', 'N/A')}"
            ])

        elif item.get("status") == "cost_anomaly_detected":

            message.extend([
                f"Analysis date: {item.get('date', 'N/A')}",
                (
                    f"Actual cost: {item.get('currency', '')} "
                    f"{item.get('actual_cost', 'N/A')}"
                ),
                (
                    f"Baseline average: {item.get('currency', '')} "
                    f"{item.get('baseline_average', 'N/A')}"
                ),
                f"Cost increase: {item.get('percentage_increase', 'N/A')}%"
            ])

        message.append(
            f"Recommended action: {item.get('action', '')}"
        )

    message.extend([
        "",
        "No AWS resources have been modified.",
        "Please review all recommendations before taking action."
    ])

    # Publish first. Do not update history if SNS publishing fails.
    response = send_cost_alert("\n".join(message))

    for item, alert_key, fingerprint in new_alerts:
        previous_alerts[alert_key] = fingerprint

    save_alert_history({
        "alerts": previous_alerts
    })

    return {
        "sent": True,
        "message_id": response.get("MessageId"),
        "notified_instances": ec2_count,
        "notified_cost_anomalies": anomaly_count,
        "notified_resources": len(new_alerts)
    }


# ---------------------------------------------------------
# COMPLETE RESOURCE ANALYSIS
# ---------------------------------------------------------

def analyze_all_resources(
    region_name=None,
    days=7,
    snapshot_days=30,
    cost_days=30,
    cost_baseline_days=14
):
    """
    Run all AWS resource and cost recommendation checks.

    Checks:
    1. EC2 utilization
    2. Unattached EBS volumes
    3. Unused Elastic IPs
    4. Old EBS snapshots
    5. AWS service cost anomalies

    Read-only analysis. No AWS resources are modified.
    """

    recommendations = []

    checks = [
        (
            "EC2",
            lambda: analyze_ec2_utilization(
                region_name=region_name,
                days=days
            )
        ),
        (
            "EBS",
            lambda: analyze_unattached_ebs(
                region_name=region_name
            )
        ),
        (
            "Elastic IP",
            lambda: analyze_unused_elastic_ips(
                region_name=region_name
            )
        ),
        (
            "EBS Snapshot",
            lambda: analyze_old_snapshots(
                region_name=region_name,
                days=snapshot_days
            )
        ),
        (
            "Cost Anomaly",
            lambda: analyze_aws_cost_anomalies(
                days=cost_days,
                baseline_days=cost_baseline_days
            )
        )
    ]

    for resource_type, check in checks:

        try:
            recommendations.extend(check())

        except Exception as error:
            recommendations.append({
                "resource_id": f"{resource_type.upper()}_SCAN",
                "resource_type": resource_type,
                "status": "analysis_error",
                "message": str(error),
                "action": (
                    "Review AWS permissions and scan configuration."
                )
            })

    return recommendations
