from pathlib import Path

import pypdf


def extract_text_from_pdf(file_path: str | Path) -> str:
    """
    Extracts text from a PDF file using pypdf.
    
    Args:
        file_path: Path to the PDF file.
        
    Returns:
        The extracted plain text.
    """
    reader = pypdf.PdfReader(str(file_path))
    
    extracted_text = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            extracted_text.append(text)
            
    return "\n\n".join(extracted_text)

