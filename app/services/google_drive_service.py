import os
import logging
from typing import Optional, Dict, List, Any, Union
import io

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload, MediaIoBaseDownload

from app.config.settings import get_google_drive_settings

# Set up logging
logger = logging.getLogger(__name__)

class GoogleDriveService:
    """
    Service for interacting with Google Drive using a service account
    """
    # The scope for the Google Drive API
    SCOPES = ['https://www.googleapis.com/auth/drive']
    
    def __init__(self, credentials_path: str = None):
        """
        Initialize the Google Drive service with service account credentials
        
        Args:
            credentials_path: Path to the service account credentials JSON file
        """
        drive_settings = get_google_drive_settings()
        self.credentials_path = credentials_path or os.environ.get(
            'GOOGLE_DRIVE_CREDENTIALS_PATH', 
            drive_settings.credentials_path
        )
        self.default_upload_path = drive_settings.default_upload_path
        self.service = None
    
    def authenticate(self) -> bool:
        """
        Authenticate with Google Drive API using service account credentials
        
        Returns:
            True if authentication was successful, False otherwise
        """
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, scopes=self.SCOPES
            )
            
            self.service = build('drive', 'v3', credentials=credentials)
            logger.info("Successfully authenticated with Google Drive API")
            return True
        except Exception as e:
            logger.error(f"Error authenticating with Google Drive API: {e}")
            return False
    
    def ensure_authenticated(self) -> bool:
        """
        Ensure the service is authenticated before making API calls
        
        Returns:
            True if authenticated, False otherwise
        """
        if self.service is None:
            return self.authenticate()
        return True
    
    def create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Create a folder in Google Drive
        
        Args:
            folder_name: Name of the folder to create
            parent_id: ID of the parent folder. If None, the folder will be created in the root
            
        Returns:
            The ID of the created folder, or None if creation failed
        """
        if not self.ensure_authenticated():
            return None
        
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        try:
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"Created folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        except HttpError as e:
            logger.error(f"Error creating folder in Google Drive: {e}")
            return None
    
    def find_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Find a folder in Google Drive by name
        
        Args:
            folder_name: Name of the folder to find
            parent_id: ID of the parent folder to search in. If None, search everywhere
            
        Returns:
            The ID of the found folder, or None if not found
        """
        if not self.ensure_authenticated():
            return None
        
        query = f"mimeType='application/vnd.google-apps.folder' and name='{folder_name}' and trashed=false"
        
        if parent_id:
            query += f" and '{parent_id}' in parents"
        
        try:
            results = self.service.files().list(
                q=query,
                spaces='drive',
                fields='files(id, name)',
                pageSize=1
            ).execute()
            
            items = results.get('files', [])
            
            if not items:
                logger.info(f"Folder '{folder_name}' not found in Google Drive")
                return None
            
            folder_id = items[0].get('id')
            logger.info(f"Found folder '{folder_name}' with ID: {folder_id}")
            return folder_id
        except HttpError as e:
            logger.error(f"Error finding folder in Google Drive: {e}")
            return None
    
    def find_or_create_folder(self, folder_name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """
        Find a folder in Google Drive by name, or create it if it doesn't exist
        
        Args:
            folder_name: Name of the folder to find or create
            parent_id: ID of the parent folder. If None, use the root
            
        Returns:
            The ID of the found or created folder, or None if operation failed
        """
        folder_id = self.find_folder(folder_name, parent_id)
        
        if folder_id:
            return folder_id
        
        return self.create_folder(folder_name, parent_id)
    
    def create_folder_path(self, path: str) -> Optional[str]:
        """
        Create a path of folders in Google Drive (e.g., '/test/files/')
        
        Args:
            path: The path to create, with folders separated by '/'
            
        Returns:
            The ID of the last folder in the path, or None if creation failed
        """
        if not self.ensure_authenticated():
            return None
        
        # Remove leading and trailing slashes and split the path
        path = path.strip('/')
        if not path:
            return None  # Root folder, no need to create anything
            
        folders = path.split('/')
        
        current_parent_id = None  # Start from the root
        
        for folder_name in folders:
            if not folder_name:
                continue  # Skip empty folder names
                
            folder_id = self.find_or_create_folder(folder_name, current_parent_id)
            if not folder_id:
                logger.error(f"Failed to create folder '{folder_name}' in path '{path}'")
                return None
                
            current_parent_id = folder_id
        
        return current_parent_id
    
    def upload_file(
        self, 
        file_content: Union[str, bytes, io.IOBase],
        file_name: str,
        parent_id: Optional[str] = None,
        mime_type: Optional[str] = None,
        resumable: bool = True,
        is_path: bool = False
    ) -> Optional[str]:
        """
        Upload a file to Google Drive
        
        Args:
            file_content: The file content or path to the file
            file_name: Name to use for the file in Google Drive
            parent_id: ID of the parent folder. If None, file will be uploaded to root
            mime_type: MIME type of the file. If None, it will be guessed
            resumable: Whether to use resumable upload (recommended for files > 5MB)
            is_path: Whether file_content is a path to a file (True) or the actual content (False)
            
        Returns:
            The ID of the uploaded file, or None if upload failed
        """
        if not self.ensure_authenticated():
            return None
        
        file_metadata = {'name': file_name}
        
        if parent_id:
            file_metadata['parents'] = [parent_id]
        
        try:
            if is_path:
                if not os.path.exists(file_content) or not os.path.isfile(file_content):
                    logger.error(f"Local file not found or is not a file: {file_content}")
                    return None
                    
                media = MediaFileUpload(
                    file_content,
                    mimetype=mime_type,
                    resumable=resumable
                )
            else:
                # If file_content is actual content (string, bytes, or file-like object)
                if isinstance(file_content, str):
                    file_content = file_content.encode('utf-8')
                
                if isinstance(file_content, bytes):
                    file_content = io.BytesIO(file_content)
                
                media = MediaIoBaseUpload(
                    file_content,
                    mimetype=mime_type,
                    resumable=resumable
                )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            logger.info(f"Uploaded file '{file_name}' with ID: {file_id}")
            return file_id
        except HttpError as e:
            logger.error(f"Error uploading file to Google Drive: {e}")
            return None
    
    def upload_file_to_path(
        self,
        file_content: Union[str, bytes, io.IOBase],
        file_name: str,
        folder_path: str = None,
        mime_type: Optional[str] = None,
        is_path: bool = False
    ) -> Optional[str]:
        """
        Upload a file to a specified path in Google Drive
        
        Args:
            file_content: The file content or path to the file
            file_name: Name to use for the file in Google Drive
            folder_path: Path where the file should be uploaded (e.g., '/test/files')
            mime_type: MIME type of the file. If None, it will be guessed
            is_path: Whether file_content is a path to a file (True) or the actual content (False)
            
        Returns:
            The ID of the uploaded file, or None if upload failed
        """
        # Use default path if none is provided
        if folder_path is None:
            folder_path = self.default_upload_path
            
        # Create the folder path if it doesn't exist
        folder_id = self.create_folder_path(folder_path)
        if not folder_id:
            logger.error(f"Failed to create or find folder path: {folder_path}")
            return None
        
        # Calculate file size for resumable upload if it's a file path
        if is_path and isinstance(file_content, str):
            file_size = os.path.getsize(file_content)
            use_resumable = file_size > 5 * 1024 * 1024  # 5MB
        else:
            use_resumable = True  # Default to resumable for non-file paths
        
        # Upload the file to the folder
        return self.upload_file(
            file_content=file_content,
            file_name=file_name,
            parent_id=folder_id,
            mime_type=mime_type,
            resumable=use_resumable,
            is_path=is_path
        )
        
    def download_file(
        self, 
        file_id: str, 
        destination_path: Optional[str] = None
    ) -> Optional[Union[bytes, str]]:
        """
        Download a file from Google Drive by its ID
        
        Args:
            file_id: The ID of the file to download
            destination_path: Path where the file should be saved. If None, returns the file content as bytes.
            
        Returns:
            If destination_path is provided, returns the path to the saved file.
            If destination_path is None, returns the file content as bytes.
            Returns None if download failed.
        """
        if not self.ensure_authenticated():
            return None
            
        try:
            # Get file metadata to determine filename if not saving directly
            file_metadata = self.service.files().get(fileId=file_id, fields="name,mimeType").execute()
            file_name = file_metadata.get("name", "downloaded_file")
            mime_type = file_metadata.get("mimeType", "application/octet-stream")
            
            # Download the file content
            request = self.service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            
            downloader = MediaIoBaseDownload(file_content, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Download progress: {int(status.progress() * 100)}%")
                
            file_content.seek(0)
            
            # If destination path is provided, save the file
            if destination_path:
                os.makedirs(os.path.dirname(os.path.abspath(destination_path)), exist_ok=True)
                
                with open(destination_path, "wb") as f:
                    f.write(file_content.read())
                logger.info(f"File saved to {destination_path}")
                return destination_path
            
            # Otherwise return the file content as bytes
            return file_content.getvalue()
            
        except HttpError as e:
            logger.error(f"Error downloading file from Google Drive: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error downloading file: {e}")
            return None
            
    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a file in Google Drive
        
        Args:
            file_id: The ID of the file
            
        Returns:
            A dictionary containing the file metadata, or None if retrieval failed
        """
        if not self.ensure_authenticated():
            return None
            
        try:
            return self.service.files().get(
                fileId=file_id, 
                fields="id,name,mimeType,size,createdTime,modifiedTime,webViewLink"
            ).execute()
        except HttpError as e:
            logger.error(f"Error getting file metadata from Google Drive: {e}")
            return None