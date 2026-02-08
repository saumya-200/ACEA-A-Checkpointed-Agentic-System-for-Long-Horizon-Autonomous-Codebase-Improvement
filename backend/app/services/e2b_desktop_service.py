# E2B Desktop Service
# Creates full Desktop environments with VS Code + Chrome via noVNC streaming

import os
import asyncio
import logging
from typing import Dict, Optional, Any, Callable, List
from pathlib import Path
from datetime import datetime

from e2b_desktop import Sandbox

from app.core.filesystem import read_project_files, write_project_files, BASE_PROJECTS_DIR

logger = logging.getLogger(__name__)

# E2B Configuration
E2B_API_KEY = os.getenv("E2B_API_KEY", "")
E2B_TIMEOUT_SECONDS = int(os.getenv("E2B_TIMEOUT", "600"))  # 10 min default
DESKTOP_RESOLUTION = os.getenv("E2B_DESKTOP_RESOLUTION", "1920x1080")


class E2BDesktopService:
    """Manages full Desktop environments via E2B Desktop SDK with noVNC streaming."""
    
    def __init__(self):
        self.active_sandboxes: Dict[str, Sandbox] = {}  # project_id -> sandbox
        self.sandbox_info: Dict[str, Dict] = {}  # project_id -> {sandbox_id, stream_url, etc}
        
        if E2B_API_KEY:
            logger.info(f"E2BDesktopService: API key configured, timeout={E2B_TIMEOUT_SECONDS}s")
        else:
            logger.warning("E2BDesktopService: No E2B_API_KEY found in environment!")
    
    def _detect_project_config(self, blueprint: dict, files: Dict[str, str]) -> Dict[str, Any]:
        """Detect project type and return install/run commands."""
        tech_stack = blueprint.get("tech_stack", "")
        if isinstance(tech_stack, list):
            tech_stack = " ".join(tech_stack).lower()
        else:
            tech_stack = str(tech_stack).lower()
        
        # Check for specific files
        has_package_json = any("package.json" in f for f in files.keys())
        has_requirements_txt = any("requirements.txt" in f for f in files.keys())
        has_index_html = any("index.html" in f for f in files.keys())
        
        # Detect framework
        is_nextjs = any("next.config" in f for f in files.keys()) or "next" in tech_stack
        is_vite = any("vite.config" in f for f in files.keys()) or "vite" in tech_stack
        is_react = has_package_json and ("react" in tech_stack or any(".jsx" in f or ".tsx" in f for f in files.keys()))
        is_flask = has_requirements_txt and ("flask" in tech_stack or any("app.py" in f for f in files.keys()))
        is_fastapi = "fastapi" in tech_stack
        
        config = {
            "install_cmd": "",
            "run_cmd": "",
            "port": 3000,
            "work_dir": "/home/user/project",
            "project_type": "unknown",
            "preview_url": "http://localhost:3000"
        }
        
        if is_nextjs:
            config.update({
                "install_cmd": "npm install",
                "run_cmd": "npm run dev",
                "port": 3000,
                "project_type": "nextjs",
                "preview_url": "http://localhost:3000"
            })
        elif is_vite:
            config.update({
                "install_cmd": "npm install",
                "run_cmd": "npm run dev -- --host 0.0.0.0",
                "port": 5173,
                "project_type": "vite",
                "preview_url": "http://localhost:5173"
            })
        elif is_react:
            config.update({
                "install_cmd": "npm install",
                "run_cmd": "npm start",
                "port": 3000,
                "project_type": "react",
                "preview_url": "http://localhost:3000"
            })
        elif has_package_json:
            config.update({
                "install_cmd": "npm install",
                "run_cmd": "npm start",
                "port": 3000,
                "project_type": "nodejs",
                "preview_url": "http://localhost:3000"
            })
        elif is_fastapi:
            config.update({
                "install_cmd": "pip install -r requirements.txt" if has_requirements_txt else "pip install fastapi uvicorn",
                "run_cmd": "uvicorn main:app --reload --host 0.0.0.0 --port 8000",
                "port": 8000,
                "project_type": "fastapi",
                "preview_url": "http://localhost:8000"
            })
        elif is_flask:
            config.update({
                "install_cmd": "pip install -r requirements.txt" if has_requirements_txt else "pip install flask",
                "run_cmd": "flask run --host=0.0.0.0 --port=5000",
                "port": 5000,
                "project_type": "flask",
                "preview_url": "http://localhost:5000"
            })
        elif has_index_html:
            config.update({
                "install_cmd": "",
                "run_cmd": "python3 -m http.server 3000",
                "port": 3000,
                "project_type": "static",
                "preview_url": "http://localhost:3000"
            })
        
        return config
    
    def _create_instructions_file(self, config: dict, files: dict) -> str:
        """Generate helpful INSTRUCTIONS.md content."""
        project_type = config.get("project_type", "unknown")
        port = config.get("port", 3000)
        run_cmd = config.get("run_cmd", "")
        preview_url = config.get("preview_url", "http://localhost:3000")
        
        file_list = "\n".join(f"- `{f}`" for f in sorted(files.keys())[:20])
        if len(files) > 20:
            file_list += f"\n- ... and {len(files) - 20} more files"
        
        content = f"""# 🚀 Welcome to Your ACEA Studio Desktop!

## Your App is Running!
Your **{project_type}** app is running on port {port}.

**Preview URL:** {preview_url}

Hot-reload is **enabled** - edit any file and save (Ctrl+S) to see changes instantly!

## Project Structure
{file_list}

## Helpful Commands

Open a terminal in VS Code with **Ctrl+`** and run:

```bash
# Restart the development server
{run_cmd}

# Install a new package
{"npm install <package>" if "npm" in config.get("install_cmd", "") else "pip install <package>"}
```

## Tips
1. **Chrome** is on the right - it shows your running app
2. **VS Code** is on the left - edit your code here
3. **Save** with Ctrl+S to trigger hot-reload
4. Files are synced back when you Stop or Download

---
*Generated by ACEA Studio - Autonomous Code Evolution Agent*
"""
        return content
    
    async def create_desktop_environment(
        self,
        project_id: str,
        blueprint: dict,
        on_progress: Optional[Callable[[str], None]] = None
    ) -> Dict[str, Any]:
        """
        Create a full Desktop environment with VS Code + Chrome.
        
        Returns:
            {
                "status": "ready" | "error",
                "stream_url": "https://...",
                "sandbox_id": "...",
                "message": str,
                "logs": str,
                "project_type": str
            }
        """
        logs = []
        
        def log(msg: str):
            logs.append(msg)
            logger.info(f"[Desktop:{project_id}] {msg}")
            if on_progress:
                on_progress(msg)
        
        def error_response(message: str, user_message: str = None) -> Dict[str, Any]:
            return {
                "status": "error",
                "stream_url": None,
                "sandbox_id": None,
                "message": user_message or message,
                "logs": "\n".join(logs)
            }
        
        # === API Key Check ===
        if not E2B_API_KEY:
            return error_response(
                "E2B_API_KEY not configured",
                "E2B API key missing. Add E2B_API_KEY to your .env file."
            )
        
        # === Close existing sandbox for this project ===
        if project_id in self.active_sandboxes:
            log("Closing existing sandbox...")
            await self.stop_sandbox(project_id)
        
        try:
            # === Read project files ===
            project_files = read_project_files(project_id)
            if not project_files:
                return error_response("No project files found", "Project is empty - nothing to run.")
            
            log(f"📁 Found {len(project_files)} files")
            
            # === Detect project configuration ===
            config = self._detect_project_config(blueprint, project_files)
            log(f"🔍 Detected: {config['project_type']}")
            
            # === Create Desktop sandbox ===
            log("🖥️ Creating E2B Desktop sandbox...")
            try:
                desktop = Sandbox.create(api_key=E2B_API_KEY)
                sandbox_id = desktop.sandbox_id
                log(f"✅ Desktop sandbox ready: {sandbox_id[:8]}...")
            except Exception as e:
                error_str = str(e).lower()
                if "unauthorized" in error_str or "invalid" in error_str:
                    return error_response(str(e), "Invalid E2B API key. Please check your .env file.")
                elif "rate limit" in error_str:
                    return error_response(str(e), "E2B rate limit reached. Please try again.")
                else:
                    return error_response(str(e), f"Failed to create Desktop sandbox: {str(e)}")
            
            # === Upload project files ===
            log("📤 Uploading project files...")
            work_dir = config["work_dir"]
            uploaded = 0
            
            for file_path, content in project_files.items():
                if file_path == "blueprint.json":
                    continue
                
                full_path = f"{work_dir}/{file_path}"
                
                try:
                    # Create parent directories
                    parent_dir = str(Path(full_path).parent)
                    desktop.commands.run(f"mkdir -p {parent_dir}")
                    desktop.files.write(full_path, content)
                    uploaded += 1
                except Exception as e:
                    log(f"⚠️ Failed to upload {file_path}: {str(e)[:50]}")
            
            log(f"✅ Uploaded {uploaded} files")
            
            # === Create INSTRUCTIONS.md ===
            try:
                instructions = self._create_instructions_file(config, project_files)
                desktop.files.write(f"{work_dir}/INSTRUCTIONS.md", instructions)
                log("📝 Created INSTRUCTIONS.md")
            except Exception as e:
                log(f"⚠️ Could not create INSTRUCTIONS.md: {str(e)[:50]}")
            
            # === Install dependencies ===
            if config["install_cmd"]:
                log(f"📦 Installing dependencies: {config['install_cmd']}")
                try:
                    result = desktop.commands.run(
                        f"cd {work_dir} && {config['install_cmd']}",
                        timeout=300
                    )
                    if result.exit_code != 0:
                        log(f"⚠️ Install warning: {result.stderr[:200] if result.stderr else 'check logs'}")
                    else:
                        log("✅ Dependencies installed")
                except Exception as e:
                    log(f"⚠️ Install error: {str(e)[:100]}")
            
            # === Start dev server in background ===
            if config["run_cmd"]:
                log(f"🏃 Starting dev server: {config['run_cmd']}")
                try:
                    desktop.commands.run(
                        f"cd {work_dir} && {config['run_cmd']} > /tmp/app.log 2>&1 &",
                        background=True
                    )
                    log(f"✅ Dev server starting on port {config['port']}")
                except Exception as e:
                    log(f"⚠️ Dev server start error: {str(e)[:100]}")
            
            # === Wait for server to start ===
            log("⏳ Waiting for dev server...")
            await asyncio.sleep(5)
            
            # === Launch VS Code ===
            log("🖥️ Launching VS Code...")
            try:
                desktop.launch("code", args=[work_dir])
                await asyncio.sleep(3)
                log("✅ VS Code launched")
            except Exception as e:
                log(f"⚠️ VS Code launch error: {str(e)[:100]}")
            
            # === Launch Chrome with preview URL ===
            log("🌐 Launching Chrome...")
            try:
                desktop.launch("google-chrome", args=[
                    "--no-first-run",
                    "--no-default-browser-check",
                    config["preview_url"]
                ])
                await asyncio.sleep(3)
                log("✅ Chrome launched")
            except Exception as e:
                log(f"⚠️ Chrome launch error: {str(e)[:100]}")
            
            # === Arrange windows side-by-side ===
            log("🪟 Arranging windows...")
            try:
                # Use wmctrl or xdotool to tile windows
                desktop.commands.run("wmctrl -r 'Visual Studio Code' -e 0,0,0,960,1080 || true")
                desktop.commands.run("wmctrl -r 'Google Chrome' -e 0,960,0,960,1080 || true")
                log("✅ Windows arranged side-by-side")
            except Exception as e:
                log(f"⚠️ Window arrangement skipped: {str(e)[:50]}")
            
            # === Start streaming ===
            log("📺 Starting desktop stream...")
            try:
                desktop.stream.start(require_auth=True)
                auth_key = desktop.stream.get_auth_key()
                stream_url = desktop.stream.get_url(auth_key=auth_key)
                log(f"✅ Stream ready: {stream_url[:50]}...")
            except Exception as e:
                return error_response(str(e), f"Failed to start desktop stream: {str(e)}")
            
            # === Store sandbox reference ===
            self.active_sandboxes[project_id] = desktop
            self.sandbox_info[project_id] = {
                "sandbox_id": sandbox_id,
                "stream_url": stream_url,
                "auth_key": auth_key,
                "config": config,
                "created_at": datetime.now().isoformat(),
                "logs": "\n".join(logs)
            }
            
            return {
                "status": "ready",
                "stream_url": stream_url,
                "sandbox_id": sandbox_id,
                "message": f"Desktop ready ({config['project_type']})",
                "logs": "\n".join(logs),
                "project_type": config["project_type"],
                "port": config["port"]
            }
            
        except Exception as e:
            error_msg = str(e)
            log(f"❌ Error: {error_msg}")
            logger.exception(f"E2B Desktop error for project {project_id}")
            
            return error_response(error_msg, f"Failed to create Desktop environment: {error_msg[:100]}")
    
    def has_active_sandbox(self, project_id: str) -> bool:
        """Check if a project has an active Desktop sandbox."""
        return project_id in self.active_sandboxes
    
    async def sync_from_sandbox(self, project_id: str) -> Dict[str, Any]:
        """
        Sync files FROM the sandbox back to backend storage.
        Call this before download or when user wants to save their work.
        """
        sandbox = self.active_sandboxes.get(project_id)
        if not sandbox:
            return {"status": "error", "message": "No active sandbox"}
        
        info = self.sandbox_info.get(project_id, {})
        work_dir = info.get("config", {}).get("work_dir", "/home/user/project")
        
        try:
            # List all files in the project directory
            result = sandbox.commands.run(f"find {work_dir} -type f -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/__pycache__/*'")
            
            if result.exit_code != 0:
                return {"status": "error", "message": "Failed to list files"}
            
            file_paths = [p.strip() for p in result.stdout.strip().split("\n") if p.strip()]
            
            synced_files = {}
            for full_path in file_paths:
                try:
                    rel_path = full_path.replace(f"{work_dir}/", "")
                    content = sandbox.files.read(full_path)
                    if isinstance(content, bytes):
                        content = content.decode("utf-8", errors="ignore")
                    synced_files[rel_path] = content
                except Exception as e:
                    logger.warning(f"Could not read {full_path}: {e}")
            
            # Write to backend storage
            if synced_files:
                write_project_files(project_id, synced_files)
            
            return {
                "status": "success",
                "message": f"Synced {len(synced_files)} files from sandbox",
                "files_synced": len(synced_files)
            }
            
        except Exception as e:
            logger.error(f"Sync from sandbox failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def sync_to_sandbox(self, project_id: str, files: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Sync files TO the sandbox from backend storage.
        Called after AI edits or file updates.
        """
        sandbox = self.active_sandboxes.get(project_id)
        if not sandbox:
            return {"status": "error", "message": "No active sandbox"}
        
        info = self.sandbox_info.get(project_id, {})
        work_dir = info.get("config", {}).get("work_dir", "/home/user/project")
        
        try:
            # If no files provided, read all from backend
            if files is None:
                files = read_project_files(project_id)
            
            synced = 0
            for file_path, content in files.items():
                if file_path == "blueprint.json":
                    continue
                
                full_path = f"{work_dir}/{file_path}"
                try:
                    parent_dir = str(Path(full_path).parent)
                    sandbox.commands.run(f"mkdir -p {parent_dir}")
                    sandbox.files.write(full_path, content)
                    synced += 1
                except Exception as e:
                    logger.warning(f"Could not write {file_path}: {e}")
            
            return {
                "status": "success",
                "message": f"Synced {synced} files to sandbox",
                "files_synced": synced
            }
            
        except Exception as e:
            logger.error(f"Sync to sandbox failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def sync_file_to_sandbox(self, project_id: str, filepath: str, content: str) -> bool:
        """Sync a single file update to the active sandbox."""
        sandbox = self.active_sandboxes.get(project_id)
        if not sandbox:
            return False
        
        try:
            info = self.sandbox_info.get(project_id, {})
            work_dir = info.get("config", {}).get("work_dir", "/home/user/project")
            full_path = f"{work_dir}/{filepath}"
            
            parent_dir = str(Path(full_path).parent)
            sandbox.commands.run(f"mkdir -p {parent_dir}")
            sandbox.files.write(full_path, content)
            logger.info(f"Synced {filepath} to sandbox {project_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to sync {filepath} to sandbox: {e}")
            return False
    
    def get_sandbox(self, project_id: str) -> Optional[Dict]:
        """Get info about an active sandbox."""
        return self.sandbox_info.get(project_id)
    
    async def get_sandbox_status(self, project_id: str) -> Dict[str, Any]:
        """Get current status of sandbox."""
        info = self.sandbox_info.get(project_id)
        sandbox = self.active_sandboxes.get(project_id)
        
        if not info or not sandbox:
            return {
                "status": "not_found",
                "message": "No active Desktop sandbox for this project"
            }
        
        try:
            result = sandbox.commands.run("echo 'alive'", timeout=5)
            if result.stdout and "alive" in result.stdout:
                return {
                    "status": "running",
                    "sandbox_id": info.get("sandbox_id"),
                    "stream_url": info.get("stream_url"),
                    "created_at": info.get("created_at"),
                    "project_type": info.get("config", {}).get("project_type")
                }
        except Exception:
            pass
        
        # Sandbox is dead, clean up
        await self.stop_sandbox(project_id)
        return {
            "status": "stopped",
            "message": "Desktop sandbox has expired or stopped"
        }
    
    async def stop_sandbox(self, project_id: str, sync_first: bool = True) -> Dict[str, str]:
        """Stop and cleanup a sandbox. Optionally sync files first."""
        sandbox = self.active_sandboxes.get(project_id)
        
        if not sandbox:
            return {"status": "not_found", "message": "No active Desktop sandbox"}
        
        # Sync files back to backend before killing
        if sync_first:
            try:
                await self.sync_from_sandbox(project_id)
                logger.info(f"Synced files from sandbox {project_id} before stopping")
            except Exception as e:
                logger.warning(f"Failed to sync before stop: {e}")
        
        try:
            sandbox.stream.stop()
        except Exception as e:
            logger.warning(f"Error stopping stream: {e}")
        
        try:
            sandbox.kill()
            logger.info(f"Killed Desktop sandbox for project {project_id}")
        except Exception as e:
            logger.warning(f"Error killing sandbox: {e}")
        
        self.active_sandboxes.pop(project_id, None)
        self.sandbox_info.pop(project_id, None)
        
        return {"status": "stopped", "message": "Desktop sandbox terminated"}
    
    async def cleanup_all(self):
        """Cleanup all active sandboxes (for shutdown)."""
        for project_id in list(self.active_sandboxes.keys()):
            await self.stop_sandbox(project_id, sync_first=False)


# Singleton instance
_e2b_desktop_service: Optional[E2BDesktopService] = None


def get_e2b_desktop_service() -> E2BDesktopService:
    """Get the singleton E2B Desktop service instance."""
    global _e2b_desktop_service
    if _e2b_desktop_service is None:
        _e2b_desktop_service = E2BDesktopService()
    return _e2b_desktop_service
