import re
from pathlib import Path

def parse_roadmap_markdown(file_path: str) -> dict:
    """
    Reads a local markdown file from the knowledge base and extracts milestone checkboxes.
    
    Args:
        file_path: The path to the .md file (e.g., 'obsidian_vault/docker_microservices.md').
        
    Returns:
        A dictionary containing the parsed roadmap with 'completed' and 'pending' milestones.
    """
    path = Path(file_path)
    
    if not path.exists() or path.suffix != '.md':
        return {"error": f"Markdown file not found at {file_path}"}
        
    content = path.read_text(encoding='utf-8')
    
    pending_tasks = re.findall(r'- \[\s\] (.*)', content)
    completed_tasks = re.findall(r'- \[[xX]\] (.*)', content)
    
    return {
        "file_name": path.name,
        "completed_milestones": completed_tasks,
        "pending_milestones": pending_tasks,
        "raw_content": content 
    }