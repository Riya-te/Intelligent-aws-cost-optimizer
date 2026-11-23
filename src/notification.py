
"""
Amazon SNS notification module.

Sends AWS Cost Optimizer reports and alerts through SNS.
Uses the centralized AWS session configuration.
"""

import os

from src.aws_session import get_client


DEFAULT_SUBJECT = "AWS Cost Optimization Report"


def get_sns_client():
    """Create an SNS client using the shared AWS session."""
    return get_client("sns")


def get_topic_arn():
    """Read SNS topic ARN from environment configuration."""
    topic_arn = os.getenv("SNS_TOPIC_ARN")

    if not topic_arn:
        raise ValueError(
            "SNS_TOPIC_ARN is not configured. "
            "Set the environment variable before sending notifications."
        )

    if not topic_arn.startswith("arn:") or ":sns:" not in topic_arn:
        raise ValueError("Invalid SNS topic ARN.")

    return topic_arn


def send_notification(message, subject=DEFAULT_SUBJECT):
    """Publish a notification to the configured SNS topic."""

    if not message:
        raise ValueError("Notification message cannot be empty.")

    if not subject:
        raise ValueError("Notification subject cannot be empty.")

    sns = get_sns_client()
    topic_arn = get_topic_arn()

    return sns.publish(
        TopicArn=topic_arn,
        Subject=subject[:100],
        Message=str(message)
    )


def send_email(report):
    """Send cost reports through SNS email subscription."""

    return send_notification(
        message=report,
        subject=DEFAULT_SUBJECT
    )


def send_cost_alert(message):
    """Send an AWS cost optimization alert."""

    return send_notification(
        message=message,
        subject="AWS Cost Optimizer Alert"
    )


if __name__ == "__main__":
    try:
        response = send_notification(
            message="SNS integration test successful!",
            subject="SNS Integration Test"
        )

        print("SNS notification published successfully!")
        print("Message ID:", response["MessageId"])

    except Exception as error:
        print("SNS notification failed:", error)
