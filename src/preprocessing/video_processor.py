# src/preprocessing/video_processor.py
import os
import subprocess
import logging

logger = logging.getLogger(__name__)

class VideoProcessor:
    @staticmethod
    def clean_directory(directory: str):
        for filename in os.listdir(directory):
            file_path = os.path.join(directory, filename)
            try:
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error deleting {file_path}: {e}")

    @staticmethod
    def convert_mp4_to_wav(mp4_file_path: str, wav_file_path: str) -> bool:
        try:
            if not os.path.exists(mp4_file_path):
                logger.error(f"Video file does not exist: {mp4_file_path}")
                return False
                
            command = [
                "ffmpeg",
                "-i", mp4_file_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                "-y",
                wav_file_path
            ]
            
            result = subprocess.run(
                command, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode != 0:
                logger.error(f"FFmpeg error: {result.stderr}")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Conversion error: {str(e)}")
            return False