# src/preprocessing/download_manager.py
import os
import logging
from .gdrive_manager import GoogleDriveManager

logger = logging.getLogger(__name__)

class GoogleDriveDownloader:
    def __init__(self, download_path: str, drive_folders: dict):
        self.download_path = download_path
        os.makedirs(download_path, exist_ok=True)
        self.gdrive = GoogleDriveManager()
        self.drive_folders = drive_folders  # Dict with keys: VIDEOS, AUDIOS, TRANSCRIPTS, REPORTS, MENTOR_MATERIALS

    def process_one_video(self, videos_folder_url: str):
        videos_folder_id = self.gdrive.get_folder_id(videos_folder_url)
        video_files = self.gdrive.list_files(videos_folder_id, 'video/mp4')
        if not video_files:
            logger.info("No videos found in Drive folder.")
            return None

        # Process only the first video
        video = video_files[0]
        local_video_path = os.path.join(self.download_path, video['name'])
        self.gdrive.download_file(video['id'], local_video_path)
        logger.info(f"Downloaded: {video['name']}")
        return {
            'id': video['id'],
            'name': video['name'],
            'path': local_video_path
        }

    def delete_drive_file(self, file_id):
        self.gdrive.delete_file(file_id)

    def upload_to_drive(self, local_path, folder_key, mime_type):
        folder_id = self.drive_folders[folder_key]
        return self.gdrive.upload_file(local_path, folder_id, mime_type)

    def list_all_videos(self, videos_folder_url: str):
        videos_folder_id = self.gdrive.get_folder_id(videos_folder_url)
        return self.gdrive.list_files(videos_folder_id, 'video/mp4')