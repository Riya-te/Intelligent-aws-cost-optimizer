import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import json
from datetime import datetime, timezone

import boto3
import pandas as pd
import plotly.express as px
import streamlit as st

from src.aws_session import get_session, get_client


# ============================================================
# CONFIGURATION
# ============================================================

BUCKET_NAME = "intelligent-aws-cost-reports-642615934978"
AWS_REGION = "ap-south-1"

st.set_page_config(
    page_title="Intelligent AWS Cost Optimizer",
    page_icon="☁️",
    layout="wide"
)


# ============================================================
# PAGE DESIGN AND SIDEBAR
# ============================================================

st.title("☁️ Intelligent AWS Cost Optimizer")
st.caption("AWS Resource Monitoring & Cost Optimization Platform")

st.sidebar.title("☁️ AWS Optimizer")

page = st.sidebar.radio(
    "Navigation",
    [
        "Overview",
        "AWS Resources",
        "Cost Recommendations",
        "Reports & Downloads"
    ]
)

st.sidebar.divider()

mode = st.sidebar.radio(
    "Select Data Source",
    [
        "Demo Mode",
        "Live AWS Mode",
        "Latest Lambda Report"
    ]
)

st.sidebar.divider()
st.sidebar.info(f"AWS Region: {AWS_REGION}")

if st.sidebar.button("🔄 Refresh / Scan Resources", use_container_width=True):
    st.rerun()


# ============================================================
# AWS ACCOUNT CONNECTION
# ============================================================

def get_aws_identity():
    """Get AWS identity using the configured shared session."""

    session = get_session()
    sts = session.client("sts")

    identity = sts.get_caller_identity()

    return {
        "account_id": identity["Account"],
        "arn": identity["Arn"],
        "region": session.region_name
    }


# ============================================================
# DEMO DATA
# ============================================================

def get_demo_data():

    return {
        "ec2": [
            {
                "InstanceId": "i-demo001",
                "State": "stopped",
                "InstanceType": "t2.micro",
                "AvailabilityZone": "ap-south-1a"
            },
            {
                "InstanceId": "i-demo002",
                "State": "running",
                "InstanceType": "t3.small",
                "AvailabilityZone": "ap-south-1b"
            },
            {
                "InstanceId": "i-demo003",
                "State": "stopped",
                "InstanceType": "t3.micro",
                "AvailabilityZone": "ap-south-1a"
            }
        ],

        "ebs": [
            {
                "VolumeId": "vol-demo001",
                "Size": 30,
                "VolumeType": "gp3"
            },
            {
                "VolumeId": "vol-demo002",
                "Size": 50,
                "VolumeType": "gp2"
            }
        ],

        "eip": [
            {"PublicIp": "203.0.113.10"},
            {"PublicIp": "203.0.113.20"}
        ],

        "snapshots": [
            {
                "SnapshotId": "snap-demo001",
                "AgeInDays": 120
            },
            {
                "SnapshotId": "snap-demo002",
                "AgeInDays": 95
            }
        ],

        "s3": [
            {"BucketName": "demo-backup-bucket"},
            {"BucketName": "demo-storage-bucket"}
        ],

        "rds": [
            {
                "DBInstanceIdentifier": "demo-database",
                "Engine": "mysql",
                "Status": "available"
            }
        ]
    }


# ============================================================
# LIVE AWS RESOURCE SCANNING
# ============================================================

def get_live_data():

    from src.ec2 import get_all_instances
    from src.ebs import get_unattached_volumes
    from src.eip import get_unused_elastic_ips
    from src.snapshot import get_old_snapshots
    from src.s3 import get_all_buckets
    from src.rds import get_all_rds_instances

    return {
        "ec2": get_all_instances(),
        "ebs": get_unattached_volumes(),
        "eip": get_unused_elastic_ips(),
        "snapshots": get_old_snapshots(),
        "s3": get_all_buckets(),
        "rds": get_all_rds_instances()
    }


# ============================================================
# S3 LAMBDA REPORT FUNCTIONS
# ============================================================

def get_s3_report_history():
    """Retrieve all JSON reports stored in the S3 reports folder."""

    s3 = get_client("s3")

    reports = []

    paginator = s3.get_paginator("list_objects_v2")

    for page in paginator.paginate(
        Bucket=BUCKET_NAME,
        Prefix="reports/"
    ):

        for obj in page.get("Contents", []):

            if obj["Key"].endswith(".json"):

                reports.append(obj)

    return sorted(
        reports,
        key=lambda obj: obj["LastModified"],
        reverse=True
    )


def get_lambda_report(report_key):
    """Retrieve and parse a specific Lambda report."""

    s3 = get_client("s3")

    response = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=report_key
    )

    return json.loads(
        response["Body"].read().decode("utf-8")
    )


def get_latest_lambda_report():
    """Retrieve the newest Lambda report."""

    reports = get_s3_report_history()

    if not reports:
        return None

    return get_lambda_report(reports[0]["Key"])


def normalize_lambda_report(report):
    """Convert Lambda report structure into dashboard format."""

    resources = report.get("resources", {})

    return {
        "ec2": resources.get("stopped_ec2", []),
        "ebs": resources.get("unattached_ebs", []),
        "eip": resources.get("unused_elastic_ips", []),
        "snapshots": resources.get("old_snapshots", []),
        "s3": resources.get("s3_buckets", []),
        "rds": resources.get("rds_instances", [])
    }


# ============================================================
# LOAD SELECTED DATA SOURCE
# ============================================================

identity = None
lambda_report = None
report_key = None

try:

    if mode == "Demo Mode":

        data = get_demo_data()

        st.warning(
            "DEMO MODE: These are illustrative sample records, "
            "not actual AWS resources."
        )

    elif mode == "Live AWS Mode":

        with st.spinner("Connecting to AWS and scanning resources..."):

            identity = get_aws_identity()
            data = get_live_data()

        st.success("Successfully connected to your AWS account!")

        col1, col2, col3 = st.columns(3)

        col1.metric("AWS Account", identity["account_id"])
        col2.metric("AWS Region", identity["region"])
        col3.metric(
            "Resources Found",
            sum(len(resources) for resources in data.values())
        )

        st.caption(f"Connected identity: {identity['arn']}")

    else:

        with st.spinner("Loading latest automated report from S3..."):

            reports = get_s3_report_history()

            if not reports:
                st.warning("No Lambda reports found in your S3 bucket.")
                st.stop()

            report_key = reports[0]["Key"]
            lambda_report = get_lambda_report(report_key)

            data = normalize_lambda_report(lambda_report)

        st.success("Latest Lambda report loaded successfully from S3!")

        st.caption(
            f"Report: {report_key.split('/')[-1]}"
        )

        st.caption(
            f"Generated at: {lambda_report.get('generated_at', 'Unknown')}"
        )

        st.caption(
            f"Region: {lambda_report.get('region', 'Unknown')}"
        )

        st.info(
            "Lambda report contains stopped EC2 instances, "
            "not the complete EC2 inventory."
        )

except Exception as error:

    st.error(f"Data loading failed: {error}")
    st.stop()


# ============================================================
# RESOURCE VARIABLES
# ============================================================

ec2 = data["ec2"]
ebs = data["ebs"]
eip = data["eip"]
snapshots = data["snapshots"]
s3_buckets = data["s3"]
rds = data["rds"]

resource_mapping = {
    "EC2": ec2,
    "EBS": ebs,
    "Elastic IP": eip,
    "Snapshots": snapshots,
    "S3": s3_buckets,
    "RDS": rds
}

resource_counts = {
    "EC2": len(ec2),
    "Unattached EBS": len(ebs),
    "Unused Elastic IP": len(eip),
    "Old Snapshots": len(snapshots),
    "S3 Buckets": len(s3_buckets),
    "RDS Databases": len(rds)
}


# ============================================================
# GENERATE RECOMMENDATIONS
# ============================================================

recommendations = []

for instance in ec2:

    if instance.get("State") == "stopped":

        recommendations.append({
            "Resource": instance.get("InstanceId", "EC2"),
            "Issue": "Stopped EC2 instance",
            "Recommendation": (
                "Review the instance and its attached EBS storage."
            )
        })


for volume in ebs:

    recommendations.append({
        "Resource": volume.get("VolumeId", "EBS"),
        "Issue": "Unattached EBS volume",
        "Recommendation": (
            "Check whether the volume is required before deletion."
        )
    })


for ip in eip:

    recommendations.append({
        "Resource": ip.get("PublicIp", "Elastic IP"),
        "Issue": "Potentially unused Elastic IP",
        "Recommendation": (
            "Verify usage and release if no longer required."
        )
    })


for snapshot in snapshots:

    recommendations.append({
        "Resource": snapshot.get("SnapshotId", "Snapshot"),
        "Issue": "Old EBS snapshot",
        "Recommendation": (
            "Review backup and retention requirements."
        )
    })


# ============================================================
# OVERVIEW PAGE
# ============================================================

if page == "Overview":

    st.subheader("📊 Resource Overview")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "EC2 Instances" if mode != "Latest Lambda Report"
        else "Stopped EC2",
        len(ec2)
    )

    c2.metric("Unattached EBS", len(ebs))
    c3.metric("Unused Elastic IPs", len(eip))
    c4.metric("Old Snapshots", len(snapshots))

    c5, c6 = st.columns(2)

    c5.metric("S3 Buckets", len(s3_buckets))
    c6.metric("RDS Databases", len(rds))

    if mode == "Latest Lambda Report":

        summary = lambda_report.get("summary", {})

        st.divider()
        st.subheader("☁️ Automated Lambda Scan Summary")

        summary_columns = st.columns(3)

        for index, (key, value) in enumerate(summary.items()):

            summary_columns[index % 3].metric(
                key.replace("_", " ").title(),
                value
            )

    st.divider()

    st.subheader("📈 AWS Resource Analysis")

    resource_df = pd.DataFrame({
        "Resource": list(resource_counts.keys()),
        "Count": list(resource_counts.values())
    })

    left, right = st.columns(2)

    with left:

        fig = px.bar(
            resource_df,
            x="Resource",
            y="Count",
            title="AWS Resource Inventory",
            color="Resource"
        )

        st.plotly_chart(fig, width="stretch")

    with right:

        if ec2:

            ec2_df = pd.DataFrame(ec2)

            if "State" in ec2_df.columns:

                state_counts = (
                    ec2_df["State"]
                    .value_counts()
                    .rename_axis("State")
                    .reset_index(name="Count")
                )

                fig2 = px.pie(
                    state_counts,
                    names="State",
                    values="Count",
                    title="EC2 Instance Status",
                    hole=0.4
                )

                st.plotly_chart(fig2, width="stretch")

            else:

                st.info("EC2 state information is unavailable.")

        else:

            st.info("No EC2 instances available for status analysis.")

    st.divider()

    st.subheader("💡 Recommendation Summary")

    if recommendations:

        st.warning(
            f"{len(recommendations)} resource review recommendations found."
        )

        st.dataframe(
            pd.DataFrame(recommendations),
            width="stretch"
        )

    else:

        st.success("No immediate resource-level recommendations found.")


# ============================================================
# AWS RESOURCES PAGE
# ============================================================

elif page == "AWS Resources":

    st.subheader("🔍 AWS Resource Details")

    tabs = st.tabs([
        "EC2",
        "EBS",
        "Elastic IP",
        "Snapshots",
        "S3",
        "RDS"
    ])

    resource_groups = [
        ec2,
        ebs,
        eip,
        snapshots,
        s3_buckets,
        rds
    ]

    for tab, resources in zip(tabs, resource_groups):

        with tab:

            if resources:

                st.dataframe(
                    pd.DataFrame(resources),
                    width="stretch"
                )

            else:

                st.info("No resources found.")


# ============================================================
# COST RECOMMENDATIONS PAGE
# ============================================================

elif page == "Cost Recommendations":

    st.subheader("💡 Cost Optimization Recommendations")

    st.caption(
        "Recommendations identify resources for review. "
        "No resources are automatically deleted or modified."
    )

    if recommendations:

        st.metric(
            "Review Candidates",
            len(recommendations)
        )

        recommendation_df = pd.DataFrame(recommendations)

        st.dataframe(
            recommendation_df,
            width="stretch"
        )

        st.download_button(
            "⬇️ Download Recommendations CSV",
            data=recommendation_df.to_csv(index=False),
            file_name="cost_optimization_recommendations.csv",
            mime="text/csv"
        )

    else:

        st.success("No immediate resource-level recommendations found.")

    st.divider()

    st.subheader("Resource Review Summary")

    st.dataframe(
        pd.DataFrame([
            {"Resource": key, "Count": value}
            for key, value in resource_counts.items()
        ]),
        width="stretch"
    )

    st.info(
        "This project currently provides resource-level recommendations. "
        "It does not yet calculate actual AWS billing costs or verified savings."
    )


# ============================================================
# REPORTS AND DOWNLOADS PAGE
# ============================================================

elif page == "Reports & Downloads":

    st.subheader("📄 Reports & Downloads")

    report = [
        "INTELLIGENT AWS COST OPTIMIZATION REPORT",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Data Source: {mode}",
        f"Region: {AWS_REGION}",
        "",
        f"EC2 Instances / Stopped EC2: {len(ec2)}",
        f"Unattached EBS Volumes: {len(ebs)}",
        f"Unused Elastic IPs: {len(eip)}",
        f"Old Snapshots: {len(snapshots)}",
        f"S3 Buckets: {len(s3_buckets)}",
        f"RDS Databases: {len(rds)}",
        "",
        "COST OPTIMIZATION RECOMMENDATIONS"
    ]

    for item in recommendations:

        report.append(
            f"{item['Resource']} | "
            f"{item['Issue']} | "
            f"{item['Recommendation']}"
        )

    report_text = "\n".join(report)

    col1, col2 = st.columns(2)

    with col1:

        st.download_button(
            label="⬇️ Download TXT Report",
            data=report_text,
            file_name="aws_cost_optimization_report.txt",
            mime="text/plain",
            width="stretch"
        )

    csv_records = []

    for resource_type, resources in resource_mapping.items():

        for resource in resources:

            csv_records.append({
                "Resource Type": resource_type,
                "Resource ID": (
                    resource.get("InstanceId")
                    or resource.get("VolumeId")
                    or resource.get("PublicIp")
                    or resource.get("SnapshotId")
                    or resource.get("BucketName")
                    or resource.get("DBInstanceIdentifier")
                    or "Unknown"
                ),
                "Details": str(resource)
            })

    csv_df = pd.DataFrame(
        csv_records,
        columns=["Resource Type", "Resource ID", "Details"]
    )

    with col2:

        st.download_button(
            label="⬇️ Download CSV Report",
            data=csv_df.to_csv(index=False),
            file_name="aws_resource_report.csv",
            mime="text/csv",
            width="stretch"
        )

    if lambda_report is not None:

        st.download_button(
            label="⬇️ Download Latest Lambda JSON Report",
            data=json.dumps(lambda_report, indent=4),
            file_name="lambda_cost_optimizer_report.json",
            mime="application/json",
            width="stretch"
        )

    st.divider()

    # --------------------------------------------------------
    # S3 REPORT HISTORY
    # --------------------------------------------------------

    st.subheader("☁️ Automated Lambda Report History")

    try:

        report_history = get_s3_report_history()

        if report_history:

            history_df = pd.DataFrame([
                {
                    "Report File": item["Key"].split("/")[-1],
                    "Last Modified": item["LastModified"],
                    "Size (Bytes)": item["Size"]
                }
                for item in report_history
            ])

            st.dataframe(
                history_df,
                width="stretch"
            )

            report_keys = [
                item["Key"] for item in report_history
            ]

            selected_report = st.selectbox(
                "Select a report from S3",
                report_keys,
                format_func=lambda key: key.split("/")[-1]
            )

            if st.button("📥 Load Selected JSON Report"):

                selected_data = get_lambda_report(selected_report)

                st.json(selected_data)

                st.download_button(
                    label="⬇️ Download Selected JSON",
                    data=json.dumps(selected_data, indent=4),
                    file_name=selected_report.split("/")[-1],
                    mime="application/json"
                )

        else:

            st.info("No automated Lambda reports found in S3.")

    except Exception as error:

        st.error(f"Unable to retrieve S3 report history: {error}")


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Intelligent AWS Cost Optimizer | "
    "Python · Boto3 · AWS Lambda · EventBridge · S3 · Streamlit"
)
