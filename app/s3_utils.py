"""
S3 utilities for uploading files and generating presigned URLs.
"""

import os
import boto3
from botocore.exceptions import ClientError

from app.config import settings


def upload_to_s3(file_path: str, object_key: str) -> str:
    """
    Upload a file to S3 and return a presigned download URL.
    
    Args:
        file_path: Local file path to upload
        object_key: S3 object key (filename in bucket)
        
    Returns:
        Presigned URL for downloading the file
        
    Raises:
        Exception if upload fails
    """
    s3_client = boto3.client('s3', region_name=settings.s3_region)
    
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
        
        # Generate presigned URL
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.s3_bucket_name,
                'Key': object_key
            },
            ExpiresIn=settings.presigned_url_expiry
        )
        
        return presigned_url
        
    except ClientError as e:
        raise Exception(f"Failed to upload to S3: {str(e)}")


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
