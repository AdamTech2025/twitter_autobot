import os
import time
import logging
from typing import Dict, Any, Union
from dotenv import load_dotenv
from openai import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

# Basic logging configuration
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# OpenRouter configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = "openai/gpt-4o-mini-search-preview"
OPENROUTER_TEMPERATURE = float(os.getenv("OPENROUTER_TEMPERATURE", "0.0"))
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "")
DEFAULT_TEMP = 0.0

class LLMService:
    def __init__(self, temperature=DEFAULT_TEMP, max_retries=3, 
                 retry_delay=2, model=OPENROUTER_MODEL):
        if not OPENROUTER_API_KEY:
            raise ValueError("OpenRouter API key not found in environment variables")
        
        self.temperature = temperature
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.model = model
        self._initialize_client()
    
    def _initialize_client(self):
        try:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=OPENROUTER_API_KEY
            )
            # Use print to ensure this message is shown regardless of logging level
            print(f"Initialized OpenRouter with model: {self.model} (temp: {self.temperature})")
            logger.info(f"Initialized OpenRouter with model: {self.model} (temp: {self.temperature})")
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter: {e}")
            raise ValueError(f"Failed to initialize client: {e}")
    
    def set_model(self, model_name: str):
        if model_name and model_name != self.model:
            self.model = model_name
            # Use print to ensure this message is shown regardless of logging level
            print(f"Updated model to: {model_name}")
            logger.info(f"Updated model to: {model_name}")
            return True
        return False
    
    def set_temperature(self, temperature: float):
        if temperature is not None and temperature != self.temperature:
            self.temperature = temperature
            logger.info(f"Updated temperature to: {temperature}")
            return True
        return False
    
    def generate_response(self, prompt: Union[str, Dict], image_url: str = None):
        for attempt in range(self.max_retries + 1):
            try:
                messages = []
                if isinstance(prompt, str):
                    content = [{"type": "text", "text": prompt}]
                    if image_url:
                        content.append({
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        })
                    messages.append({"role": "user", "content": content})
                elif isinstance(prompt, dict):
                    messages.append(prompt)
                
                # Print status before hitting the API
                print(f"--> Calling LLM API: Model={self.model}, Temp={self.temperature}")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    extra_headers={
                        "HTTP-Referer": OPENROUTER_SITE_URL,
                        "X-Title": OPENROUTER_SITE_NAME
                    }
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                if attempt < self.max_retries:
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    time.sleep(self.retry_delay)
                else:
                    raise Exception(f"Failed after {self.max_retries} attempts: {e}")
    
    def invoke_chain(self, prompt_template: Union[str, PromptTemplate], inputs: Dict[str, Any]):
        if isinstance(prompt_template, str):
            import re
            variables = list(set(re.findall(r'\{([^{}]*)\}', prompt_template)))
            prompt_template = PromptTemplate(
                template=prompt_template,
                input_variables=variables
            )
        formatted_prompt = prompt_template.format(**inputs)
        return self.generate_response(formatted_prompt)

# Singleton instance
llm_service = LLMService()

# Public API functions
def get_service():
    return llm_service

def set_model(model_name: str):
    return llm_service.set_model(model_name)

def set_temperature(temperature: float):
    return llm_service.set_temperature(temperature)

def generate_response(prompt: Union[str, Dict], image_url: str = None):
    return llm_service.generate_response(prompt, image_url)

def process_prompt(prompt_template: Union[str, PromptTemplate], inputs: Dict[str, Any]):
    return llm_service.process_prompt(prompt_template, inputs)