
from src.report import collect_report_data
from src.s3_report import upload_report


def run_scan():
    print("\nStarting Intelligent AWS Cost Optimizer...\n")

    # Collect actual AWS resource data
    report_data = collect_report_data()

    # Upload report to S3
    file_name = upload_report(report_data)

    print("\nAWS scan completed successfully!")
    print(f"Report stored at: {file_name}")

    print("\nResource Summary:")
    for key, value in report_data["summary"].items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    run_scan()
