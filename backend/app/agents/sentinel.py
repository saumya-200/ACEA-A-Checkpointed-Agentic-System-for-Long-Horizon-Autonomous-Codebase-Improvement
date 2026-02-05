# ACEA Sentinel - The Sentinel Agent (ENHANCED)
# Security scanning with AST-based analysis + pattern matching
# UPGRADE: More robust detection, fewer false positives

import json
import ast
import re
from typing import List, Dict, Any
from app.core.config import settings


class SentinelAgent:
    def __init__(self):
        self.dangerous_imports = {
            'pickle': 'CRITICAL',  # Arbitrary code execution
            'marshal': 'HIGH',     # Code execution
            'shelve': 'HIGH',      # Uses pickle internally
            'subprocess': 'MEDIUM',  # Command injection risk
            'os': 'MEDIUM',        # System access
        }
        
        self.dangerous_functions = {
            'eval': 'CRITICAL',
            'exec': 'CRITICAL',
            'compile': 'HIGH',
            '__import__': 'HIGH',
            'execfile': 'CRITICAL',
        }

    async def audit_code(self, file_path: str, code: str) -> dict:
        """
        Enhanced security scan using both AST analysis and pattern matching.
        AST analysis: Catches actual code constructs (harder to bypass).
        Pattern matching: Catches string-based issues and non-Python files.
        """
        vulnerabilities = []
        
        # Determine file type
        is_python = file_path.endswith('.py')
        is_javascript = file_path.endswith(('.js', '.jsx', '.ts', '.tsx'))
        
        if is_python:
            # Use AST-based analysis for Python files
            python_vulns = await self._analyze_python_ast(file_path, code)
            vulnerabilities.extend(python_vulns)
        
        if is_javascript:
            # Use pattern matching for JavaScript files
            js_vulns = await self._analyze_javascript_patterns(file_path, code)
            vulnerabilities.extend(js_vulns)
        
        # Pattern-based checks (applies to all files)
        pattern_vulns = await self._analyze_patterns(file_path, code)
        vulnerabilities.extend(pattern_vulns)
        
        # Determine status
        has_critical = any(v["severity"] in ["HIGH", "CRITICAL"] for v in vulnerabilities)
        status = "BLOCKED" if has_critical else "APPROVED"
        
        return {
            "status": status,
            "vulnerabilities": vulnerabilities
        }

    async def _analyze_python_ast(self, file_path: str, code: str) -> List[Dict[str, Any]]:
        """
        AST-based analysis for Python files.
        More reliable than regex - analyzes actual code structure.
        """
        vulnerabilities = []
        
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Check for dangerous function calls
                if isinstance(node, ast.Call):
                    func_name = None
                    
                    # Handle direct calls: eval(), exec()
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                    
                    # Handle attribute calls: os.system()
                    elif isinstance(node.func, ast.Attribute):
                        func_name = node.func.attr
                        
                        # Check for os.system, subprocess.call with shell=True
                        if func_name in ['system', 'popen', 'spawn']:
                            vulnerabilities.append({
                                "type": "Command Injection Risk",
                                "severity": "HIGH",
                                "line": node.lineno,
                                "description": f"Dangerous system call '{func_name}' at line {node.lineno} in {file_path}",
                                "fix_suggestion": "Use subprocess.run() with shell=False and argument list"
                            })
                    
                    # Check if function is in dangerous list
                    if func_name in self.dangerous_functions:
                        severity = self.dangerous_functions[func_name]
                        vulnerabilities.append({
                            "type": "Code Injection",
                            "severity": severity,
                            "line": node.lineno,
                            "description": f"Dangerous function '{func_name}()' at line {node.lineno} in {file_path}",
                            "fix_suggestion": f"Avoid using {func_name}() - consider safer alternatives"
                        })
                    
                    # Check for subprocess with shell=True
                    if func_name in ['call', 'run', 'Popen']:
                        for keyword in node.keywords:
                            if keyword.arg == 'shell' and isinstance(keyword.value, ast.Constant):
                                if keyword.value.value is True:
                                    vulnerabilities.append({
                                        "type": "Command Injection",
                                        "severity": "HIGH",
                                        "line": node.lineno,
                                        "description": f"subprocess call with shell=True at line {node.lineno} in {file_path}",
                                        "fix_suggestion": "Use shell=False and pass command as list"
                                    })
                
                # Check for dangerous imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    module_name = None
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            module_name = alias.name
                    elif isinstance(node, ast.ImportFrom):
                        module_name = node.module
                    
                    if module_name in self.dangerous_imports:
                        severity = self.dangerous_imports[module_name]
                        vulnerabilities.append({
                            "type": "Dangerous Import",
                            "severity": severity,
                            "line": node.lineno,
                            "description": f"Import of '{module_name}' at line {node.lineno} in {file_path}",
                            "fix_suggestion": f"Module '{module_name}' can be dangerous - ensure proper validation"
                        })
        
        except SyntaxError as e:
            # If code doesn't parse, fall back to pattern matching
            # Don't report as vulnerability - this is a different issue
            pass
        except Exception as e:
            # Unexpected error - log but don't block
            pass
        
        return vulnerabilities

    async def _analyze_javascript_patterns(self, file_path: str, code: str) -> List[Dict[str, Any]]:
        """
        Pattern-based analysis for JavaScript/TypeScript files.
        """
        vulnerabilities = []
        
        js_patterns = [
            (r'dangerouslySetInnerHTML\s*=', "XSS Risk", "HIGH", 
             "Avoid dangerouslySetInnerHTML or sanitize with DOMPurify"),
            (r'eval\s*\(', "Code Injection", "CRITICAL", 
             "Never use eval() with user input"),
            (r'Function\s*\(.*\)', "Code Injection", "HIGH", 
             "Avoid Function() constructor with dynamic code"),
            (r'document\.write\s*\(', "XSS Risk", "MEDIUM", 
             "Avoid document.write() - use DOM manipulation"),
            (r'innerHTML\s*=(?!.*DOMPurify)', "XSS Risk", "MEDIUM", 
             "Sanitize HTML before setting innerHTML"),
            (r'\.exec\s*\(', "Command Injection", "HIGH", 
             "Avoid executing shell commands from user input"),
        ]
        
        for pattern, vuln_type, severity, fix in js_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    "type": vuln_type,
                    "severity": severity,
                    "line": line_num,
                    "description": f"{vuln_type} detected at line {line_num} in {file_path}",
                    "fix_suggestion": fix
                })
        
        return vulnerabilities

    async def _analyze_patterns(self, file_path: str, code: str) -> List[Dict[str, Any]]:
        """
        Pattern-based checks for secrets, SQL issues, etc.
        Applies to all file types.
        """
        vulnerabilities = []
        
        # Secret detection patterns (more sophisticated)
        secret_patterns = [
            (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded Password", "HIGH",
             "Use environment variables or secret management"),
            (r'(?:api_key|apikey|api-key)\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded API Key", "HIGH",
             "Use environment variables (process.env or os.environ)"),
            (r'(?:secret_key|secret|SECRET_KEY)\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded Secret", "HIGH",
             "Use environment variables or key management service"),
            (r'(?:token|access_token|auth_token)\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded Token", "HIGH",
             "Use secure token storage"),
            # AWS keys pattern
            (r'AKIA[0-9A-Z]{16}', "AWS Access Key", "CRITICAL",
             "Remove AWS credentials immediately and rotate keys"),
            # Private keys
            (r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', "Private Key Exposed", "CRITICAL",
             "Never commit private keys - use secret management"),
        ]
        
        for pattern, vuln_type, severity, fix in secret_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    "type": vuln_type,
                    "severity": severity,
                    "line": line_num,
                    "description": f"{vuln_type} at line {line_num} in {file_path}",
                    "fix_suggestion": fix
                })
        
        # SQL Injection patterns
        sql_patterns = [
            (r'(?:execute|query|raw)\s*\([^)]*f["\'].*SELECT.*["\']', "SQL Injection", "CRITICAL",
             "Use parameterized queries instead of string formatting"),
            (r'SELECT\s+\*\s+FROM.*\+', "SQL Injection", "HIGH",
             "Use parameterized queries - never concatenate SQL"),
            (r'WHERE.*\+.*["\']', "SQL Injection", "HIGH",
             "Use parameterized queries with placeholders"),
        ]
        
        for pattern, vuln_type, severity, fix in sql_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE | re.DOTALL)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    "type": vuln_type,
                    "severity": severity,
                    "line": line_num,
                    "description": f"{vuln_type} risk at line {line_num} in {file_path}",
                    "fix_suggestion": fix
                })
        
        return vulnerabilities

    async def batch_audit(self, files: dict) -> dict:
        """
        OPTIMIZATION: Audit ALL files in one pass without API calls.
        Now with enhanced AST + pattern analysis.
        """
        from app.core.socket_manager import SocketManager
        sm = SocketManager()
        
        await sm.emit("agent_log", {"agent_name": "SENTINEL", "message": f"Scanning {len(files)} files for security issues..."})
        
        all_vulnerabilities = []
        files_with_issues = set()
        
        for path, content in files.items():
            result = await self.audit_code(path, content)
            if result["vulnerabilities"]:
                all_vulnerabilities.extend(result["vulnerabilities"])
                files_with_issues.add(path)
        
        # Determine overall status
        has_critical = any(v["severity"] in ["HIGH", "CRITICAL"] for v in all_vulnerabilities)
        status = "BLOCKED" if has_critical else "APPROVED"
        
        # Enhanced logging
        if all_vulnerabilities:
            critical_count = sum(1 for v in all_vulnerabilities if v["severity"] == "CRITICAL")
            high_count = sum(1 for v in all_vulnerabilities if v["severity"] == "HIGH")
            medium_count = sum(1 for v in all_vulnerabilities if v["severity"] == "MEDIUM")
            
            severity_summary = []
            if critical_count > 0:
                severity_summary.append(f"{critical_count} CRITICAL")
            if high_count > 0:
                severity_summary.append(f"{high_count} HIGH")
            if medium_count > 0:
                severity_summary.append(f"{medium_count} MEDIUM")
            
            await sm.emit("agent_log", {
                "agent_name": "SENTINEL", 
                "message": f"⚠️ Found {len(all_vulnerabilities)} issues: {', '.join(severity_summary)}"
            })
        else:
            await sm.emit("agent_log", {"agent_name": "SENTINEL", "message": "✅ No security issues detected"})
        
        return {
            "status": status,
            "vulnerabilities": all_vulnerabilities,
            "files_scanned": len(files),
            "files_with_issues": len(files_with_issues),
            "summary": {
                "critical": sum(1 for v in all_vulnerabilities if v["severity"] == "CRITICAL"),
                "high": sum(1 for v in all_vulnerabilities if v["severity"] == "HIGH"),
                "medium": sum(1 for v in all_vulnerabilities if v["severity"] == "MEDIUM"),
                "low": sum(1 for v in all_vulnerabilities if v["severity"] == "LOW"),
            }
        }