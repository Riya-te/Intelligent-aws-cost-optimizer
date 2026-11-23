
from src.report import collect_report_data, generate_report
from src.notification import send_email
from src.recommendation_engine import (
    send_recommendation_notifications
)


def lambda_handler(event, context):
    """
    Scheduled AWS Cost Optimization scan.

    Collects AWS resources, detects cost anomalies,
    generates a report and sends notifications.

    This Lambda performs read-only resource analysis.
    It does not modify or delete AWS resources.
    """

    try:
        print("Starting Intelligent AWS Cost Optimizer scan.")

        # Step 1: Collect all AWS resource data once.
        report_data = collect_report_data()

        summary = report_data.get("summary", {})
        resources = report_data.get("resources", {})

        recommendations = resources.get(
            "resource_recommendations", []
        )

        # Step 2: Generate report from collected data.
        report = generate_report(report_data)

        # Step 3: Send the regular email report.
        email_result = send_email(report)

        print("Regular report email processed.")

        # Step 4: Extract cost anomaly findings.
        cost_analysis = resources.get(
            "cost_anomaly_analysis", []
        )

        cost_anomalies = [
            item for item in cost_analysis
            if item.get("status") == "cost_anomaly_detected"
        ]

        cost_data_warnings = [
            item for item in cost_analysis
            if item.get("status") == "cost_anomaly_insufficient_data"
        ]

        # Step 5: Send duplicate-safe SNS notifications.
        notification_result = send_recommendation_notifications(
            recommendations
        )

        print("Recommendation notification processing completed.")

        # Step 6: Build structured execution response.
        response_body = {
            "message": "AWS Cost Optimization scan completed.",
            "region": report_data["region"],
            "generated_at": report_data["generated_at"],

            "total_recommendations": len(recommendations),

            "summary": summary,

            "cost_analysis": {
                "anomalies_detected": len(cost_anomalies),
                "billing_data_warnings": len(cost_data_warnings),
                "anomalies": cost_anomalies,
                "warnings": cost_data_warnings
            },

            "notifications": {
                "email_processed": True,
                "sns": notification_result
            },

            "resource_analysis": {
                "total_findings": len(recommendations),
                "analysis_errors": summary.get(
                    "analysis_errors", 0
                )
            }
        }

        print("AWS Cost Optimization scan completed successfully.")

        return {
            "statusCode": 200,
            "body": response_body
        }

    except Exception as error:

        print(
            f"Lambda execution failed: {type(error).__name__}: {error}"
        )

        raise
