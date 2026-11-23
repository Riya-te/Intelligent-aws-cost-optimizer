
from datetime import datetime, timezone
from src.ec2 import get_stopped_instances
from src.ebs import get_unattached_volumes
from src.snapshot import get_old_snapshots
from src.eip import get_unused_elastic_ips
from src.s3 import get_all_buckets
from src.rds import get_all_rds_instances


def collect_report_data():
    """Collect AWS resources and generate recommendations."""

    recommendations = []

    stopped = get_stopped_instances()
    volumes = get_unattached_volumes()
    snapshots = get_old_snapshots()
    eips = get_unused_elastic_ips()
    buckets = get_all_buckets()
    databases = get_all_rds_instances()

    for instance in stopped:
        recommendations.append(
            f"Review stopped EC2 instance {instance['InstanceId']}. "
            "Attached EBS volumes may still incur charges."
        )

    for volume in volumes:
        recommendations.append(
            f"Review unattached EBS volume {volume['VolumeId']} "
            f"({volume['Size']} GB) before deletion."
        )

    for snapshot in snapshots:
        recommendations.append(
            f"Review snapshot {snapshot['SnapshotId']} "
            "for backup retention requirements."
        )

    for ip in eips:
        recommendations.append(
            f"Review unused Elastic IP {ip['PublicIp']} "
            "for release if no longer required."
        )

    return {
        "project": "Intelligent AWS Cost Optimizer",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "region": "ap-south-1",
        "summary": {
            "stopped_ec2": len(stopped),
            "unattached_ebs": len(volumes),
            "old_snapshots": len(snapshots),
            "unused_elastic_ips": len(eips),
            "s3_buckets": len(buckets),
            "rds_instances": len(databases),
            "recommendations": len(recommendations)
        },
        "resources": {
            "stopped_ec2": stopped,
            "unattached_ebs": volumes,
            "old_snapshots": snapshots,
            "unused_elastic_ips": eips,
            "s3_buckets": buckets,
            "rds_instances": databases
        },
        "recommendations": recommendations
    }


def generate_report():
    """Generate a readable text report."""

    data = collect_report_data()
    report = []

    report.append("=" * 75)
    report.append("       INTELLIGENT AWS COST OPTIMIZATION REPORT")
    report.append("=" * 75)
    report.append(f"Generated At: {data['generated_at']}")
    report.append(f"Region: {data['region']}")

    sections = [
        ("STOPPED EC2 INSTANCES", data["resources"]["stopped_ec2"]),
        ("UNATTACHED EBS VOLUMES", data["resources"]["unattached_ebs"]),
        ("OLD EBS SNAPSHOTS", data["resources"]["old_snapshots"]),
        ("UNUSED ELASTIC IP ADDRESSES", data["resources"]["unused_elastic_ips"]),
        ("S3 BUCKETS", data["resources"]["s3_buckets"]),
        ("RDS DATABASE INSTANCES", data["resources"]["rds_instances"])
    ]

    for title, resources in sections:
        report.append(f"\n{title}")
        report.append("-" * 75)

        if not resources:
            report.append("No resources found.")
            continue

        for resource in resources:
            report.append(str(resource))

    report.append("\nCOST OPTIMIZATION RECOMMENDATIONS")
    report.append("-" * 75)

    if data["recommendations"]:
        for index, recommendation in enumerate(
            data["recommendations"], 1
        ):
            report.append(f"{index}. {recommendation}")
    else:
        report.append("No immediate resource-level recommendations found.")

    report.append("\n" + "=" * 75)
    report.append("END OF REPORT")
    report.append("=" * 75)

    return "\n".join(report)


if __name__ == "__main__":
    print(generate_report())
