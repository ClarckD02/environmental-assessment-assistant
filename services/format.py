from abc import ABC, abstractmethod
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()

class TextFormatter(ABC):
    """Abstract base class for formatting extracted text"""
    
    @abstractmethod
    def format(self, extracted_text: str) -> str:
        """Format the extracted text according to implementation-specific rules"""
        pass

class GeminiFormatter(TextFormatter):
    """Base class for Gemini-powered formatters"""
    
    _model = None

    @classmethod
    def _get_model(cls, model_name="gemini-2.0-flash"):
        """Get or create Gemini model instance"""
        if cls._model is None:
            api_key = os.getenv("GEMINI_API_KEY")  
            if not api_key:
                raise RuntimeError("Missing GEMINI_API_KEY")
            genai.configure(api_key=api_key)
            cls._model = genai.GenerativeModel(model_name)
        return cls._model

    def _format_with_prompt_file(self, extracted_text: str, prompt_path: str) -> str:
        """Common method to format text using a prompt file"""
        with open(prompt_path, "r", encoding="utf-8") as f:
            base_prompt = f.read().strip()

        full_prompt = f"{base_prompt}\n\n{extracted_text}"

        model = self._get_model()
        resp = model.generate_content(full_prompt)
        return resp.text or ""

class EDRReportFormatter(GeminiFormatter):
    """Formatter specifically for EDR (Environmental Data Resources) reports"""
    
    def __init__(self, prompt_path: str = "edr_format.txt"):
        self.prompt_path = prompt_path
    
    def format(self, extracted_text: str) -> str:
        """Format EDR report text using EDR-specific formatting rules"""
        return self._format_with_prompt_file(extracted_text, self.prompt_path)

class ERISReportFormatter(GeminiFormatter):
    """Formatter specifically for ERIS reports"""
    
    def __init__(self, prompt_path: str = "eris_format.txt"):
        self.prompt_path = prompt_path
    
    def format(self, extracted_text: str) -> str:
        """Format ERIS report text using ERIS-specific formatting rules"""
        return self._format_with_prompt_file(extracted_text, self.prompt_path)
