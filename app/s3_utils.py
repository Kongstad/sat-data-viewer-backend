"""
S3 utilities for uploading files and generating presigned URLs.
"""

import os
import json
from datetime import datetime, timedelta
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import settings


def get_s3_client():
    """Create S3 client with proper configuration for presigned URLs."""
    return boto3.client(
        's3',
        region_name=settings.s3_region,
        config=Config(signature_version='s3v4')
    )


def upload_to_s3(file_path: str, object_key: str) -> str:
    """
    Upload a file to S3 and return a direct download URL.
    Schedules automatic deletion after 10 minutes.
    
    Args:
        file_path: Local file path to upload
        object_key: S3 object key (filename in bucket)
        
    Returns:
        Direct S3 URL for downloading the file
        
    Raises:
        Exception if upload fails
    """
    s3_client = get_s3_client()
    
    try:
        # Upload file
        s3_client.upload_file(
            file_path,
            settings.s3_bucket_name,
            object_key,
            ExtraArgs={
                'ContentDisposition': f'attachment; filename="{os.path.basename(file_path)}"'
            }
        )
        
        # Schedule deletion in 10 minutes
        schedule_deletion(object_key, minutes=10)
        
        # Return direct S3 URL (bucket is public)
        direct_url = f"https://{settings.s3_bucket_name}.s3.{settings.s3_region}.amazonaws.com/{object_key}"
        
        return direct_url
        
    except ClientError as e:
        raise Exception(f"Failed to upload to S3: {str(e)}")


def schedule_deletion(object_key: str, minutes: int = 10):
    """
    Schedule S3 object deletion using EventBridge Scheduler.
    
    Args:
        object_key: S3 object key to delete
        minutes: Minutes from now to schedule deletion
    """
    scheduler = boto3.client('scheduler', region_name=settings.s3_region)
    sts = boto3.client('sts')
    
    # Get account ID dynamically
    account_id = sts.get_caller_identity()['Account']
    
    # Schedule time
    schedule_time = datetime.utcnow() + timedelta(minutes=minutes)
    schedule_expr = f"at({schedule_time.strftime('%Y-%m-%dT%H:%M:%S')})"
    
    # Unique schedule name
    schedule_name = f"delete-{object_key.replace('/', '-')}"[:64]  # Max 64 chars
    
    try:
        scheduler.create_schedule(
            Name=schedule_name,
            ScheduleExpression=schedule_expr,
            FlexibleTimeWindow={'Mode': 'OFF'},
            Target={
                'Arn': f'arn:aws:lambda:{settings.s3_region}:{account_id}:function:sat-data-viewer-backend',
                'RoleArn': f'arn:aws:iam::{account_id}:role/EventBridgeSchedulerRole',
                'Input': json.dumps({
                    'action': 'delete_s3_object',
                    'bucket': settings.s3_bucket_name,
                    'key': object_key
                })
            },
            ActionAfterCompletion='DELETE'  # Auto-delete schedule after execution
        )
    except Exception as e:
        # Don't fail upload if scheduling fails
        print(f"Failed to schedule deletion: {e}")


def delete_from_s3(object_key: str):
    """
    Delete an object from S3 (best effort cleanup).
    
    Args:
        object_key: S3 object key to delete
    """
    s3_client = boto3.client('s3', region_name=settings.s3_region)
    
    try:
        s3_client.delete_object(
            Bucket=settings.s3_bucket_name,
            Key=object_key
        )
    except ClientError:
        pass  # Best effort, ignore errors
