# src/report_generation/report_generator.py
import os
import glob
import time
import logging
from typing import Dict
from src.preprocessing.gdrive_manager import GoogleDriveManager  # Add this import if not present

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, openai_client, deployment_name: str, checklist: str):
        self.client = openai_client
        self.deployment_name = deployment_name
        self.checklist = checklist

    # Updated quality_check method with enhanced prompt
    def quality_check(self, transcript_content: str, material_type: str, material_content: str = None) -> str:
        material_context = ""
        if material_content:
            if material_type == "slides":
                material_context = f"\n### SLIDE CONTENT ###\n{material_content}"
            elif material_type == "notebook":
                material_context = f"\n### NOTEBOOK CONTENT ###\n{material_content}"

        user_input = f"""
    ### ROLE ###
    You are a meticulous educational content quality inspector. Your task is to rigorously evaluate video transcripts against our quality checklist.

    ### EVALUATION MATERIALS ###
    1. VIDEO TRANSCRIPT:
    {transcript_content}
    2. SUPPORTING MATERIALS:
    {material_context if material_context else "N/A"}

    ### QUALITY CHECKLIST ###
    {self.checklist}

    ### CORE INSTRUCTIONS ###
    1. ITEM-BY-ITEM ASSESSMENT:
    - For EACH checklist sub-item (1a, 1b, etc.):
        * ✅ = Fully meets criteria
        * ❌ = Fails to meet criteria
        * N/A = Not applicable to this content
    - Provide CONCISE justifications:
        * For ❌: State EXACTLY what's missing/wrong with specific evidence
        * For ✅: Note key strengths that satisfy criteria
        * For N/A: Explain why it doesn't apply

    2. ISSUE ANALYSIS:
    - "What Went Wrong":
        * ONLY include ❌ items from checklist
        * For EACH failure:
            - Identify SPECIFIC failure points with timestamps/locations
            - Explain CONSEQUENCES of the issue
            - Cite RELEVANT evidence from materials
        * Format: 
        [Item ID]: [Failure description]
            - Evidence: [Direct quote/reference]
            - Impact: [Why this matters]

    3. IMPROVEMENT RECOMMENDATIONS:
    - "How to Improve":
        * Provide ACTIONABLE solutions for EACH identified issue
        * Solutions must be:
            - Specific and measurable
            - Directly address the root cause
            - Include implementation examples where possible
        * Format:
        [Item ID]: [Solution]
            - Implementation: [Concrete steps]
            - Expected Outcome: [Quality improvement]

    ### REQUIRED OUTPUT FORMAT ###
    [Checklist Evaluation]
    1a: [✅/❌/N/A] [Precise justification (25 words max)]
    1b: [✅/❌/N/A] [Precise justification (25 words max)]
    ...
    8b: [✅/❌/N/A] [Precise justification (25 words max)]

    What Went Wrong:
    - 1b: Missing logical progression between concepts
    Evidence: "First we discuss X... then suddenly jump to Z" (Transcript 2:15)
    Impact: Learners lose conceptual thread
    - 3c: Mispronounced technical terms
    Evidence: "Pandas pronounced as /pændæs/ instead of /'pændæz/" (0:45, 1:30)
    Impact: Reduces content credibility

    How to Improve:
    - 1b: Implement concept bridging
    Implementation: Add transition statements - "Now that we understand X, let's see how it connects to Z..."
    Outcome: Smoother learning progression
    - 3c: Technical term pronunciation guide
    Implementation: Create glossary with IPA transcriptions, practice before recording
    Outcome: Professional delivery of technical content
    """

        try:
            logger.info("Calling Azure OpenAI API for quality check...")
            logger.info(f"Transcript length: {len(transcript_content)}")
            logger.info(f"Checklist length: {len(self.checklist)}")
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an uncompromising quality assurance specialist with expertise in "
                                "educational content evaluation. Be brutally honest and evidence-driven."
                    },
                    {"role": "user", "content": user_input}
                ],
                temperature=0.1,  # Lowered for more deterministic output
                max_tokens=4096,
                top_p=0.9,
                frequency_penalty=0.3  # Discourage repetition
            )
            logger.info("Received response from Azure OpenAI API.")
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Azure OpenAI error: {str(e)}")
            return f"Error in quality check: {str(e)}"
    def generate_reports(self, transcript_path: str, mentor_materials_path: str, reports_dir: str, drive_folder_id: str, only_base_names=None):
        os.makedirs(reports_dir, exist_ok=True)
        
        # Get all transcript files
        video_transcripts = []
        for file_path in glob.glob(os.path.join(transcript_path, "*.txt")):
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            if only_base_names and base_name not in only_base_names:
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                video_transcripts.append({
                    "path": file_path,
                    "content": f.read(),
                    "base_name": base_name
                })

        if not video_transcripts:
            logger.error("No video transcripts found!")
            return

        # Get mentor materials
        mentor_contents: Dict[str, str] = {}
        for file_path in glob.glob(os.path.join(mentor_materials_path, "*.txt")):
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            with open(file_path, 'r', encoding='utf-8') as f:
                mentor_contents[base_name] = f.read()

        # Prepare Drive manager for report uploads
        gdrive = GoogleDriveManager()

        # Generate reports
        for video in video_transcripts:
            base_name = video["base_name"]
            logger.info(f"Generating report for: {base_name}")
            
            material_content = mentor_contents.get(base_name, "")
            material_type = ""
            
            if "slide" in base_name.lower():
                material_type = "slides"
            elif "notebook" in base_name.lower():
                material_type = "notebook"
            
            report = self.quality_check(
                video["content"], 
                material_type, 
                material_content
            )

            report_file = os.path.join(reports_dir, f"report_{base_name}.txt")
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            logger.info(f"Report saved to {report_file}")

            # --- Ensure no duplicate in Drive: delete if exists, then upload ---
            # drive_folder_id is now passed as an argument

            # Find and delete duplicate in Drive
            drive_file_id = gdrive.find_file_by_name(drive_folder_id, f"report_{base_name}.txt")
            if drive_file_id:
                gdrive.delete_file(drive_file_id)
                logger.info(f"Deleted duplicate report in Drive: report_{base_name}.txt")

            # Upload new report
            gdrive.upload_file(report_file, drive_folder_id, "text/plain")
            logger.info(f"Uploaded report to Drive: report_{base_name}.txt")

            time.sleep(2)  # Avoid rate limiting