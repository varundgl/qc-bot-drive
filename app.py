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
st.subheader("Automated Quality Control for Training Videos")

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
    
    # Processing steps
    steps = [
        "Downloading videos from Google Drive",
        "Processing mentor materials",
        "Generating transcripts",
        "Creating quality reports"
    ]
    
    for i, step in enumerate(steps):
        progress = int((i + 1) * 25)
        status_area.info(f"⏳ **Step {i+1}/4**: {step}")
        progress_bar.progress(progress)
        try:
            if i == 0:
                # Process mentor materials FIRST
                main_flow.process_mentor_materials(mentor_files)
            elif i == 1:
                # Download and process videos
                asyncio.run(main_flow.process_drive_url(drive_url))
            elif i == 2:
                # Transcripts generated automatically
                pass
            elif i == 3:
                # Generate reports
                main_flow.generate_quality_reports()
        except Exception as e:
            status_area.error(f"❌ Error in step {i+1}: {str(e)}")
            st.session_state.processing = False
            st.stop()
        time.sleep(1)  # Simulate processing time
    
    status_area.success("✅ Processing completed!")
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

# Display Reports
if st.session_state.reports_generated:
    # Sync reports before displaying
    sync_reports_from_drive(main_flow)
    
    st.divider()
    st.subheader("📋 Generated Reports")
    
    reports_dir = main_flow.paths["REPORTS"]
    report_files = [f for f in os.listdir(reports_dir) if f.endswith(".txt")]
    
    if report_files:
        for report_file in report_files:
            with st.expander(f"📝 {report_file.replace('report_', '').replace('.txt', '')}"):
                try:
                    with open(os.path.join(reports_dir, report_file), "r", encoding="utf-8") as f:
                        report_content = f.read()
                    
                    # Display report with formatting
                    st.markdown(report_content)
                    
                    # Download button
                    st.download_button(
                        label=f"Download {report_file}",
                        data=report_content,
                        file_name=report_file,
                        mime="text/plain",
                        key=f"dl_{report_file}"
                    )
                except Exception as e:
                    st.error(f"Error reading report: {str(e)}")
    else:
        st.info("No reports found. Please generate reports first.")