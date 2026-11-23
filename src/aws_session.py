
import boto3

AWS_PROFILE = "new-account"
AWS_REGION = "ap-south-1"


def get_session():
    return boto3.Session(
        profile_name=AWS_PROFILE,
        region_name=AWS_REGION
    )


def get_client(service_name):
    return get_session().client(service_name)
