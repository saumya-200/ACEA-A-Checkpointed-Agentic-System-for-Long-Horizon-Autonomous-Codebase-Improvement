# ACEA Sentinel - The Advisor Agent (ENHANCED)
# Deployment strategy analysis with platform recommendations

import json
import re
from typing import Dict, Any, List
from app.core.config import settings
from app.core.key_manager import KeyManager


class AdvisorAgent:
    def __init__(self):
        self.km = KeyManager()
        
        # Platform capabilities and constraints
        self.platforms = {
            "vercel": {
                "strengths": ["Next.js", "React", "Static sites", "Edge functions"],
                "limitations": ["No persistent storage", "Short serverless timeout"],
                "ideal_for": ["frontend", "jamstack", "nextjs"]
            },
            "railway": {
                "strengths": ["Full stack", "Databases", "Persistent storage", "Docker"],
                "limitations": ["Higher cost", "Learning curve"],
                "ideal_for": ["backend", "fullstack", "database"]
            },
            "render": {
                "strengths": ["Full stack", "Free tier", "Postgres", "Docker"],
                "limitations": ["Slower cold starts", "Limited free tier"],
                "ideal_for": ["backend", "fullstack", "postgres"]
            },
            "fly.io": {
                "strengths": ["Global edge deployment", "Persistent storage", "Docker"],
                "limitations": ["Complex configuration", "CLI-heavy"],
                "ideal_for": ["backend", "distributed", "docker"]
            },
            "heroku": {
                "strengths": ["Simple deployment", "Add-ons ecosystem", "Buildpacks"],
                "limitations": ["Expensive", "Deprecated free tier"],
                "ideal_for": ["backend", "simple", "legacy"]
            },
            "aws": {
                "strengths": ["Full control", "Scalable", "Enterprise features"],
                "limitations": ["Complex", "Expensive", "Steep learning curve"],
                "ideal_for": ["enterprise", "scalable", "complex"]
            },
            "digitalocean": {
                "strengths": ["Simple VPS", "App Platform", "Databases"],
                "limitations": ["Less automated", "Manual scaling"],
                "ideal_for": ["vps", "simple", "cost-effective"]
            }
        }

    async def analyze_deployment(
        self, 
        blueprint: dict, 
        security_report: dict = None, 
        visual_report: dict = None
    ) -> dict:
        """
        Analyze project and recommend deployment strategy.
        
        FIXED: Now matches orchestrator's expected interface:
        - Takes blueprint, security_report, visual_report
        - Returns structured dict with platform, config, costs
        
        Args:
            blueprint: Project blueprint from Architect
            security_report: Security audit results from Sentinel
            visual_report: Verification results from Watcher
            
        Returns:
            {
                "recommended_platform": str,
                "alternative_platforms": [str],
                "reasoning": str,
                "cost_estimate": str,
                "configuration": dict,
                "deployment_steps": [str],
                "config_files": dict,
                "warnings": [str]
            }
        """
        from app.core.socket_manager import SocketManager
        sm = SocketManager()
        
        try:
            project_name = blueprint.get("project_name", "Unknown Project")
            tech_stack = blueprint.get("tech_stack", {})
            architecture = blueprint.get("architecture", {})
            
            await sm.emit("agent_log", {
                "agent_name": "ADVISOR",
                "message": f"Analyzing deployment options for {project_name}..."
            })
            
            # Analyze project characteristics
            analysis = self._analyze_project_characteristics(
                tech_stack, 
                architecture,
                security_report,
                visual_report
            )
            
            # Get AI-powered recommendation
            ai_recommendation = await self._get_ai_recommendation(
                blueprint, 
                analysis,
                security_report
            )
            
            # Merge rule-based and AI recommendations
            final_recommendation = self._merge_recommendations(analysis, ai_recommendation)
            
            # Generate configuration files
            config_files = await self._generate_config_files(
                final_recommendation["recommended_platform"],
                tech_stack,
                project_name
            )
            
            final_recommendation["config_files"] = config_files
            
            await sm.emit("agent_log", {
                "agent_name": "ADVISOR",
                "message": f"✅ Recommended: {final_recommendation['recommended_platform']}"
            })
            
            return final_recommendation
            
        except Exception as e:
            await sm.emit("agent_log", {
                "agent_name": "ADVISOR",
                "message": f"❌ Analysis failed: {str(e)[:100]}"
            })
            return {
                "recommended_platform": "manual",
                "error": str(e),
                "reasoning": "Automated analysis failed - manual deployment required"
            }

    def _analyze_project_characteristics(
        self, 
        tech_stack: dict, 
        architecture: dict,
        security_report: dict = None,
        visual_report: dict = None
    ) -> dict:
        """
        Rule-based analysis of project characteristics.
        """
        characteristics = {
            "has_backend": False,
            "has_frontend": False,
            "has_database": False,
            "framework": None,
            "language": None,
            "complexity": "simple",
            "security_concerns": [],
            "verified": False
        }
        
        # Analyze tech stack
        backend = tech_stack.get("backend", "").lower()
        frontend = tech_stack.get("frontend", "").lower()
        database = tech_stack.get("database", "").lower()
        
        characteristics["has_backend"] = bool(backend)
        characteristics["has_frontend"] = bool(frontend)
        characteristics["has_database"] = bool(database)
        
        # Identify frameworks
        if "next.js" in frontend or "nextjs" in frontend:
            characteristics["framework"] = "nextjs"
            characteristics["language"] = "javascript"
        elif "react" in frontend:
            characteristics["framework"] = "react"
            characteristics["language"] = "javascript"
        elif "vue" in frontend:
            characteristics["framework"] = "vue"
            characteristics["language"] = "javascript"
        
        if "fastapi" in backend:
            characteristics["backend_framework"] = "fastapi"
            characteristics["language"] = "python"
        elif "flask" in backend:
            characteristics["backend_framework"] = "flask"
            characteristics["language"] = "python"
        elif "express" in backend:
            characteristics["backend_framework"] = "express"
            characteristics["language"] = "javascript"
        
        # Determine complexity
        if characteristics["has_database"]:
            characteristics["complexity"] = "medium"
        if characteristics["has_backend"] and characteristics["has_frontend"]:
            characteristics["complexity"] = "medium"
        if len(architecture.get("components", [])) > 5:
            characteristics["complexity"] = "complex"
        
        # Security analysis
        if security_report:
            vulns = security_report.get("vulnerabilities", [])
            high_severity = [v for v in vulns if v.get("severity") in ["HIGH", "CRITICAL"]]
            if high_severity:
                characteristics["security_concerns"] = [v["type"] for v in high_severity]
        
        # Verification status
        if visual_report:
            characteristics["verified"] = visual_report.get("status") == "PASS"
        
        return characteristics

    async def _get_ai_recommendation(
        self, 
        blueprint: dict, 
        analysis: dict,
        security_report: dict = None
    ) -> dict:
        """
        Get AI-powered deployment recommendation using Gemini.
        """
        try:
            # Build context-aware prompt
            tech_summary = f"""
Project: {blueprint.get('project_name', 'Unknown')}
Tech Stack:
- Frontend: {blueprint.get('tech_stack', {}).get('frontend', 'None')}
- Backend: {blueprint.get('tech_stack', {}).get('backend', 'None')}
- Database: {blueprint.get('tech_stack', {}).get('database', 'None')}

Characteristics:
- Complexity: {analysis['complexity']}
- Has Database: {analysis['has_database']}
- Framework: {analysis.get('framework', 'Unknown')}
- Security Concerns: {', '.join(analysis.get('security_concerns', [])) or 'None'}
"""
            
            prompt = f"""You are a deployment strategy expert. Analyze this project and recommend the best deployment platform.

{tech_summary}

Available platforms: Vercel, Railway, Render, Fly.io, Heroku, DigitalOcean, AWS

Consider:
1. Tech stack compatibility
2. Scalability needs
3. Cost efficiency
4. Ease of deployment
5. Database requirements

Respond ONLY with valid JSON in this exact format:
{{
  "recommended_platform": "platform_name",
  "alternative_platforms": ["platform1", "platform2"],
  "reasoning": "2-3 sentence explanation",
  "cost_estimate": "Free tier / $X-Y per month / Enterprise",
  "deployment_steps": ["step1", "step2", "step3"],
  "warnings": ["warning1 if any"]
}}"""

            client = self.km.get_client()
            response = await client.aio.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            
            # Extract JSON from response
            response_text = response.text.strip()
            
            # Remove markdown code blocks if present
            response_text = re.sub(r'```json\s*', '', response_text)
            response_text = re.sub(r'```\s*', '', response_text)
            
            # Parse JSON
            recommendation = json.loads(response_text)
            
            return recommendation
            
        except json.JSONDecodeError as e:
            # Fallback if JSON parsing fails
            return {
                "recommended_platform": "vercel" if analysis["has_frontend"] else "railway",
                "reasoning": "AI parsing failed - using rule-based fallback",
                "error": f"JSON parse error: {str(e)}"
            }
        except Exception as e:
            return {
                "recommended_platform": "manual",
                "reasoning": "AI analysis failed",
                "error": str(e)
            }

    def _merge_recommendations(self, rule_based: dict, ai_based: dict) -> dict:
        """
        Merge rule-based analysis with AI recommendation.
        Apply safety checks and validation.
        """
        # Start with AI recommendation
        final = {
            "recommended_platform": ai_based.get("recommended_platform", "vercel"),
            "alternative_platforms": ai_based.get("alternative_platforms", []),
            "reasoning": ai_based.get("reasoning", "No reasoning provided"),
            "cost_estimate": ai_based.get("cost_estimate", "Unknown"),
            "deployment_steps": ai_based.get("deployment_steps", []),
            "warnings": ai_based.get("warnings", [])
        }
        
        # Add security warnings
        if rule_based.get("security_concerns"):
            final["warnings"].append(
                f"Security issues detected: {', '.join(rule_based['security_concerns'])}. "
                "Fix before deploying to production."
            )
        
        # Add verification warning
        if not rule_based.get("verified"):
            final["warnings"].append(
                "Project verification incomplete. Test thoroughly before deployment."
            )
        
        # Validate platform recommendation
        platform = final["recommended_platform"].lower()
        if platform not in self.platforms:
            # Fallback to safe default
            if rule_based["has_frontend"] and not rule_based["has_backend"]:
                final["recommended_platform"] = "vercel"
            else:
                final["recommended_platform"] = "railway"
            final["warnings"].append("Platform recommendation adjusted based on project type")
        
        # Add project characteristics
        final["project_type"] = (
            "fullstack" if rule_based["has_backend"] and rule_based["has_frontend"]
            else "frontend" if rule_based["has_frontend"]
            else "backend"
        )
        
        return final

    async def _generate_config_files(
        self, 
        platform: str, 
        tech_stack: dict,
        project_name: str
    ) -> dict:
        """
        Generate platform-specific configuration files.
        """
        configs = {}
        platform_lower = platform.lower()
        
        # Vercel configuration
        if platform_lower == "vercel":
            configs["vercel.json"] = json.dumps({
                "version": 2,
                "builds": [
                    {
                        "src": "package.json",
                        "use": "@vercel/next"
                    }
                ],
                "routes": [
                    {
                        "src": "/(.*)",
                        "dest": "/$1"
                    }
                ]
            }, indent=2)
        
        # Railway configuration
        elif platform_lower == "railway":
            configs["railway.json"] = json.dumps({
                "build": {
                    "builder": "NIXPACKS"
                },
                "deploy": {
                    "startCommand": "npm start",
                    "restartPolicyType": "ON_FAILURE"
                }
            }, indent=2)
        
        # Render configuration
        elif platform_lower == "render":
            configs["render.yaml"] = f"""services:
  - type: web
    name: {project_name}
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: PYTHON_VERSION
        value: 3.12
"""
        
        # Fly.io configuration
        elif platform_lower == "fly.io" or platform_lower == "fly":
            configs["fly.toml"] = f"""app = "{project_name}"

[build]
  builder = "paketobuildpacks/builder:base"

[env]
  PORT = "8080"

[[services]]
  internal_port = 8080
  protocol = "tcp"

  [[services.ports]]
    port = 80
    handlers = ["http"]

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]
"""
        
        # Dockerfile (universal)
        if tech_stack.get("backend"):
            backend = tech_stack["backend"].lower()
            if "python" in backend or "fastapi" in backend:
                configs["Dockerfile"] = """FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
        
        return configs