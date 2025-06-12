# app.py
import streamlit as st
import os
import asyncio
import logging
import time
from src.preprocessing.gdrive_manager import GoogleDriveManager
from src.main_flow import MainFlow
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("qc_bot.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize MainFlow
main_flow = MainFlow("config/config.json")

# Streamlit UI
st.set_page_config(
    page_title="QC Report Generator", 
    page_icon="📊", 
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        font-weight: bold;
        padding: 10px 24px;
        border-radius: 5px;
    }
    .report-box {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        background-color: #f9f9f9;
    }
    .success-banner {
        background-color: #d4edda;
        color: #155724;
        padding: 15px;
        border-radius: 5px;
        margin: 20px 0;
        text-align: center;
    }
    .warning-banner {
        background-color: #fff3cd;
        color: #856404;
        padding: 15px;
        border-radius: 5px;
        margin: 20px 0;
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'reports_generated' not in st.session_state:
    st.session_state.reports_generated = False
if 'video_type' not in st.session_state:
    st.session_state.video_type = "conceptual"

# App header
st.title("📊 QC Report Generator")
st.subheader("Automated Quality Control for Recordings")

# Configuration Section
with st.expander("⚙️ Configuration", expanded=True):
    st.session_state.video_type = st.radio(
        "Select Video Type:",
        ["conceptual", "hands-on", "both"],
        format_func=lambda x: {
            "conceptual": "Conceptual Explanation",
            "hands-on": "Hands-on Demonstration",
            "both": "Both"
        }[x]
    )
    
    drive_url = st.text_input(
        "Google Drive Videos Folder URL:",
        placeholder="https://drive.google.com/drive/folders/1KSdVSVs_yN6FHvzH0i0CW2wNI0tCPhGt",
        help="URL of the folder containing videos"
    )
    
    mentor_files = {}
    if st.session_state.video_type in ["conceptual", "both"]:
        mentor_files["slides"] = st.file_uploader(
            "Upload Presentation (PPTX):", 
            type=["pptx", "ppt"]
        )
    
    if st.session_state.video_type in ["hands-on", "both"]:
        mentor_files["notebook"] = st.file_uploader(
            "Upload Notebook (IPYNB):", 
            type=["ipynb"]
        )
    
    if st.button("Generate Reports", disabled=st.session_state.processing):
        if not drive_url:
            st.error("Please enter a Google Drive URL")
        else:
            st.session_state.processing = True
            st.session_state.reports_generated = False

# Processing
if st.session_state.processing:
    status_area = st.empty()
    progress_bar = st.progress(0)

    # Step 1: Process mentor materials
    status_area.info("⏳ Step 1/4: Processing mentor materials...")
    try:
        main_flow.process_mentor_materials(mentor_files)
    except Exception as e:
        status_area.error(f"❌ Error in step 1: {str(e)}")
        st.session_state.processing = False
        st.stop()
    progress_bar.progress(25)
    time.sleep(1)

    # Step 2: Download and process videos
    status_area.info("⏳ Step 2/4: Downloading and processing videos...")
    from src.preprocessing.download_manager import GoogleDriveDownloader
    download_manager = GoogleDriveDownloader(main_flow.paths["VIDEOS"], main_flow.drive_folders)
    gdrive = download_manager.gdrive
    video_files = download_manager.list_all_videos(drive_url)
    total_videos = len(video_files)

    # Get all transcript files in Drive Transcripts folder
    transcript_drive_files = gdrive.list_txt_files(main_flow.drive_folders["TRANSCRIPTS"])
    transcript_names = {os.path.splitext(f['name'])[0] for f in transcript_drive_files}

    processed_videos = []
    report_files = []

    for idx, video in enumerate(video_files, 1):
        base_name = os.path.splitext(video['name'])[0]
        video_report_start = time.time()
        if base_name in transcript_names:
            status_area.info(f"✅ Transcript for video {idx}/{total_videos} ({video['name']}) already exists in Drive. Generating report...")
            processed_videos.append(base_name)
            # Download transcript if not local
            transcript_file = f"{base_name}.txt"
            local_transcript_path = os.path.join(main_flow.paths["TRANSCRIPTS"], transcript_file)
            if not os.path.exists(local_transcript_path):
                file_info = next((f for f in transcript_drive_files if f['name'] == transcript_file), None)
                if file_info:
                    gdrive.download_file(file_info["id"], local_transcript_path)
            # Generate report immediately
            from src.report_generation.openai_client import OpenAIClient
            from src.report_generation.report_generator import ReportGenerator
            with open("config/checklist.txt", "r") as f:
                checklist = f.read()
            openai_client = OpenAIClient("config/config.json")
            client = openai_client.get_client()
            deployment = openai_client.get_deployment()
            report_generator = ReportGenerator(client, deployment, checklist)
            report_generator.generate_reports(
                main_flow.paths["TRANSCRIPTS"],
                main_flow.paths["MENTOR_MATERIALS"],
                main_flow.paths["REPORTS"],
                main_flow.drive_folders["REPORTS"],
                only_base_names=[base_name]
            )
            video_report_end = time.time()
            minutes, seconds = divmod(int(video_report_end - video_report_start), 60)
            st.success(f"✅ Report generated for {base_name} ({minutes}m {seconds}s)")
            report_file = f"report_{base_name}.txt"
            report_path = os.path.join(main_flow.paths["REPORTS"], report_file)
            if os.path.exists(report_path):
                with st.expander(f"📝 {base_name}"):
                    with open(report_path, "r", encoding="utf-8") as f:
                        report_content = f.read()
                    st.markdown(report_content)
                    st.download_button(
                        label=f"Download {report_file}",
                        data=report_content,
                        file_name=report_file,
                        mime="text/plain",
                        key=f"dl_{report_file}"
                    )
            continue

        status_area.info(f"🎬 Processing video {idx}/{total_videos}: {video['name']}")
        st.write(f"- Downloading video...")
        local_video_path = os.path.join(main_flow.paths["VIDEOS"], video['name'])
        gdrive.download_file(video['id'], local_video_path)
        st.write(f"- Converting to audio...")
        audio_path = os.path.join(main_flow.paths["AUDIOS"], f"{base_name}.wav")
        from src.preprocessing.video_processor import VideoProcessor
        video_processor = VideoProcessor()
        if video_processor.convert_mp4_to_wav(local_video_path, audio_path):
            st.write(f"- Uploading audio to Drive...")
            download_manager.upload_to_drive(audio_path, "AUDIOS", "audio/wav")
            st.write(f"- Deleting video from Drive and local...")
            try:
                download_manager.delete_drive_file(video['id'])
            except Exception:
                pass
            try:
                os.remove(local_video_path)
            except Exception:
                pass
            st.write(f"- Generating transcript...")
            from src.preprocessing.transcript_generator import TranscriptGenerator
            transcript_generator = TranscriptGenerator(model_size="base.en", compute_type="int8")
            transcript_path = os.path.join(main_flow.paths["TRANSCRIPTS"], f"{base_name}.txt")
            if transcript_generator.transcribe_audio(audio_path, transcript_path):
                st.write(f"- Uploading transcript to Drive...")
                download_manager.upload_to_drive(transcript_path, "TRANSCRIPTS", "text/plain")
                st.write(f"- Deleting audio from Drive and local...")
                audio_drive_id = gdrive.find_file_by_name(main_flow.drive_folders["AUDIOS"], f"{base_name}.wav")
                if audio_drive_id:
                    try:
                        download_manager.delete_drive_file(audio_drive_id)
                    except Exception:
                        pass
                try:
                    os.remove(audio_path)
                except Exception:
                    pass
                processed_videos.append(base_name)
                # Generate report immediately
                from src.report_generation.openai_client import OpenAIClient
                from src.report_generation.report_generator import ReportGenerator
                with open("config/checklist.txt", "r") as f:
                    checklist = f.read()
                openai_client = OpenAIClient("config/config.json")
                client = openai_client.get_client()
                deployment = openai_client.get_deployment()
                report_generator = ReportGenerator(client, deployment, checklist)
                report_generator.generate_reports(
                    main_flow.paths["TRANSCRIPTS"],
                    main_flow.paths["MENTOR_MATERIALS"],
                    main_flow.paths["REPORTS"],
                    main_flow.drive_folders["REPORTS"],
                    only_base_names=[base_name]
                )
                video_report_end = time.time()
                minutes, seconds = divmod(int(video_report_end - video_report_start), 60)
                st.success(f"✅ Report generated for {base_name} ({minutes}m {seconds}s)")
                report_file = f"report_{base_name}.txt"
                report_path = os.path.join(main_flow.paths["REPORTS"], report_file)
                if os.path.exists(report_path):
                    with st.expander(f"📝 {base_name}"):
                        with open(report_path, "r", encoding="utf-8") as f:
                            report_content = f.read()
                        st.markdown(report_content)
                        st.download_button(
                            label=f"Download {report_file}",
                            data=report_content,
                            file_name=report_file,
                            mime="text/plain",
                            key=f"dl_{report_file}"
                        )
            else:
                st.write(f"❌ Failed to generate transcript for {video['name']}")
        else:
            st.write(f"❌ Failed to convert video: {video['name']}")
        progress_bar.progress(25 + int(50 * idx / total_videos))
        time.sleep(1)

    progress_bar.progress(100)
    time.sleep(1)

    st.session_state.processing = False
    st.session_state.reports_generated = True
    st.balloons()

# Sync reports from Google Drive
def sync_reports_from_drive(main_flow):
    gdrive = GoogleDriveManager()
    report_drive_files = gdrive.list_txt_files(main_flow.drive_folders["REPORTS"])
    for file in report_drive_files:
        local_path = os.path.join(main_flow.paths["REPORTS"], file["name"])
        if not os.path.exists(local_path):
            gdrive.download_file(file["id"], local_path)
