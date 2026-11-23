
from botocore.exceptions import ClientError, BotoCoreError
from src.aws_session import get_client


def get_rds_client():
    """Create RDS client using the shared AWS session."""
    return get_client("rds")


def get_all_rds_instances():
    """Retrieve all RDS database instances."""
    rds = get_rds_client()

    try:
        paginator = rds.get_paginator("describe_db_instances")
        databases = []

        for page in paginator.paginate():
            for db in page.get("DBInstances", []):
                databases.append({
                    "DBInstanceIdentifier": db["DBInstanceIdentifier"],
                    "Engine": db["Engine"],
                    "DBInstanceClass": db["DBInstanceClass"],
                    "Status": db["DBInstanceStatus"],
                    "AllocatedStorage": db["AllocatedStorage"],
                    "MultiAZ": db["MultiAZ"],
                    "Endpoint": db.get("Endpoint", {}).get(
                        "Address", "N/A"
                    ),
                    "PubliclyAccessible": db.get(
                        "PubliclyAccessible", False
                    ),
                    "Encrypted": db.get("StorageEncrypted", False)
                })

        return databases

    except (ClientError, BotoCoreError) as error:
        raise RuntimeError(
            f"Unable to retrieve RDS instances: {error}"
        ) from error


def get_available_rds_instances():
    """Retrieve RDS instances in the available state."""
    return [
        db for db in get_all_rds_instances()
        if db["Status"] == "available"
    ]
