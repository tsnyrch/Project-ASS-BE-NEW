import os
import logging
import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from typing import Optional

# Set up logging
logger = logging.getLogger(__name__)

class CloudUploaderService:
    """
    Service for uploading files to a cloud storage provider, initially AWS S3.
    """

    def __init__(self):
        """
        Initializes the CloudUploaderService.
        
        AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY) and region (AWS_DEFAULT_REGION)
        should be configured in the environment or via other Boto3 configuration methods
        (e.g., ~/.aws/credentials, IAM roles if running on EC2).
        Refer to Boto3 documentation for more details on credential configuration:
        https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
        """
        # TODO: Consider injecting S3 client or configuration from settings for better testability and flexibility.
        # For now, we rely on Boto3's default credential and region discovery.
        # Example:
        # self.aws_access_key_id = get_settings().aws_access_key_id 
        # self.aws_secret_access_key = get_settings().aws_secret_access_key
        # self.aws_region_name = get_settings().aws_region_name
        #
        # self.s3_client = boto3.client(
        # 's3',
        # aws_access_key_id=self.aws_access_key_id,
        # aws_secret_access_key=self.aws_secret_access_key,
        # region_name=self.aws_region_name
        # )
        # For simplicity in this example, the client will be created per method call,
        # or you can initialize it here if credentials are confirmed to be available.
        pass

    def upload_file_to_s3(self, local_file_path: str, bucket_name: str, s3_object_name: Optional[str] = None) -> bool:
        """
        Uploads a single file to an S3 bucket.

        Args:
            local_file_path: Path to the file on the local filesystem.
            bucket_name: The name of the S3 bucket.
            s3_object_name: The desired object name (path) in S3. If None, the base filename will be used.

        Returns:
            True if the file was uploaded successfully, False otherwise.
        """
        if not os.path.exists(local_file_path) or not os.path.isfile(local_file_path):
            logger.error(f"Local file not found or is not a file: {local_file_path}")
            return False

        if s3_object_name is None:
            s3_object_name = os.path.basename(local_file_path)
        
        # Ensure AWS credentials and region are configured.
        # These can be set as environment variables:
        # AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
        # Or via other Boto3 configuration methods.
        try:
            # TODO: Retrieve these from your application settings or environment variables
            # aws_access_key_id = "YOUR_AWS_ACCESS_KEY_ID"  # Replace with actual key or config call
            # aws_secret_access_key = "YOUR_AWS_SECRET_ACCESS_KEY" # Replace with actual secret or config call
            # region_name = "YOUR_AWS_REGION" # e.g., "us-east-1"

            # It's better to let boto3 find credentials from environment or shared config files.
            # If you must pass them explicitly, ensure they are not hardcoded.
            s3_client = boto3.client('s3') # Boto3 will attempt to find credentials

        except NoCredentialsError:
            logger.error("AWS S3 credentials not found. Configure AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.")
            return False
        except PartialCredentialsError:
            logger.error("Incomplete AWS S3 credentials found. Ensure both key ID and secret key are configured.")
            return False
        except Exception as e: # Catch other potential boto3 session/client creation errors
            logger.error(f"Error initializing S3 client: {e}")
            return False


        try:
            logger.info(f"Uploading {local_file_path} to S3 bucket '{bucket_name}' as '{s3_object_name}'")
            s3_client.upload_file(local_file_path, bucket_name, s3_object_name)
            logger.info(f"Successfully uploaded {local_file_path} to {bucket_name}/{s3_object_name}")
            return True
        except FileNotFoundError:
            logger.error(f"The file was not found: {local_file_path}")
            return False
        except NoCredentialsError: # Should be caught earlier, but good for robustness
            logger.error("Credentials not available for S3 upload.")
            return False
        except PartialCredentialsError:
            logger.error("Partial credentials provided for S3 upload.")
            return False
        except ClientError as e:
            logger.error(f"S3 ClientError during upload of {local_file_path}: {e}")
            # You might want to inspect e.response['Error']['Code'] for specific S3 errors
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred during S3 upload of {local_file_path}: {e}")
            return False

    def upload_folder_to_s3(self, local_folder_path: str, bucket_name: str, s3_destination_folder: Optional[str] = None) -> dict:
        """
        Uploads all files from a local folder to a specified S3 bucket and destination folder.

        Args:
            local_folder_path: The path to the local folder containing files to upload.
            bucket_name: The name of the S3 bucket.
            s3_destination_folder: Optional. The destination folder path within the S3 bucket. 
                                   If None, files will be uploaded to the root of the bucket.

        Returns:
            A dictionary with counts of successful and failed uploads.
            e.g., {"successful_uploads": 5, "failed_uploads": 1}
        """
        if not os.path.exists(local_folder_path) or not os.path.isdir(local_folder_path):
            logger.error(f"Local folder not found or is not a directory: {local_folder_path}")
            return {"successful_uploads": 0, "failed_uploads": 0, "error": "Local folder not found."}

        successful_uploads = 0
        failed_uploads = 0

        for root, _, files in os.walk(local_folder_path):
            for filename in files:
                local_file_path = os.path.join(root, filename)
                
                # Determine the S3 object name, including the relative path from the local_folder_path
                relative_path = os.path.relpath(local_file_path, local_folder_path)
                
                if s3_destination_folder:
                    s3_object_name = os.path.join(s3_destination_folder, relative_path).replace("\\", "/") # Ensure forward slashes for S3
                else:
                    s3_object_name = relative_path.replace("\\", "/")

                if self.upload_file_to_s3(local_file_path, bucket_name, s3_object_name):
                    successful_uploads += 1
                else:
                    failed_uploads += 1
        
        logger.info(f"Folder upload summary: {successful_uploads} successful, {failed_uploads} failed.")
        return {"successful_uploads": successful_uploads, "failed_uploads": failed_uploads}

# Example Usage (for testing purposes, normally this service would be injected and used elsewhere):
# if __name__ == "__main__":
#     # Configure logging for standalone testing
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#
#     # --- IMPORTANT ---
#     # For this example to run, you MUST:
#     # 1. Install boto3: pip install boto3
#     # 2. Configure your AWS credentials (e.g., via environment variables AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION)
#     #    or through a shared credentials file (~/.aws/credentials).
#     # 3. Create an S3 bucket and specify its name below.
#     # 4. Create a local folder with some files to test uploading.
#
#     TEST_LOCAL_FOLDER = "path/to/your/local_test_data_folder"  # REPLACE with your test folder path
#     TEST_BUCKET_NAME = "your-s3-bucket-name-for-testing"    # REPLACE with your S3 bucket name
#     TEST_S3_DEST_FOLDER = "uploaded_from_service_test"      # Optional destination folder in S3
#
#     # Ensure the local test folder exists
#     if not os.path.exists(TEST_LOCAL_FOLDER):
#         os.makedirs(TEST_LOCAL_FOLDER)
#         # Create a few dummy files for testing
#         with open(os.path.join(TEST_LOCAL_FOLDER, "test_file1.txt"), "w") as f:
#             f.write("This is test file 1.")
#         with open(os.path.join(TEST_LOCAL_FOLDER, "test_file2.jpg"), "w") as f: # dummy jpg
#             f.write("dummy image content")
#         os.makedirs(os.path.join(TEST_LOCAL_FOLDER, "subfolder"), exist_ok=True)
#         with open(os.path.join(TEST_LOCAL_FOLDER, "subfolder", "test_file3.txt"), "w") as f:
#             f.write("This is test file 3 in a subfolder.")
#         logger.info(f"Created/ensured test folder: {TEST_LOCAL_FOLDER} with dummy files.")
#
#
#     if TEST_BUCKET_NAME == "your-s3-bucket-name-for-testing" or TEST_LOCAL_FOLDER == "path/to/your/local_test_data_folder":
#         logger.warning("Please update TEST_LOCAL_FOLDER and TEST_BUCKET_NAME with actual paths and bucket name before running the example.")
#     else:
#         uploader_service = CloudUploaderService()
#         
#         # Test single file upload
#         single_file_path = os.path.join(TEST_LOCAL_FOLDER, "test_file1.txt")
#         if os.path.exists(single_file_path):
#             s3_single_file_object_name = os.path.join(TEST_S3_DEST_FOLDER, "single_uploads", "test_file1_uploaded.txt") if TEST_S3_DEST_FOLDER else "single_uploads/test_file1_uploaded.txt"
#             uploader_service.upload_file_to_s3(
#                 local_file_path=single_file_path,
#                 bucket_name=TEST_BUCKET_NAME,
#                 s3_object_name=s3_single_file_object_name.replace("\\", "/")
#             )
#         else:
#             logger.warning(f"Single test file {single_file_path} not found, skipping single file upload test.")
#
#         # Test folder upload
#         upload_results = uploader_service.upload_folder_to_s3(
#             local_folder_path=TEST_LOCAL_FOLDER,
#             bucket_name=TEST_BUCKET_NAME,
#             s3_destination_folder=TEST_S3_DEST_FOLDER
#         )
#         logger.info(f"Folder upload results: {upload_results}")
