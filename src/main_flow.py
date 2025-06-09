# src/main_flow.py
from src.preprocessing.gdrive_manager import GoogleDriveManager
from src.preprocessing.download_manager import GoogleDriveDownloader
from src.preprocessing.video_processor import VideoProcessor
from src.preprocessing.transcript_generator import TranscriptGenerator
from src.preprocessing.file_processor import FileProcessor
from src.report_generation.openai_client import OpenAIClient
from src.report_generation.report_generator import ReportGenerator
import json
import os
import glob
import asyncio
import logging
import tempfile
import shutil
import googleapiclient.errors

logger = logging.getLogger(__name__)

class MainFlow:
    def __init__(self, config_path: str):
        logger.info("Initializing MainFlow with config: %s", config_path)
        with open(config_path) as f:
            self.config = json.load(f)
        self.paths = self.config["PATHS"]
        self.drive_folders = {
            "VIDEOS": "1angHYyiE_sPTKpRsrHyPAJkYF7b78iPf",
            "AUDIOS": "1bLbSXaO3AS-EuBg_o7sGc8AonkHt7SdG",
            "TRANSCRIPTS": "1TbqLgYXOguxYivMiy17s1UVqUKxpGtt3",
            "REPORTS": "1JgwDdQVc1YsyKNhag5l1PdD607vMjy1H",
            "MENTOR_MATERIALS": "1OVhmzLD5NHmrHknSSWwAYC_NVlD39-sh"
        }
        self._create_directories()
        
    def _create_directories(self):
        for path in self.paths.values():
            os.makedirs(path, exist_ok=True)

    async def process_drive_url(self, folder_url: str):
        logger.info("Processing Google Drive folder: %s", folder_url)
        VideoProcessor.clean_directory(self.paths["VIDEOS"])
        VideoProcessor.clean_directory(self.paths["AUDIOS"])
        download_manager = GoogleDriveDownloader(self.paths["VIDEOS"], self.drive_folders)
        gdrive = download_manager.gdrive

        # Get all video files in Drive
        video_files = download_manager.list_all_videos(folder_url)
        if not video_files:
            logger.warning("No videos to process in folder: %s", folder_url)
            return

        # Get all transcript files in Drive Transcripts folder
        transcript_drive_files = gdrive.list_txt_files(self.drive_folders["TRANSCRIPTS"])
        transcript_names = {os.path.splitext(f['name'])[0] for f in transcript_drive_files}

        for video in video_files:
            base_name = os.path.splitext(video['name'])[0]
            if base_name in transcript_names:
                logger.info(f"Transcript for {base_name} already exists in Drive. Skipping video.")
                continue

            # Download and process this video
            local_video_path = os.path.join(self.paths["VIDEOS"], video['name'])
            gdrive.download_file(video['id'], local_video_path)
            logger.info(f"Downloaded: {video['name']}")
            video_id = video['id']
            video_name = video['name']
            video_path = local_video_path
            audio_path = os.path.join(self.paths["AUDIOS"], f"{base_name}.wav")
            transcript_path = os.path.join(self.paths["TRANSCRIPTS"], f"{base_name}.txt")

            video_processor = VideoProcessor()
            transcript_generator = TranscriptGenerator(
                os.getenv("AZURE_SPEECH_KEY"),
                os.getenv("AZURE_SPEECH_REGION")
            )

            try:
                # Convert video to audio
                if video_processor.convert_mp4_to_wav(video_path, audio_path):
                    logger.info("Converted video to audio: %s", audio_path)
                    # Upload audio to Drive
                    download_manager.upload_to_drive(audio_path, "AUDIOS", "audio/wav")
                    # Delete video from Drive and local
                    try:
                        download_manager.delete_drive_file(video_id)
                    except googleapiclient.errors.HttpError as e:
                        if e.resp.status == 403:
                            logger.warning(f"Skipping delete for {video_name} due to insufficient permissions.")
                        else:
                            logger.error(f"Error deleting video from Drive: {e}")
                    try:
                        os.remove(video_path)
                    except Exception as e:
                        logger.warning(f"Could not delete local video file: {e}")

                    # Generate transcript
                    if transcript_generator.transcribe_audio(audio_path, transcript_path):
                        logger.info(f"Generated transcript: {transcript_path}")
                        # Upload transcript to Drive
                        download_manager.upload_to_drive(transcript_path, "TRANSCRIPTS", "text/plain")
                        # Delete audio from Drive and local
                        audio_drive_id = gdrive.find_file_by_name(self.drive_folders["AUDIOS"], f"{base_name}.wav")
                        if audio_drive_id:
                            try:
                                download_manager.delete_drive_file(audio_drive_id)
                            except googleapiclient.errors.HttpError as e:
                                if e.resp.status == 403:
                                    logger.warning(f"Skipping delete for audio {base_name}.wav due to insufficient permissions.")
                                else:
                                    logger.error(f"Error deleting audio from Drive: {e}")
                        try:
                            os.remove(audio_path)
                        except Exception as e:
                            logger.warning(f"Could not delete local audio file: {e}")
                    else:
                        logger.error(f"Failed to generate transcript for {video_name}")
                else:
                    logger.error(f"Failed to convert video: {video_name}")
            except googleapiclient.errors.HttpError as e:
                if e.resp.status == 403:
                    logger.warning(f"Skipping file {video_name} due to insufficient permissions.")
                else:
                    logger.error(f"Google API error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing {video_name}: {e}")

    def process_mentor_materials(self, files: dict):
        """Process mentor materials (PPTX/IPYNB)"""
        logger.info("Processing mentor materials...")
        processed_files = []
        
        # Clean directory first
        VideoProcessor.clean_directory(self.paths["MENTOR_MATERIALS"])
        
        for file_type, file_data in files.items():
            if not file_data:
                continue
                
            # Save uploaded file
            file_path = os.path.join(self.paths["MENTOR_MATERIALS"], file_data.name)
            with open(file_path, "wb") as f:
                f.write(file_data.getbuffer())
            
            # Process based on file type
            base_name = os.path.splitext(file_data.name)[0]
            output_path = os.path.join(self.paths["MENTOR_MATERIALS"], f"{base_name}.txt")
            
            if file_type == "slides" and file_path.lower().endswith(('.pptx', '.ppt')):
                content = FileProcessor.process_slide_file(file_path)
            elif file_type == "notebook" and file_path.lower().endswith('.ipynb'):
                content = FileProcessor.process_notebook_file(file_path)
            else:
                logger.error(f"Unsupported file type: {file_data.name}")
                continue
                
            # Save processed content
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Remove original file
            os.remove(file_path)
            
            # Upload to Drive
            gdrive = GoogleDriveManager()
            gdrive.upload_file(output_path, self.drive_folders["MENTOR_MATERIALS"], "application/octet-stream")
            
            processed_files.append(output_path)
        
        return processed_files

    def generate_quality_reports(self):
        """Generate quality reports"""
        logger.info("Generating quality reports...")
        # Remove duplicates first
        self.remove_drive_duplicates()

        # List transcript files from Drive
        gdrive = GoogleDriveManager()
        transcript_drive_files = gdrive.list_txt_files(self.drive_folders["TRANSCRIPTS"])

        # Download transcripts from Drive to local if not present
        for file in transcript_drive_files:
            local_path = os.path.join(self.paths["TRANSCRIPTS"], file["name"])
            if not os.path.exists(local_path):
                gdrive.download_file(file["id"], local_path)

        # Now generate reports from these local files (which mirror Drive)
        # Load checklist
        with open("config/checklist.txt", "r") as f:
            checklist = f.read()

        # Initialize OpenAI client
        openai_client = OpenAIClient("config/config.json")
        client = openai_client.get_client()
        deployment = openai_client.get_deployment()

        report_generator = ReportGenerator(client, deployment, checklist)
        report_generator.generate_reports(
            self.paths["TRANSCRIPTS"],
            self.paths["MENTOR_MATERIALS"],
            self.paths["REPORTS"]
        )
        # Upload reports to Drive
        gdrive = GoogleDriveManager()
        for report_file in os.listdir(self.paths["REPORTS"]):
            if report_file.endswith(".txt"):
                local_path = os.path.join(self.paths["REPORTS"], report_file)
                gdrive.upload_file(local_path, self.drive_folders["REPORTS"], "text/plain")

    def remove_drive_duplicates(self):
        gdrive = GoogleDriveManager()
        for key in ["REPORTS", "TRANSCRIPTS", "MENTOR_MATERIALS"]:
            gdrive.remove_duplicates_by_name(self.drive_folders[key])