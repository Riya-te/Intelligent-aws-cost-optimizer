
from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client


def get_ec2_client():
    """Create an EC2 client using the configured AWS session."""
    return get_client("ec2")


def get_all_elastic_ips():
    """Retrieve all Elastic IP addresses."""
    ec2 = get_ec2_client()

    try:
        response = ec2.describe_addresses()
        elastic_ips = []

        for address in response.get("Addresses", []):
            elastic_ips.append({
                "PublicIp": address.get("PublicIp"),
                "AllocationId": address.get("AllocationId"),
                "AssociationId": address.get("AssociationId"),
                "InstanceId": address.get("InstanceId"),
                "Domain": address.get("Domain"),
                "NetworkInterfaceId": address.get("NetworkInterfaceId"),
            })

        return elastic_ips

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve Elastic IPs: {error}"
        ) from error


def get_unused_elastic_ips():
    """Identify Elastic IPs not associated with a resource."""
    return [
        ip for ip in get_all_elastic_ips()
        if not ip["AssociationId"]
    ]
