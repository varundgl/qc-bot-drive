# src/gdrive_manager.py
import os
import io
import json
import logging
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

class GoogleDriveManager:
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self):
        # Try to load full credentials from environment variable
        gcp_credentials = os.getenv("GCP_CREDENTIALS")
        if gcp_credentials:
            cred_data = json.loads(gcp_credentials)
            creds = service_account.Credentials.from_service_account_info(
                cred_data, scopes=self.SCOPES
            )
        else:
            # Fallback to file-based credentials
            creds = service_account.Credentials.from_service_account_file(
                "credentials.json", scopes=self.SCOPES
            )
        self.service = build('drive', 'v3', credentials=creds)

    def get_folder_id(self, url):
        """Extract folder ID from Google Drive URL"""
        if 'folders/' in url:
            return url.split('folders/')[-1].split('?')[0]
        elif 'id=' in url:
            return url.split('id=')[-1].split('&')[0]
        return url

    def list_files(self, folder_id, file_type='video/mp4'):
        """List files in a Google Drive folder"""
        query = f"'{folder_id}' in parents and mimeType='{file_type}' and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name, mimeType)"
        ).execute()
        return results.get('files', [])

    def download_file(self, file_id, destination):
        """Download a file from Google Drive"""
        logger.info("Downloading file %s to %s", file_id, destination)
        request = self.service.files().get_media(fileId=file_id)
        fh = io.FileIO(destination, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            logger.info(f"Download {int(status.progress() * 100)}%")
        logger.info("Download complete: %s", destination)
        return destination

    def upload_file(self, local_path, drive_folder_id, mime_type):
        """Upload a file to Google Drive"""
        file_metadata = {
            'name': os.path.basename(local_path),
            'parents': [drive_folder_id]
        }
        media = MediaFileUpload(local_path, mimetype=mime_type)
        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        logger.info(f"Uploaded {local_path} to Drive folder {drive_folder_id}")
        return file.get('id')

    def delete_file(self, file_id):
        """Delete a file from Google Drive"""
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Deleted file {file_id} from Drive")
            return True
        except HttpError as error:
            logger.error(f"An error occurred: {error}")
            return False

    def find_file_by_name(self, folder_id, filename):
        """Find a file by name in a folder"""
        query = f"'{folder_id}' in parents and name='{filename}' and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id)"
        ).execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None

    def list_txt_files(self, folder_id):
        """List all .txt files in a Google Drive folder"""
        query = f"'{folder_id}' in parents and mimeType='text/plain' and trashed=false"
        results = self.service.files().list(
            q=query,
            fields="files(id, name)"
        ).execute()
        return results.get('files', [])

    def remove_duplicates_by_name(self, folder_id):
        """Remove duplicate files (by name) in a Drive folder, keeping only the latest."""
        files = self.list_txt_files(folder_id)
        name_map = {}
        for file in files:
            if file['name'] not in name_map:
                name_map[file['name']] = file
            else:
                # If duplicate, delete the older one (or you can keep the latest by timestamp if available)
                self.delete_file(file['id'])
                logger.info(f"Deleted duplicate file: {file['name']} ({file['id']})")