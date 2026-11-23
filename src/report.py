
from datetime import datetime, timezone

from src.ec2 import get_stopped_instances
from src.ebs import get_unattached_volumes
from src.snapshot import get_old_snapshots
from src.eip import get_unused_elastic_ips
from src.s3 import get_all_buckets
from src.rds import get_all_rds_instances
from src.recommendation_engine import analyze_all_resources


AWS_REGION = "ap-south-1"


# ---------------------------------------------------------
# COLLECT REPORT DATA
# ---------------------------------------------------------

def collect_report_data():
    """
    Collect AWS resource inventories, CPU metrics,
    cost anomaly findings and unified recommendations.
    """

    recommendations = []

    # -----------------------------------------------------
    # AWS RESOURCE INVENTORY
    # -----------------------------------------------------

    stopped = get_stopped_instances()
    volumes = get_unattached_volumes()
    snapshots = get_old_snapshots()
    eips = get_unused_elastic_ips()
    buckets = get_all_buckets()
    databases = get_all_rds_instances()

    # -----------------------------------------------------
    # UNIFIED RECOMMENDATION ENGINE
    # -----------------------------------------------------

    try:
        all_resource_analysis = analyze_all_resources(
            region_name=AWS_REGION,
            days=7,
            snapshot_days=30,
            cost_days=30,
            cost_baseline_days=14
        )

    except Exception as error:
        all_resource_analysis = [{
            "resource_id": "RESOURCE_SCAN",
            "resource_type": "AWS",
            "status": "analysis_error",
            "message": str(error),
            "action": (
                "Check AWS permissions and scan configuration."
            )
        }]

    # -----------------------------------------------------
    # EXTRACT EC2 ANALYSIS
    # -----------------------------------------------------

    cpu_analysis = [
        item
        for item in all_resource_analysis
        if item.get("resource_type") == "EC2"
    ]

    # -----------------------------------------------------
    # EXTRACT COST ANOMALY ANALYSIS
    # -----------------------------------------------------

    cost_analysis = [
        item
        for item in all_resource_analysis
        if item.get("resource_type") == "AWS Cost Anomaly"
    ]

    detected_anomalies = [
        item
        for item in cost_analysis
        if item.get("status") == "cost_anomaly_detected"
    ]

    cost_data_warnings = [
        item
        for item in cost_analysis
        if item.get("status") == "cost_anomaly_insufficient_data"
    ]

    # -----------------------------------------------------
    # PRESERVE STOPPED EC2 RECOMMENDATIONS
    # -----------------------------------------------------

    for instance in stopped:
        recommendations.append(
            f"Review stopped EC2 instance "
            f"{instance['InstanceId']}. "
            "Attached EBS volumes may still incur charges."
        )

    # -----------------------------------------------------
    # ACTIONABLE FINDINGS
    # -----------------------------------------------------

    actionable_statuses = {
        "potentially_underutilized",
        "unattached_volume_review",
        "unused_elastic_ip_review",
        "old_snapshot_review",
        "cost_anomaly_detected"
    }

    for item in all_resource_analysis:

        if item.get("status") in actionable_statuses:

            recommendations.append(
                f"{item.get('resource_type')} "
                f"{item.get('resource_id')}: "
                f"{item.get('message')} "
                f"Recommended action: {item.get('action')}"
            )

    # -----------------------------------------------------
    # RESOURCE COUNTS
    # -----------------------------------------------------

    underutilized_count = sum(
        1 for item in all_resource_analysis
        if item.get("status") == "potentially_underutilized"
    )

    insufficient_data_count = sum(
        1 for item in cpu_analysis
        if item.get("status") == "insufficient_data"
    )

    analysis_error_count = sum(
        1 for item in all_resource_analysis
        if item.get("status") == "analysis_error"
    )

    unattached_ebs_count = sum(
        1 for item in all_resource_analysis
        if item.get("status") == "unattached_volume_review"
    )

    unused_eip_count = sum(
        1 for item in all_resource_analysis
        if item.get("status") == "unused_elastic_ip_review"
    )

    old_snapshot_count = sum(
        1 for item in all_resource_analysis
        if item.get("status") == "old_snapshot_review"
    )

    # -----------------------------------------------------
    # COST ANOMALY COUNTS
    # -----------------------------------------------------

    cost_anomaly_count = len(detected_anomalies)

    cost_insufficient_data_count = len(cost_data_warnings)

    # -----------------------------------------------------
    # FINAL REPORT DATA
    # -----------------------------------------------------

    return {
        "project": "Intelligent AWS Cost Optimizer",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "region": AWS_REGION,

        "summary": {
            "stopped_ec2": len(stopped),
            "unattached_ebs": len(volumes),
            "old_snapshots": len(snapshots),
            "unused_elastic_ips": len(eips),
            "s3_buckets": len(buckets),
            "rds_instances": len(databases),

            "underutilized_ec2": underutilized_count,
            "ec2_metrics_insufficient": insufficient_data_count,

            "unattached_ebs_recommendations": unattached_ebs_count,
            "unused_eip_recommendations": unused_eip_count,
            "old_snapshot_recommendations": old_snapshot_count,

            "cost_anomalies": cost_anomaly_count,
            "cost_anomaly_insufficient_data": (
                cost_insufficient_data_count
            ),

            "analysis_errors": analysis_error_count,

            "recommendations": len(recommendations)
        },

        "resources": {
            "stopped_ec2": stopped,
            "unattached_ebs": volumes,
            "old_snapshots": snapshots,
            "unused_elastic_ips": eips,
            "s3_buckets": buckets,
            "rds_instances": databases,

            "ec2_cpu_analysis": cpu_analysis,

            "cost_anomaly_analysis": cost_analysis,

            "resource_recommendations": all_resource_analysis
        },

        "recommendations": recommendations
    }


# ---------------------------------------------------------
# GENERATE TEXT REPORT
# ---------------------------------------------------------

def generate_report(data=None):
    """
    Generate a readable AWS cost optimization report.

    Accepts previously collected report data to avoid
    running AWS scans more than once.
    """

    if data is None:
        data = collect_report_data()

    report = []

    report.append("=" * 75)
    report.append(
        "       INTELLIGENT AWS COST OPTIMIZATION REPORT"
    )
    report.append("=" * 75)

    report.append(f"Generated At: {data['generated_at']}")
    report.append(f"Region: {data['region']}")

    # -----------------------------------------------------
    # RESOURCE INVENTORY SECTIONS
    # -----------------------------------------------------

    sections = [
        (
            "STOPPED EC2 INSTANCES",
            data["resources"]["stopped_ec2"]
        ),
        (
            "UNATTACHED EBS VOLUMES",
            data["resources"]["unattached_ebs"]
        ),
        (
            "OLD EBS SNAPSHOTS",
            data["resources"]["old_snapshots"]
        ),
        (
            "UNUSED ELASTIC IP ADDRESSES",
            data["resources"]["unused_elastic_ips"]
        ),
        (
            "S3 BUCKETS",
            data["resources"]["s3_buckets"]
        ),
        (
            "RDS DATABASE INSTANCES",
            data["resources"]["rds_instances"]
        )
    ]

    for title, resources in sections:

        report.append(f"\n{title}")
        report.append("-" * 75)

        if not resources:
            report.append("No resources found.")
            continue

        for resource in resources:
            report.append(str(resource))

    # -----------------------------------------------------
    # EC2 CPU UTILIZATION ANALYSIS
    # -----------------------------------------------------

    report.append("\nEC2 CPU UTILIZATION ANALYSIS")
    report.append("-" * 75)

    cpu_analysis = data["resources"]["ec2_cpu_analysis"]

    if not cpu_analysis:
        report.append(
            "No running EC2 instances available for analysis."
        )

    for item in cpu_analysis:

        report.append(
            f"\nInstance: {item.get('resource_id', 'N/A')}"
        )

        report.append(
            f"Status: {item.get('status', 'unknown')}"
        )

        if "average_cpu" in item:
            report.append(
                f"Average CPU: {item['average_cpu']}%"
            )

        if "maximum_cpu" in item:
            report.append(
                f"Maximum CPU: {item['maximum_cpu']}%"
            )

        report.append(
            f"Details: {item.get('message', 'No additional details')}"
        )

        report.append(
            f"Action: {item.get('action', 'No action specified')}"
        )

    # -----------------------------------------------------
    # AWS COST ANOMALY ANALYSIS
    # -----------------------------------------------------

    report.append("\nAWS COST ANOMALY ANALYSIS")
    report.append("-" * 75)

    cost_analysis = data["resources"].get(
        "cost_anomaly_analysis", []
    )

    detected_anomalies = [
        item for item in cost_analysis
        if item.get("status") == "cost_anomaly_detected"
    ]

    insufficient_data = [
        item for item in cost_analysis
        if item.get("status") == "cost_anomaly_insufficient_data"
    ]

    cost_errors = [
        item for item in cost_analysis
        if item.get("status") == "analysis_error"
    ]

    report.append(
        f"Detected Anomalies: {len(detected_anomalies)}"
    )

    if detected_anomalies:

        for index, item in enumerate(detected_anomalies, 1):

            report.append(f"\nAnomaly #{index}")

            report.append(
                f"Service: {item.get('service', item.get('resource_name', 'N/A'))}"
            )

            report.append(
                f"Analysis Date: {item.get('date', 'N/A')}"
            )

            report.append(
                f"Actual Cost: "
                f"{item.get('currency', '')} "
                f"{item.get('actual_cost', 'N/A')}"
            )

            report.append(
                f"Historical Daily Average: "
                f"{item.get('currency', '')} "
                f"{item.get('baseline_average', 'N/A')}"
            )

            report.append(
                f"Cost Increase: "
                f"{item.get('increase', 'N/A')} "
                f"{item.get('currency', '')}"
            )

            report.append(
                f"Percentage Increase: "
                f"{item.get('percentage_increase', 'N/A')}%"
            )

            report.append(
                f"Statistical Threshold: "
                f"{item.get('statistical_limit', 'N/A')}"
            )

            report.append(
                f"Details: {item.get('message', 'N/A')}"
            )

            report.append(
                f"Recommended Action: "
                f"{item.get('action', 'N/A')}"
            )

    else:
        report.append(
            "No cost anomalies crossed the configured thresholds."
        )

    if insufficient_data:

        report.append("\nBILLING DATA WARNINGS")

        for item in insufficient_data:

            report.append(
                f"Warning: {item.get('message', 'Billing data unavailable.')}"
            )

            report.append(
                f"Action: {item.get('action', 'Retry the analysis later.')}"
            )

    if cost_errors:

        report.append("\nCOST ANALYSIS ERRORS")

        for item in cost_errors:

            report.append(
                f"Error: {item.get('message', 'Unknown error')}"
            )

            report.append(
                f"Action: {item.get('action', 'Check AWS configuration.')}"
            )

    # -----------------------------------------------------
    # COST OPTIMIZATION RECOMMENDATIONS
    # -----------------------------------------------------

    report.append("\nCOST OPTIMIZATION RECOMMENDATIONS")
    report.append("-" * 75)

    if data["recommendations"]:

        for index, recommendation in enumerate(
            data["recommendations"], 1
        ):
            report.append(
                f"{index}. {recommendation}"
            )

    else:
        report.append(
            "No immediate resource-level recommendations found."
        )

    # -----------------------------------------------------
    # RESOURCE SUMMARY
    # -----------------------------------------------------

    report.append("\nRESOURCE SUMMARY")
    report.append("-" * 75)

    for key, value in data["summary"].items():
        report.append(f"{key}: {value}")

    # -----------------------------------------------------
    # REPORT FOOTER
    # -----------------------------------------------------

    report.append("\n" + "=" * 75)

    report.append(
        "All findings are recommendations only. "
        "No AWS resources were modified."
    )

    report.append("END OF REPORT")
    report.append("=" * 75)

    return "\n".join(report)


# ---------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":

    try:
        report_data = collect_report_data()

        generated_report = generate_report(report_data)

        print(generated_report)

    except Exception as error:

        print("Report generation failed:", error)
        raise
