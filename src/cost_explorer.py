
"""
AWS Cost Explorer integration.

Features:
1. Retrieves actual AWS costs grouped by month and service.
2. Retrieves daily AWS costs grouped by service.
3. Detects unusual increases in daily service spending.
4. Handles missing billing data safely.
5. Uses manual pagination through NextPageToken.

Read-only: does not modify AWS resources.

Note:
Cost anomaly detection uses statistical heuristics, not ML.
"""

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from statistics import mean, pstdev

from src.aws_session import get_client


COST_EXPLORER_REGION = "us-east-1"
DEFAULT_METRIC = "UnblendedCost"


# ---------------------------------------------------------
# COST EXPLORER CLIENT
# ---------------------------------------------------------

def get_cost_explorer_client():
    """Create the AWS Cost Explorer client."""

    return get_client(
        "ce",
        region_name=COST_EXPLORER_REGION
    )


# ---------------------------------------------------------
# DATE RANGE
# ---------------------------------------------------------

def _get_date_range(months=6):
    """Get a date range covering the requested months."""

    if not isinstance(months, int) or not 1 <= months <= 24:
        raise ValueError("months must be between 1 and 24.")

    today = date.today()

    first_month = today.month - months + 1
    year = today.year

    while first_month <= 0:
        first_month += 12
        year -= 1

    start_date = date(year, first_month, 1)
    end_date = date.fromordinal(today.toordinal() + 1)

    return {
        "Start": start_date.isoformat(),
        "End": end_date.isoformat()
    }


# ---------------------------------------------------------
# DECIMAL CONVERSION
# ---------------------------------------------------------

def _to_decimal(value):
    """Safely convert an AWS cost value to Decimal."""

    try:
        return Decimal(str(value))

    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0")


# ---------------------------------------------------------
# MONTHLY COST REPORT
# ---------------------------------------------------------

def get_cost_report(months=6):
    """
    Retrieve AWS costs grouped by month and service.

    Handles pagination manually using NextPageToken.
    """

    client = get_cost_explorer_client()
    period = _get_date_range(months)

    request = {
        "TimePeriod": period,
        "Granularity": "MONTHLY",
        "Metrics": [DEFAULT_METRIC],
        "GroupBy": [
            {
                "Type": "DIMENSION",
                "Key": "SERVICE"
            }
        ]
    }

    monthly_totals = {}
    service_totals = {}

    total_cost = Decimal("0")
    currency = "USD"

    next_token = None

    while True:

        if next_token:
            request["NextPageToken"] = next_token

        response = client.get_cost_and_usage(**request)

        for result in response.get("ResultsByTime", []):

            month_start = result.get(
                "TimePeriod", {}
            ).get("Start", "")

            total_metric = result.get(
                "Total", {}
            ).get(DEFAULT_METRIC, {})

            amount = _to_decimal(
                total_metric.get("Amount", "0")
            )

            currency = total_metric.get("Unit", currency)
            total_cost += amount

            if month_start:
                monthly_totals[month_start[:7]] = {
                    "month": month_start[:7],
                    "amount": float(amount),
                    "currency": currency,
                    "estimated": result.get("Estimated", False)
                }

            for group in result.get("Groups", []):

                keys = group.get("Keys", [])

                if not keys:
                    continue

                service_name = keys[0]

                metric = group.get(
                    "Metrics", {}
                ).get(DEFAULT_METRIC, {})

                service_amount = _to_decimal(
                    metric.get("Amount", "0")
                )

                currency = metric.get("Unit", currency)

                service_totals[service_name] = (
                    service_totals.get(
                        service_name, Decimal("0")
                    ) + service_amount
                )

        next_token = response.get("NextPageToken")

        if not next_token:
            break

    monthly_costs = sorted(
        monthly_totals.values(),
        key=lambda item: item["month"]
    )

    service_costs = [
        {
            "service": service,
            "amount": float(amount),
            "currency": currency
        }
        for service, amount in sorted(
            service_totals.items(),
            key=lambda item: item[1],
            reverse=True
        )
    ]

    return {
        "currency": currency,
        "total_cost": float(total_cost),
        "monthly_costs": monthly_costs,
        "service_costs": service_costs,
        "period": period
    }


# ---------------------------------------------------------
# DAILY SERVICE COSTS
# ---------------------------------------------------------

def get_daily_service_costs(days=30):
    """
    Retrieve daily AWS costs grouped by service.

    Today's incomplete billing data is excluded because
    the Cost Explorer end date is exclusive.

    Dates with no service groups are preserved as empty
    dictionaries so zero-spend days are not mistaken for
    missing billing data.
    """

    if not isinstance(days, int) or not 3 <= days <= 90:
        raise ValueError("days must be between 3 and 90.")

    client = get_cost_explorer_client()

    today = date.today()

    start_date = today - timedelta(days=days)
    end_date = today

    request = {
        "TimePeriod": {
            "Start": start_date.isoformat(),
            "End": end_date.isoformat()
        },
        "Granularity": "DAILY",
        "Metrics": [DEFAULT_METRIC],
        "GroupBy": [
            {
                "Type": "DIMENSION",
                "Key": "SERVICE"
            }
        ]
    }

    daily_costs = {}
    currency = "USD"

    next_token = None

    while True:

        if next_token:
            request["NextPageToken"] = next_token

        response = client.get_cost_and_usage(**request)

        for result in response.get("ResultsByTime", []):

            period = result.get("TimePeriod", {})
            day = period.get("Start")

            if not day:
                continue

            # Preserve the date even if there are no
            # service spending groups for that day.
            daily_costs.setdefault(day, {})

            for group in result.get("Groups", []):

                keys = group.get("Keys", [])

                if not keys:
                    continue

                service = keys[0]

                metric = group.get(
                    "Metrics", {}
                ).get(DEFAULT_METRIC, {})

                amount = _to_decimal(
                    metric.get("Amount", "0")
                )

                currency = metric.get("Unit", currency)

                daily_costs[day][service] = float(amount)

        next_token = response.get("NextPageToken")

        if not next_token:
            break

    return {
        "currency": currency,
        "daily_costs": daily_costs,
        "period": {
            "Start": start_date.isoformat(),
            "End": end_date.isoformat()
        }
    }


# ---------------------------------------------------------
# COST ANOMALY DETECTION
# ---------------------------------------------------------

def analyze_cost_anomalies(
    days=30,
    baseline_days=14,
    percentage_threshold=50.0,
    standard_deviations=2.0,
    minimum_increase=1.0
):
    """
    Detect unusually high daily AWS service costs.

    Compares yesterday's service spending against the
    previous baseline_days of daily spending.

    Detection conditions:
    1. Actual spending exceeds the statistical limit.
    2. Percentage increase meets the configured threshold.
    3. Absolute increase meets the minimum threshold.

    This is a statistical heuristic, not an ML prediction.
    """

    # Validate inputs.
    if not isinstance(baseline_days, int) or baseline_days < 2:
        raise ValueError("baseline_days must be at least 2.")

    if not isinstance(days, int) or days <= baseline_days:
        raise ValueError(
            "days must be greater than baseline_days."
        )

    if percentage_threshold < 0:
        raise ValueError(
            "percentage_threshold cannot be negative."
        )

    if standard_deviations < 0:
        raise ValueError(
            "standard_deviations cannot be negative."
        )

    if minimum_increase < 0:
        raise ValueError(
            "minimum_increase cannot be negative."
        )

    # Retrieve actual AWS billing data.
    report = get_daily_service_costs(days=days)

    daily_costs = report["daily_costs"]

    # Analyze yesterday, the latest completed billing day.
    target_date = date.today() - timedelta(days=1)
    target_day = target_date.isoformat()

    # Build the historical baseline dates.
    baseline_dates = [
        (
            target_date - timedelta(days=offset)
        ).isoformat()
        for offset in range(baseline_days, 0, -1)
    ]

    # -----------------------------------------------------
    # MISSING BILLING DATA VALIDATION
    # -----------------------------------------------------

    required_dates = [target_day] + baseline_dates

    missing_dates = [
        day
        for day in required_dates
        if day not in daily_costs
    ]

    if missing_dates:

        return {
            "analysis_status": "insufficient_data",
            "analysis_date": target_day,
            "baseline_days": baseline_days,
            "currency": report["currency"],
            "anomaly_count": 0,
            "anomalies": [],
            "warning": (
                "Cost Explorer data is missing for: "
                + ", ".join(missing_dates)
            )
        }

    # -----------------------------------------------------
    # COLLECT SERVICES
    # -----------------------------------------------------

    services = set()

    for costs in daily_costs.values():
        services.update(costs.keys())

    anomalies = []

    # -----------------------------------------------------
    # ANALYZE EACH SERVICE
    # -----------------------------------------------------

    for service in sorted(services):

        # Historical spending for the baseline period.
        historical_costs = [
            daily_costs.get(day, {}).get(service, 0.0)
            for day in baseline_dates
        ]

        # Yesterday's actual spending.
        actual_cost = daily_costs.get(
            target_day, {}
        ).get(service, 0.0)

        # Statistical baseline.
        baseline_average = mean(historical_costs)

        baseline_stddev = pstdev(historical_costs)

        increase = actual_cost - baseline_average

        # Calculate percentage increase.
        if baseline_average > 0:

            percentage_increase = (
                increase / baseline_average
            ) * 100

        elif actual_cost > 0:

            # Spending appeared where historical average
            # spending was zero.
            percentage_increase = 100.0

        else:
            percentage_increase = 0.0

        # Calculate the anomaly threshold.
        statistical_limit = (
            baseline_average
            + standard_deviations * baseline_stddev
        )

        # -------------------------------------------------
        # ANOMALY CONDITIONS
        # -------------------------------------------------

        if (
            actual_cost > statistical_limit
            and percentage_increase >= percentage_threshold
            and increase >= minimum_increase
        ):

            anomalies.append({

                "resource_type": "AWS Service",

                "resource_id": service,

                "service": service,

                "status": "cost_anomaly_detected",

                "date": target_day,

                "actual_cost": round(actual_cost, 4),

                "baseline_average": round(
                    baseline_average, 4
                ),

                "baseline_stddev": round(
                    baseline_stddev, 4
                ),

                "increase": round(increase, 4),

                "percentage_increase": round(
                    percentage_increase, 2
                ),

                "statistical_limit": round(
                    statistical_limit, 4
                ),

                "currency": report["currency"],

                "message": (
                    f"{service} spending increased by "
                    f"{percentage_increase:.2f}% compared "
                    "with its historical daily average."
                ),

                "action": (
                    "Investigate service usage, resource "
                    "provisioning, data transfer and billing "
                    "changes in AWS Cost Explorer."
                )
            })

    # Sort anomalies by highest absolute cost increase.
    anomalies.sort(
        key=lambda item: item["increase"],
        reverse=True
    )

    return {
        "analysis_status": "completed",
        "analysis_date": target_day,
        "baseline_days": baseline_days,
        "currency": report["currency"],
        "anomaly_count": len(anomalies),
        "anomalies": anomalies
    }


# ---------------------------------------------------------
# MAIN EXECUTION
# ---------------------------------------------------------

if __name__ == "__main__":

    try:

        # Monthly cost report.
        report = get_cost_report(months=6)

        print("\nAWS COST REPORT")
        print("=" * 40)

        print("Period:", report["period"])

        print(
            "Total Cost:",
            report["currency"],
            report["total_cost"]
        )

        print("\nMONTHLY COSTS")

        for item in report["monthly_costs"]:

            estimated = (
                " (Estimated)" if item["estimated"] else ""
            )

            print(
                item["month"],
                item["currency"],
                item["amount"],
                estimated
            )

        print("\nSERVICE-WISE COSTS")

        for item in report["service_costs"]:

            print(
                item["service"],
                item["currency"],
                item["amount"]
            )

        # Daily anomaly analysis.
        print("\nAWS COST ANOMALY ANALYSIS")
        print("=" * 40)

        anomaly_report = analyze_cost_anomalies()

        print(
            "Analysis status:",
            anomaly_report["analysis_status"]
        )

        print(
            "Analysis date:",
            anomaly_report["analysis_date"]
        )

        print(
            "Anomalies detected:",
            anomaly_report["anomaly_count"]
        )

        if anomaly_report["analysis_status"] == "insufficient_data":

            print("Warning:", anomaly_report["warning"])

        else:

            for anomaly in anomaly_report["anomalies"]:

                print("\nService:", anomaly["service"])

                print(
                    "Actual cost:",
                    anomaly["currency"],
                    anomaly["actual_cost"]
                )

                print(
                    "Baseline average:",
                    anomaly["baseline_average"]
                )

                print(
                    "Increase:",
                    anomaly["percentage_increase"],
                    "%"
                )

                print("Action:", anomaly["action"])

    except Exception as error:

        print("Cost Explorer request failed:", error)
        raise
