
import os
import boto3


def get_session():
    """
    Create an AWS session using the appropriate credential provider.

    Local development:
        Uses AWS_PROFILE when configured.

    AWS Lambda:
        Uses the attached IAM execution role automatically.
    """

    profile = os.getenv("AWS_PROFILE")

    region = (
        os.getenv("AWS_REGION")
        or os.getenv("AWS_DEFAULT_REGION")
        or "ap-south-1"
    )

    return boto3.Session(
        profile_name=profile or None,
        region_name=region
    )


def get_client(service_name, region_name=None):
    """
    Return an AWS service client using the shared session.
    """

    session = get_session()

    return session.client(
        service_name,
        region_name=region_name or session.region_name
    )
