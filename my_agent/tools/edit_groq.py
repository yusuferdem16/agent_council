import os
from pathlib import Path
from openai import OpenAI
from groq import Groq

def edit_markdown_with_groq(file_path: str, edit_instructions: str) -> str:
    """
    Passes a local markdown file to Groq (LLaMA 3) to edit based on specific instructions.
    
    Args:
        file_path: The local path to the .md file.
        edit_instructions: What Groq should change, add, or fix in the file.
        
    Returns:
        A success message summarizing the edits, or an error string.
    """
    path = Path(file_path)
    if not path.exists() or path.suffix != '.md':
        return f"Error: Markdown file not found at {file_path}"
        
    original_content = path.read_text(encoding='utf-8')
    
    # Initialize the client pointing to Groq's OpenAI-compatible endpoint
    client = Groq()
    
    prompt = f"Edit the following markdown according to these instructions: {edit_instructions}\n\nORIGINAL CONTENT:\n{original_content}"
    
    try:
        # Using LLaMA 3 70B on Groq for high-speed, high-quality reasoning
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b", 
            messages=[
                {"role": "system", "content": "You are an expert technical editor. Return ONLY the raw updated markdown content. Do not enclose it in markdown code blocks. Keep all existing formatting intact unless instructed to change it."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2
        )
        
        updated_content = response.choices[0].message.content.strip()
        path.write_text(updated_content, encoding='utf-8')
        
        return f"Success! Groq edited {path.name} based on: '{edit_instructions}'"
        
    except Exception as e:
        return f"Groq failed to edit the file: {str(e)}"