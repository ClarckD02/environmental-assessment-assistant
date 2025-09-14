from abc import ABC, abstractmethod
import subprocess
import tempfile
import os

class ExtractText(ABC):
    """Abstract base class for extracting text from various file formats"""
    
    @abstractmethod
    def extract(self, file_bytes: bytes, filename: str = "uploaded.pdf") -> dict:
        """Extract text from file bytes and return structured result"""
        pass

class ExtractPdfs(ExtractText):
    """Extract text from PDF files using Poppler's pdftotext"""
    
    def __init__(self, layout_mode: bool = True):
        """
        Initialize PDF extractor
        
        Args:
            layout_mode: Whether to preserve layout formatting (-layout flag)
        """
        self.layout_mode = layout_mode
    
    def extract(self, pdf_bytes: bytes, filename: str = "uploaded.pdf") -> dict:
        """
        Extract text from PDF bytes using pdftotext
        
        Args:
            pdf_bytes: Raw PDF file bytes
            filename: Original filename for reference
            
        Returns:
            Dict containing filename, extracted text, and optional error
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = os.path.join(tmpdir, filename)
            txt_path = os.path.join(tmpdir, "output.txt")

            # Write the incoming bytes to a temp PDF file
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)

            try:
                # Build pdftotext command
                cmd = ["pdftotext"]
                if self.layout_mode:
                    cmd.append("-layout")
                cmd.extend([pdf_path, txt_path])
                
                # Run pdftotext on the temp PDF -> temp TXT
                subprocess.run(
                    cmd,
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )

                # Read back the extracted text
                with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()

                return {
                    "filename": filename,
                    "text": text
                }

            except subprocess.CalledProcessError as e:
                return {
                    "filename": filename,
                    "text": "",
                    "error": e.stderr.decode(errors="ignore")
                }