import boto3
import os
import botocore.exceptions
import time

def handler(event, context):
    S3_BUCKET = os.environ['S3_BUCKET']
    IAM_ROLE = os.environ['IAM_ROLE']
    KMS_KEY = os.environ['KMS_KEY']
    DB_INSTANCE_ID = os.environ['DB_INSTANCE_ID']
    
    rds = boto3.client('rds')

    try:
        # Retrieve the list of snapshots (both automatic and manual)
        snapshots = rds.describe_db_snapshots(DBInstanceIdentifier=DB_INSTANCE_ID)

        if not snapshots['DBSnapshots']:
            print("No available snapshots.")
            return {"statusCode": 400, "body": "No available snapshots."}

        # Select the latest snapshot
        latest_snapshot = max(
            snapshots['DBSnapshots'], 
            key=lambda x: x['SnapshotCreateTime']
        )
        latest_snapshot_arn = latest_snapshot['DBSnapshotArn']
        latest_snapshot_id = latest_snapshot['DBSnapshotIdentifier'].replace(':', '-')
        snapshot_status = latest_snapshot['Status']

        print(f"Latest snapshot ARN: {latest_snapshot_arn}, Status: {snapshot_status}")

        # Check if the snapshot is available for export
        if snapshot_status != "available":
            return {
                "statusCode": 400,
                "body": f"Snapshot {latest_snapshot_id} is not available for export (Status: {snapshot_status})"
            }

        # Generate a unique export task name
        timestamp = int(time.time())  # Current timestamp to ensure uniqueness
        export_task_name = f"rds-snapshot-export-{latest_snapshot_id}-{timestamp}"

        # Check for existing export tasks
        existing_exports = rds.describe_export_tasks()
        for task in existing_exports.get("ExportTasks", []):
            if task["SourceArn"] == latest_snapshot_arn and task["Status"] in ["STARTING", "IN_PROGRESS"]:
                print(f"Existing export task found: {task['ExportTaskIdentifier']} (Status: {task['Status']})")
                return {
                    "statusCode": 400,
                    "body": f"Snapshot {latest_snapshot_id} is already being exported. Task: {task['ExportTaskIdentifier']}"
                }

        # Start the export task to S3
        response = rds.start_export_task(
            ExportTaskIdentifier=export_task_name,
            SourceArn=latest_snapshot_arn,
            S3BucketName=S3_BUCKET,
            IamRoleArn=IAM_ROLE,
            KmsKeyId=KMS_KEY
        )

        print(f"Export started: {response['ExportTaskIdentifier']}")
        return {
            "statusCode": 200,
            "body": f"Snapshot {latest_snapshot_id} is being exported to {S3_BUCKET}"
        }

    except botocore.exceptions.ClientError as e:
        print(f"AWS error: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"AWS error: {str(e)}"
        }

    except Exception as e:
        print(f"Export error: {str(e)}")
        return {
            "statusCode": 500,
            "body": f"Export error: {str(e)}"
        }
