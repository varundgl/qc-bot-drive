# src/report_generation/report_generator.py
import os
import glob
import time
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class ReportGenerator:
    def __init__(self, openai_client, deployment_name: str, checklist: str):
        self.client = openai_client
        self.deployment_name = deployment_name
        self.checklist = checklist

    def quality_check(self, transcript_content: str, material_type: str, material_content: str = None) -> str:
        material_context = ""
        if material_content:
            if material_type == "slides":
                material_context = f"\n### SLIDE CONTENT ###\n{material_content}"
            elif material_type == "notebook":
                material_context = f"\n### NOTEBOOK CONTENT ###\n{material_content}"

        user_input = f"""
### VIDEO TRANSCRIPT ###
{transcript_content}
{material_context}

### TASK ###
Review using this checklist:
{self.checklist}

### INSTRUCTIONS ###
1. For EACH checklist item:
   - Respond using format: [✅/❌/N/A] [Brief explanation]
2. After checklist, provide:
   - "What Went Wrong:" (bullet points)
   - "How to Improve:" (bullet points)
3. Use ONLY this format:

### RESPONSE FORMAT ###
1a: [✅/❌/N/A] [Explanation]
...
8b: [✅/❌/N/A] [Explanation]

What Went Wrong:
- [Issue 1]
- [Issue 2]

How to Improve:
- [Recommendation 1]
- [Recommendation 2]
"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=[
                    {"role": "system", "content": "You are an analytical quality assurance assistant."},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.2,
                max_tokens=4096,
                top_p=0.95
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Azure OpenAI error: {str(e)}")
            return f"Error in quality check: {str(e)}"

    def generate_reports(self, transcript_path: str, mentor_materials_path: str, reports_dir: str):
        # Create reports directory if not exists
        os.makedirs(reports_dir, exist_ok=True)
        
        # Get all transcript files
        video_transcripts = []
        for file_path in glob.glob(os.path.join(transcript_path, "*.txt")):
            with open(file_path, 'r', encoding='utf-8') as f:
                video_transcripts.append({
                    "path": file_path,
                    "content": f.read(),
                    "base_name": os.path.splitext(os.path.basename(file_path))[0]
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
            time.sleep(2)  # Avoid rate limiting