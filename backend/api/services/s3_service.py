"""
S3 Service - File upload and management with MinIO/AWS S3

Handles file uploads, downloads, and deletion using boto3 with MinIO or AWS S3.
"""

import os
import boto3
from botocore.exceptions import ClientError
from botocore.client import Config
from typing import Optional, BinaryIO
import logging

logger = logging.getLogger(__name__)


class S3Service:
    """
    Service for managing file uploads to S3-compatible storage (MinIO or AWS S3)
    """

    def __init__(self):
        """Initialize S3 client with configuration from environment variables"""
        self.endpoint_url = os.getenv("S3_ENDPOINT", "http://localhost:9000")
        self.access_key = os.getenv("S3_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("S3_SECRET_KEY", "minioadmin")
        self.bucket_name = os.getenv("S3_BUCKET_NAME", "open-notebook-files")
        self.region = os.getenv("S3_REGION", "us-east-1")
        self.use_ssl = os.getenv("S3_USE_SSL", "false").lower() == "true"
        self.enabled = os.getenv("S3_ENABLED", "true").lower() == "true"

        if not self.enabled:
            logger.warning("S3 storage is disabled. File uploads will not work.")
            self.client = None
            return

        try:
            # Create S3 client
            self.client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=Config(signature_version="s3v4"),
                use_ssl=self.use_ssl,
            )

            # Ensure bucket exists
            self._ensure_bucket_exists()
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            logger.warning("File uploads will not work. Install Docker and start MinIO, or configure AWS S3.")
            self.client = None

    def _ensure_bucket_exists(self):
        """Create bucket if it doesn't exist"""
        if not self.client:
            return

        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"S3 bucket '{self.bucket_name}' exists")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                logger.info(f"Creating S3 bucket '{self.bucket_name}'")
                try:
                    self.client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"S3 bucket '{self.bucket_name}' created successfully")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    # Don't raise - bucket might exist, just can't verify
            else:
                logger.error(f"Error checking bucket: {e}")
                # Don't raise - allow upload to fail gracefully later
        except Exception as e:
            logger.error(f"Unexpected error checking bucket: {e}")
            # Connection error - disable client
            self.client = None
            raise  # Re-raise to be caught by __init__

    def upload_file(
        self,
        file_obj: BinaryIO,
        object_name: str,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a file to S3

        Args:
            file_obj: File-like object to upload
            object_name: S3 object key (path in bucket)
            content_type: MIME type of the file

        Returns:
            URL to access the uploaded file

        Raises:
            ClientError: If upload fails
            RuntimeError: If S3 is not available
        """
        if not self.client:
            raise RuntimeError("S3 storage is not available. Please start MinIO (Docker) or configure AWS S3.")

        extra_args = {}
        if content_type:
            extra_args["ContentType"] = content_type

        try:
            self.client.upload_fileobj(
                file_obj, self.bucket_name, object_name, ExtraArgs=extra_args
            )
            logger.info(f"File uploaded successfully: {object_name}")

            # Generate URL
            url = self.get_file_url(object_name)
            return url
        except ClientError as e:
            logger.error(f"Failed to upload file: {e}")
            raise

    def download_file(self, object_name: str) -> bytes:
        """
        Download a file from S3

        Args:
            object_name: S3 object key

        Returns:
            File content as bytes

        Raises:
            ClientError: If download fails
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_name)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Failed to download file: {e}")
            raise

    def delete_file(self, object_name: str) -> bool:
        """
        Delete a file from S3

        Args:
            object_name: S3 object key

        Returns:
            True if successful, False otherwise
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
            logger.info(f"File deleted successfully: {object_name}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file: {e}")
            return False

    def file_exists(self, object_name: str) -> bool:
        """
        Check if a file exists in S3

        Args:
            object_name: S3 object key

        Returns:
            True if file exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False

    def get_file_url(self, object_name: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for file access

        Args:
            object_name: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL
        """
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": object_name},
                ExpiresIn=expiration,
            )
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            # Fallback to public URL if using MinIO
            return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"

    def get_file_metadata(self, object_name: str) -> dict:
        """
        Get file metadata from S3

        Args:
            object_name: S3 object key

        Returns:
            Dictionary with metadata (size, content_type, last_modified)

        Raises:
            ClientError: If file doesn't exist
        """
        try:
            response = self.client.head_object(
                Bucket=self.bucket_name, Key=object_name
            )
            return {
                "size": response["ContentLength"],
                "content_type": response.get("ContentType"),
                "last_modified": response["LastModified"],
                "etag": response["ETag"].strip('"'),
            }
        except ClientError as e:
            logger.error(f"Failed to get file metadata: {e}")
            raise


# Singleton instance
_s3_service: Optional[S3Service] = None


def get_s3_service() -> S3Service:
    """Get or create S3 service singleton"""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3Service()
    return _s3_service
