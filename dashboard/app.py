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


@st.cache_data(ttl=3600, show_spinner=False)
def load_cost_report(months=6):
    """Load Cost Explorer data and cache it for one hour."""
    from src.cost_explorer import get_cost_report
    return get_cost_report(months=months)


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
        ],

        # Illustrative sample only; not measured AWS telemetry.
        "ec2_cpu_analysis": [
            {
                "resource_id": "i-demo002",
                "resource_name": "Demo Running Instance",
                "resource_type": "EC2",
                "status": "potentially_underutilized",
                "average_cpu": 5.2,
                "maximum_cpu": 18.4,
                "datapoints": 168,
                "message": "Illustrative low CPU utilization.",
                "action": "Review workload before resizing."
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
    from src.recommendation_engine import analyze_ec2_utilization

    return {
        "ec2": get_all_instances(),
        "ebs": get_unattached_volumes(),
        "eip": get_unused_elastic_ips(),
        "snapshots": get_old_snapshots(),
        "s3": get_all_buckets(),
        "rds": get_all_rds_instances(),
        "ec2_cpu_analysis": analyze_ec2_utilization(days=7)
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
        "rds": resources.get("rds_instances", []),
        "ec2_cpu_analysis": resources.get("ec2_cpu_analysis", [])
    }


# ============================================================
# LOAD SELECTED DATA SOURCE
# ============================================================

identity = None
lambda_report = None
report_key = None
cost_report = None
cost_report_error = None

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
            sum(
                len(data.get(key, []))
                for key in ("ec2", "ebs", "eip", "snapshots", "s3", "rds")
            )
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


# Cost Explorer is optional and cached; billing errors do not stop resource scanning.
if mode == "Live AWS Mode":
    try:
        with st.spinner("Loading AWS billing data from Cost Explorer..."):
            cost_report = load_cost_report(months=6)
    except Exception as error:
        cost_report_error = str(error)


# ============================================================
# RESOURCE VARIABLES
# ============================================================

ec2 = data["ec2"]
ebs = data["ebs"]
eip = data["eip"]
snapshots = data["snapshots"]
s3_buckets = data["s3"]
rds = data["rds"]
ec2_cpu_analysis = data.get("ec2_cpu_analysis", [])

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
# COST REPORT DISPLAY
# ============================================================

def display_cost_report(show_details=True):
    """Display actual Cost Explorer results when available."""

    if cost_report_error:
        st.warning(f"Cost Explorer data unavailable: {cost_report_error}")
        return

    if not cost_report:
        st.info(
            "Actual billing data is available in Live AWS Mode. "
            "Demo and Lambda report modes do not load Cost Explorer data."
        )
        return

    currency = cost_report.get("currency", "USD")
    total = cost_report.get("total_cost", 0.0)
    monthly = cost_report.get("monthly_costs", [])
    services = cost_report.get("service_costs", [])

    period = cost_report.get("period", {})
    st.caption(
        f"Cost Explorer period: {period.get('Start', '')} to "
        f"{period.get('End', '')} (end date exclusive)"
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Net Unblended Cost", f"{currency} {total:,.8f}")
    c2.metric("Months Returned", len(monthly))
    c3.metric("Services Returned", len(services))

    st.caption(
        "These are actual Cost Explorer UnblendedCost values. "
        "Negative service amounts may reflect credits, refunds, or billing "
        "adjustments; they are not automatically treated as savings."
    )

    if not show_details:
        return

    if monthly:
        monthly_df = pd.DataFrame(monthly)
        monthly_df["amount"] = pd.to_numeric(
            monthly_df["amount"], errors="coerce"
        )
        st.subheader("Monthly AWS Spending")
        fig = px.bar(
            monthly_df,
            x="month",
            y="amount",
            title=f"Monthly Unblended Cost ({currency})",
            labels={"month": "Month", "amount": f"Cost ({currency})"}
        )
        st.plotly_chart(fig, width="stretch")

        display_df = monthly_df.copy()
        display_df["amount"] = display_df["amount"].map(
            lambda value: f"{value:.8f}"
        )
        st.dataframe(display_df, width="stretch", hide_index=True)
    else:
        st.info("Cost Explorer returned no monthly cost records.")

    if services:
        service_df = pd.DataFrame(services)
        service_df["amount"] = pd.to_numeric(
            service_df["amount"], errors="coerce"
        )
        st.subheader("Service-wise AWS Costs")
        fig = px.bar(
            service_df,
            x="service",
            y="amount",
            title=f"Cost by AWS Service ({currency})",
            labels={"service": "AWS Service", "amount": f"Cost ({currency})"}
        )
        st.plotly_chart(fig, width="stretch")

        display_df = service_df.copy()
        display_df["amount"] = display_df["amount"].map(
            lambda value: f"{value:.8f}"
        )
        st.dataframe(display_df, width="stretch", hide_index=True)
    else:
        st.info("Cost Explorer returned no service-level cost records.")


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

    st.subheader("💰 Actual AWS Billing Overview")
    if mode == "Live AWS Mode":
        display_cost_report(show_details=True)
    else:
        st.info(
            "Switch to Live AWS Mode to retrieve actual AWS billing data. "
            "No sample billing amounts are displayed."
        )

    st.divider()

    st.subheader("📉 EC2 CPU Utilization Analysis")

    if ec2_cpu_analysis:
        cpu_df = pd.DataFrame(ec2_cpu_analysis)

        display_columns = [
            column for column in (
                "resource_id",
                "resource_name",
                "status",
                "average_cpu",
                "maximum_cpu",
                "datapoints",
                "message",
                "action"
            )
            if column in cpu_df.columns
        ]

        st.dataframe(
            cpu_df[display_columns],
            width="stretch",
            hide_index=True
        )

        if "average_cpu" in cpu_df.columns:
            chart_df = cpu_df.dropna(subset=["average_cpu"]).copy()

            if not chart_df.empty:
                label_column = (
                    "resource_name"
                    if "resource_name" in chart_df.columns
                    else "resource_id"
                )
                fig_cpu = px.bar(
                    chart_df,
                    x=label_column,
                    y="average_cpu",
                    title="Average EC2 CPU Utilization",
                    labels={
                        "average_cpu": "Average CPU (%)",
                        label_column: "EC2 Instance"
                    }
                )
                st.plotly_chart(fig_cpu, width="stretch")

        if mode == "Demo Mode":
            st.caption("Demo CPU values are illustrative sample data.")
        elif mode == "Latest Lambda Report" and not ec2_cpu_analysis:
            st.info(
                "This Lambda report does not contain EC2 CPU analysis. "
                "Older report formats remain supported."
            )
    else:
        st.info(
            "No EC2 CPU analysis is available for this data source. "
            "Live mode requires sufficient CloudWatch metric data."
        )

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

    st.subheader("💰 Actual AWS Cost Explorer Data")
    if mode == "Live AWS Mode":
        display_cost_report(show_details=True)
    else:
        st.info("Select Live AWS Mode to view actual Cost Explorer billing data.")

    st.divider()

    st.subheader("EC2 CPU-Based Review Candidates")

    if ec2_cpu_analysis:
        cpu_df = pd.DataFrame(ec2_cpu_analysis)
        st.dataframe(cpu_df, width="stretch", hide_index=True)

        insufficient = sum(
            1 for item in ec2_cpu_analysis
            if item.get("status") == "insufficient_data"
        )
        potentially_underutilized = sum(
            1 for item in ec2_cpu_analysis
            if item.get("status") == "potentially_underutilized"
        )

        cpu_col1, cpu_col2 = st.columns(2)
        cpu_col1.metric("Potentially Underutilized", potentially_underutilized)
        cpu_col2.metric("Insufficient CloudWatch Data", insufficient)

        st.caption(
            "CPU thresholds are an initial screening heuristic. "
            "Review memory, network, workload patterns and business needs "
            "before changing an instance type."
        )
    else:
        st.info("No CPU analysis records are available.")

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
        "AWS COST EXPLORER SUMMARY"
    ]

    if cost_report:
        report.extend([
            f"Currency: {cost_report.get('currency', 'USD')}",
            f"Net Unblended Cost: {cost_report.get('total_cost', 0.0):.8f}",
            f"Cost Period: {cost_report.get('period', {})}"
        ])
    elif cost_report_error:
        report.append(f"Cost Explorer unavailable: {cost_report_error}")
    else:
        report.append("Cost Explorer data not loaded for this data source.")

    report.extend([
        "",
        "EC2 CPU UTILIZATION ANALYSIS"
    ])

    for item in ec2_cpu_analysis:
        report.append(
            f"{item.get('resource_id', 'Unknown')} | "
            f"Status: {item.get('status', 'Unknown')} | "
            f"Average CPU: {item.get('average_cpu', 'N/A')}% | "
            f"Maximum CPU: {item.get('maximum_cpu', 'N/A')}% | "
            f"Datapoints: {item.get('datapoints', 'N/A')} | "
            f"{item.get('message', '')}"
        )

    report.extend(["", "COST OPTIMIZATION RECOMMENDATIONS"])

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
