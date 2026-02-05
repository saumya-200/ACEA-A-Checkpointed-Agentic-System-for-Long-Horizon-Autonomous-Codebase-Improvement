# ACEA Sentinel - The Oracle Agent (ENHANCED)
# Test generation and execution with proper file management

import subprocess
import os
import sys
import json
from typing import Dict, Any, List
from pathlib import Path
from app.core.config import settings
from app.core.key_manager import KeyManager


class OracleAgent:
    def __init__(self):
        self.km = KeyManager()

    async def generate_tests(self, files: Dict[str, str], blueprint: dict) -> dict:
        """
        Generate test files for a project based on its codebase and blueprint.
        
        FIXED: Now matches the orchestrator's expected interface:
        - Takes files dict and blueprint as input
        - Returns dict with test_files and metadata
        - Works with the new orchestrator node
        
        Args:
            files: Dictionary of file paths to content
            blueprint: The project blueprint from Architect
            
        Returns:
            {
                "test_files": {"path/to/test.py": "test code"},
                "tests_generated": int,
                "framework": str,
                "error": str (if failed)
            }
        """
        from app.core.socket_manager import SocketManager
        sm = SocketManager()
        
        try:
            project_name = blueprint.get("project_name", "unknown")
            tech_stack = blueprint.get("tech_stack", {})
            
            # Determine test framework based on stack
            backend_stack = tech_stack.get("backend", "")
            frontend_stack = tech_stack.get("frontend", "")
            
            test_framework = "pytest"  # Default
            if "FastAPI" in backend_stack or "Python" in backend_stack:
                test_framework = "pytest"
            elif "Next.js" in frontend_stack or "React" in frontend_stack:
                test_framework = "vitest"
            
            await sm.emit("agent_log", {
                "agent_name": "ORACLE",
                "message": f"Generating tests using {test_framework}..."
            })
            
            # Generate tests for key files
            test_files = {}
            files_tested = 0
            
            # Filter files that should have tests (skip configs, assets, etc.)
            testable_files = self._filter_testable_files(files)
            
            if not testable_files:
                await sm.emit("agent_log", {
                    "agent_name": "ORACLE",
                    "message": "⚠️ No testable files found"
                })
                return {
                    "test_files": {},
                    "tests_generated": 0,
                    "framework": test_framework,
                    "error": "No testable files found"
                }
            
            # Generate tests in batch (limit to avoid token overuse)
            max_files_to_test = min(5, len(testable_files))
            
            for file_path in list(testable_files.keys())[:max_files_to_test]:
                file_content = testable_files[file_path]
                language = self._detect_language(file_path)
                
                test_code = await self._generate_test_for_file(
                    file_path, 
                    file_content, 
                    language,
                    test_framework
                )
                
                if test_code:
                    test_file_path = self._get_test_file_path(file_path, language)
                    test_files[test_file_path] = test_code
                    files_tested += 1
            
            await sm.emit("agent_log", {
                "agent_name": "ORACLE",
                "message": f"✅ Generated {files_tested} test files"
            })
            
            return {
                "test_files": test_files,
                "tests_generated": files_tested,
                "framework": test_framework,
                "files_tested": list(testable_files.keys())[:max_files_to_test]
            }
            
        except Exception as e:
            await sm.emit("agent_log", {
                "agent_name": "ORACLE",
                "message": f"❌ Test generation failed: {str(e)[:100]}"
            })
            return {
                "test_files": {},
                "tests_generated": 0,
                "framework": "unknown",
                "error": str(e)
            }

    def _filter_testable_files(self, files: Dict[str, str]) -> Dict[str, str]:
        """
        Filter files that should have tests generated.
        Skip configs, assets, tests, and other non-code files.
        """
        testable = {}
        
        # Extensions that should have tests
        testable_extensions = {'.py', '.js', '.jsx', '.ts', '.tsx'}
        
        # Paths to skip
        skip_patterns = [
            'test_', 'tests/', '__pycache__/', 'node_modules/',
            '.config.', 'config.', 'package.json', 'requirements.txt',
            '.css', '.html', '.md', '.json', '.env', '.gitignore',
            'main.py',  # Entry points usually don't need unit tests
            'index.', 'app.py'
        ]
        
        for path, content in files.items():
            # Check extension
            ext = Path(path).suffix
            if ext not in testable_extensions:
                continue
            
            # Check if path should be skipped
            should_skip = any(pattern in path.lower() for pattern in skip_patterns)
            if should_skip:
                continue
            
            # Must have actual code (not just imports/config)
            if len(content.strip()) < 50:  # Too short to be meaningful
                continue
            
            testable[path] = content
        
        return testable

    def _detect_language(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
        }
        
        return language_map.get(ext, 'python')

    def _get_test_file_path(self, original_path: str, language: str) -> str:
        """
        Generate appropriate test file path based on language conventions.
        
        Python: tests/test_<module>.py
        JavaScript/TypeScript: <module>.test.js/ts
        """
        path = Path(original_path)
        filename = path.stem
        
        if language == 'python':
            # Python convention: tests/test_filename.py
            return f"tests/test_{filename}.py"
        else:
            # JavaScript/TypeScript convention: filename.test.ext
            return str(path.parent / f"{filename}.test{path.suffix}")

    async def _generate_test_for_file(
        self, 
        file_path: str, 
        file_content: str, 
        language: str,
        test_framework: str
    ) -> str:
        """
        Generate test code for a single file using Gemini.
        """
        try:
            # Build context-aware prompt
            if language == 'python':
                prompt = f"""Generate comprehensive unit tests for this Python code using {test_framework}.

File: {file_path}

Code:
```python
{file_content}
```

Requirements:
- Use {test_framework} framework
- Import the module correctly (from app.* import ...)
- Test all public functions/classes
- Include edge cases and error handling
- Use descriptive test names
- Add docstrings to test functions

Return ONLY the test code, no explanations. Start with imports."""

            else:  # JavaScript/TypeScript
                prompt = f"""Generate comprehensive unit tests for this {language} code using {test_framework}.

File: {file_path}

Code:
```{language}
{file_content}
```

Requirements:
- Use {test_framework} framework
- Import the module correctly
- Test all exported functions/components
- Include edge cases
- Use describe/it blocks
- Mock external dependencies if needed

Return ONLY the test code, no explanations."""

            client = self.km.get_client()
            response = await client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            
            # Clean up response
            test_code = response.text
            
            # Remove markdown code blocks
            test_code = test_code.replace("```python", "").replace("```typescript", "")
            test_code = test_code.replace("```javascript", "").replace("```", "")
            test_code = test_code.strip()
            
            return test_code
            
        except Exception as e:
            print(f"Test generation failed for {file_path}: {e}")
            return ""

    async def run_tests(self, project_id: str) -> dict:
        """
        Execute tests in a generated project.
        
        Args:
            project_id: The project identifier
            
        Returns:
            {
                "passed": bool,
                "total_tests": int,
                "passed_tests": int,
                "failed_tests": int,
                "details": str,
                "duration": float
            }
        """
        from app.core.filesystem import BASE_PROJECTS_DIR
        from app.core.socket_manager import SocketManager
        sm = SocketManager()
        
        project_path = BASE_PROJECTS_DIR / project_id
        
        if not project_path.exists():
            return {
                "passed": False,
                "error": f"Project path not found: {project_path}"
            }
        
        await sm.emit("agent_log", {
            "agent_name": "ORACLE",
            "message": "Running test suite..."
        })
        
        # Check for Python tests
        test_dir = project_path / "tests"
        if test_dir.exists():
            result = await self._run_pytest(project_path)
        else:
            # Check for JavaScript tests
            js_tests = list(project_path.glob("**/*.test.js")) + list(project_path.glob("**/*.test.ts"))
            if js_tests:
                result = await self._run_vitest(project_path)
            else:
                await sm.emit("agent_log", {
                    "agent_name": "ORACLE",
                    "message": "⚠️ No tests found to run"
                })
                return {
                    "passed": True,
                    "total_tests": 0,
                    "details": "No test files found"
                }
        
        if result["passed"]:
            await sm.emit("agent_log", {
                "agent_name": "ORACLE",
                "message": f"✅ Tests passed: {result.get('passed_tests', 0)}/{result.get('total_tests', 0)}"
            })
        else:
            await sm.emit("agent_log", {
                "agent_name": "ORACLE",
                "message": f"❌ Tests failed: {result.get('failed_tests', 0)} failures"
            })
        
        return result

    async def _run_pytest(self, project_path: Path) -> dict:
        """Run pytest and parse results."""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
                capture_output=True,
                text=True,
                cwd=str(project_path),
                timeout=30
            )
            
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            
            # Parse test counts from pytest output
            total_tests = output.count("PASSED") + output.count("FAILED")
            passed_tests = output.count("PASSED")
            failed_tests = output.count("FAILED")
            
            return {
                "passed": passed,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": failed_tests,
                "details": output,
                "framework": "pytest"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": "Test execution timeout (30s)"
            }
        except Exception as e:
            return {
                "passed": False,
                "error": f"Test execution error: {str(e)}"
            }

    async def _run_vitest(self, project_path: Path) -> dict:
        """Run vitest and parse results."""
        try:
            result = subprocess.run(
                ["npm", "test"],
                capture_output=True,
                text=True,
                cwd=str(project_path),
                timeout=30
            )
            
            passed = result.returncode == 0
            output = result.stdout + result.stderr
            
            return {
                "passed": passed,
                "details": output,
                "framework": "vitest"
            }
            
        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "error": "Test execution timeout (30s)"
            }
        except Exception as e:
            return {
                "passed": False,
                "error": f"Test execution error: {str(e)}"
            }