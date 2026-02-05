from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.agents.architect import ArchitectAgent
from app.agents.virtuoso import VirtuosoAgent
from app.agents.sentinel import SentinelAgent
from app.agents.oracle import OracleAgent
from app.agents.watcher import WatcherAgent
from app.agents.advisor import AdvisorAgent

router = APIRouter()

class PromptRequest(BaseModel):
    prompt: str
    project_id: str

class VerifyRequest(BaseModel):
    url: str
    project_id: str

@router.post("/architect/design")
async def run_architect(request: PromptRequest):
    """
    Design a system blueprint from a user prompt.
    Returns the architectural blueprint JSON.
    """
    agent = ArchitectAgent()
    result = await agent.design_system(request.prompt)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result

@router.post("/virtuoso/generate")
async def run_virtuoso(file_path: str, description: str):
    """
    Generate code for a specific file based on description.
    Note: This is a single-file generation endpoint.
    For full project generation, use the orchestrator workflow.
    """
    agent = VirtuosoAgent()
    code = await agent.generate_code(file_path, description)
    return {"code": code}

@router.post("/sentinel/audit")
async def run_sentinel(file_path: str, code: str):
    """
    Audit a single file for security vulnerabilities.
    Returns security report with findings.
    """
    agent = SentinelAgent()
    result = await agent.audit_code(file_path, code)
    return result

@router.post("/watcher/verify")
async def run_watcher(request: VerifyRequest):
    """
    FIXED: Properly defined endpoint for Watcher verification.
    Verifies a running project at the given URL.
    """
    agent = WatcherAgent()
    result = await agent.verify_url(request.url)
    return result

@router.post("/oracle/generate-tests")
async def run_oracle(request: PromptRequest):
    """
    NEW: Generate tests for a project.
    Returns test files and test report.
    """
    agent = OracleAgent()
    # This would need the actual files to generate tests
    # For now, we return a placeholder response
    return {
        "status": "oracle_endpoint_placeholder",
        "message": "Use the orchestrator workflow for full test generation"
    }

@router.post("/advisor/analyze")
async def run_advisor(request: PromptRequest):
    """
    NEW: Analyze deployment strategy for a project.
    Returns deployment recommendations.
    """
    agent = AdvisorAgent()
    # This would need security and visual reports
    # For now, we return a placeholder response
    return {
        "status": "advisor_endpoint_placeholder",
        "message": "Use the orchestrator workflow for full deployment analysis"
    }

from app.core.filesystem import read_project_files, read_file

@router.get("/projects/{project_id}/files")
async def get_project_files_route(project_id: str):
    """
    Get all files for a project with their content.
    Returns a dictionary mapping file paths to their content.
    Optimized for small projects (full file tree with content).
    """
    files = read_project_files(project_id)
    return files

@router.get("/projects/{project_id}/files/content")
async def get_file_content_route(project_id: str, path: str):
    """
    Get content of a specific file in a project.
    Used for lazy-loading individual files in larger projects.
    """
    content = read_file(project_id, path)
    if content is None:
        raise HTTPException(status_code=404, detail="File not found")
    return {"content": content}