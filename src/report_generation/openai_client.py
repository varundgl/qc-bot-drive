# src/report_generation/openai_client.py
from openai import AzureOpenAI
import json
import os
import logging

logger = logging.getLogger(__name__)

class OpenAIClient:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            config = json.load(f)
            
        self.client = AzureOpenAI(
            azure_endpoint=config["AZURE_OPENAI_ENDPOINT"],
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=config["AZURE_OPENAI_APIVERSION"]
        )
        self.deployment_name = config["CHATGPT_MODEL"]
        
    def get_client(self) -> AzureOpenAI:
        return self.client
        
    def get_deployment(self) -> str:
        return self.deployment_name