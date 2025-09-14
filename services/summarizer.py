from abc import ABC, abstractmethod
from anthropic import Anthropic
import os
from prompts.edr_summarization import (
    build_section_521_prompt,  # EDR sections
    build_section_522_prompt,
    parse_extracted_address,
    EDR_DEFAULT_DATABASES_LIST
)
from prompts.eris_summarization import(
    build_section_523_prompt,  # ERIS sections  
    build_section_524_prompt,
    parse_extracted_address,
    DEFAULT_DATABASES_LIST
)
from dotenv import load_dotenv

load_dotenv()

class SectionSummarizer(ABC):
    """Abstract base class for section summarizers"""
    
    @abstractmethod
    async def generate_section_streaming(self, websocket, formatted_text: str, **kwargs) -> dict:
        """Generate a section with streaming output"""
        pass

class ClaudeSummarizer(SectionSummarizer):
    """Base class for Claude-powered summarizers"""
    
    _client: Anthropic = None
    _model: str = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20240620")

    @classmethod
    def _get_client(cls) -> Anthropic:
        if cls._client is None:
            api_key = os.getenv("CLAUDE")
            if not api_key:
                raise RuntimeError("Missing Anthropic API key.")
            cls._client = Anthropic(api_key=api_key)
        return cls._client

    async def _stream_response(self, websocket, system_prompt: str, user_content: str, 
                              max_tokens: int = 1500, temperature: float = 0.0) -> str:
        """Common streaming logic for all Claude summarizers"""
        client = self._get_client()
        
        full_content = ""
        buffer = ""
        
        stream = client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        
        with stream as message_stream:
            for chunk in message_stream:
                if chunk.type == "content_block_delta":
                    text_chunk = chunk.delta.text
                    full_content += text_chunk
                    buffer += text_chunk
                    
                    # Send buffer when we have complete words or hit punctuation
                    if any(char in buffer for char in [' ', '\n', '.', '!', '?', ':', ';', ',']):
                        await websocket.send_text(buffer)
                        buffer = ""
        
        # Send any remaining buffer content
        if buffer:
            await websocket.send_text(buffer)
        
        return full_content.strip()

# EDR Report Summarizers (Sections 5.2.1 and 5.2.2)
class EDRSection521Summarizer(ClaudeSummarizer):
    """EDR Section 5.2.1 - Subject Property Environmental Database Listings"""
    
    async def generate_section_streaming(self, websocket, formatted_text: str, 
                                       databases_list: list[str] = None,
                                       temperature: float = 0.0,
                                       max_tokens: int = 1500) -> dict:
        dbs = databases_list or DEFAULT_DATABASES_LIST
        system_prompt = build_section_521_prompt(dbs)
        
        content = await self._stream_response(websocket, system_prompt, formatted_text, 
                                            max_tokens, temperature)
        
        subject_address = parse_extracted_address(content)
        
        return {
            "section_content": content,
            "subject_address": subject_address
        }

class EDRSection522Summarizer(ClaudeSummarizer):
    """EDR Section 5.2.2 - Surrounding Area Environmental Database Listings"""
    
    async def generate_section_streaming(self, websocket, formatted_text: str,
                                       subject_address: str,
                                       groundwater_flow: str = None,
                                       distance_data: dict = None,
                                       databases_list: list[str] = None,
                                       temperature: float = 0.0,
                                       max_tokens: int = 2000) -> str:
        dbs = databases_list or DEFAULT_DATABASES_LIST
        system_prompt = build_section_522_prompt(dbs)
        
        user_content = f"Subject Property Address: {subject_address}\n"
        if groundwater_flow:
            user_content += f"Groundwater Flow Direction: {groundwater_flow}\n"
        if distance_data:
            user_content += f"Distance Data: {distance_data}\n"
        user_content += f"\nStructured content:\n{formatted_text}"
        
        return await self._stream_response(websocket, system_prompt, user_content, 
                                         max_tokens, temperature)

# ERIS Report Summarizers (Sections 5.2.3 and 5.2.4)
class ERISSection523Summarizer(ClaudeSummarizer):
    """ERIS Section 5.2.3 - Subject Property Environmental Database Listings"""
    
    async def generate_section_streaming(self, websocket, formatted_text: str,
                                       databases_list: list[str] = None,
                                       temperature: float = 0.0,
                                       max_tokens: int = 1500) -> dict:
        dbs = databases_list or DEFAULT_DATABASES_LIST
        system_prompt = build_section_523_prompt(dbs)
        
        content = await self._stream_response(websocket, system_prompt, formatted_text, 
                                            max_tokens, temperature)
        
        subject_address = parse_extracted_address(content)
        
        return {
            "section_content": content,
            "subject_address": subject_address
        }

class ERISSection524Summarizer(ClaudeSummarizer):
    """ERIS Section 5.2.4 - Surrounding Area Environmental Database Listings"""
    
    async def generate_section_streaming(self, websocket, formatted_text: str,
                                       subject_address: str,
                                       groundwater_flow: str = None,
                                       distance_data: dict = None,
                                       databases_list: list[str] = None,
                                       temperature: float = 0.0,
                                       max_tokens: int = 2000) -> str:
        dbs = databases_list or DEFAULT_DATABASES_LIST
        system_prompt = build_section_524_prompt(dbs)
        
        user_content = f"Subject Property Address: {subject_address}\n"
        if groundwater_flow:
            user_content += f"Groundwater Flow Direction: {groundwater_flow}\n"
        if distance_data:
            user_content += f"Distance Data: {distance_data}\n"
        user_content += f"\nStructured content:\n{formatted_text}"
        
        return await self._stream_response(websocket, system_prompt, user_content, 
                                         max_tokens, temperature)

# Chat Summarizer
class IntelligentChatSummarizer(ClaudeSummarizer):
    """Handle intelligent chat conversations"""
    
    async def generate_section_streaming(self, websocket, context: str,
                                       temperature: float = 0.1,
                                       max_tokens: int = 800) -> str:
        return await self._stream_response(websocket, "", context, max_tokens, temperature)

# Factory for creating appropriate summarizers
class SummarizerFactory:
    @staticmethod
    def get_summarizer(report_type: str, section: str) -> SectionSummarizer:
        """Factory method to get the appropriate summarizer"""
        if report_type.upper() == "EDR":
            if section == "5.2.1":
                return EDRSection521Summarizer()
            elif section == "5.2.2":
                return EDRSection522Summarizer()
        elif report_type.upper() == "ERIS":
            if section == "5.2.3":
                return ERISSection523Summarizer()
            elif section == "5.2.4":
                return ERISSection524Summarizer()
        elif section == "chat":
            return IntelligentChatSummarizer()
        
        raise ValueError(f"Unknown report type '{report_type}' or section '{section}'")