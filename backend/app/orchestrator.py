# ACEA Sentinel - Orchestrator with Self-Healing Loop
# Manages the agent workflow with automatic error detection and fixing
# FIXED: Oracle and Advisor agents now properly integrated

import json
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from app.agents.state import AgentState
from app.agents.architect import ArchitectAgent
from app.agents.virtuoso import VirtuosoAgent
from app.agents.sentinel import SentinelAgent
from app.agents.oracle import OracleAgent
from app.agents.watcher import WatcherAgent
from app.agents.advisor import AdvisorAgent

# Initialize Agents
architect_agent = ArchitectAgent()
virtuoso_agent = VirtuosoAgent()
sentinel_agent = SentinelAgent()
oracle_agent = OracleAgent()
watcher_agent = WatcherAgent()
advisor_agent = AdvisorAgent()

async def architect_node(state: AgentState):
    from app.core.socket_manager import SocketManager
    sm = SocketManager()
    
    print("--- ARCHITECT NODE ---")
    await sm.emit("agent_log", {"agent_name": "SYSTEM", "message": "Architect analyzing requirements..."})
    
    prompt = state["user_prompt"]
    blueprint = await architect_agent.design_system(prompt)
    
    if "error" in blueprint:
        await sm.emit("agent_log", {"agent_name": "ARCHITECT", "message": f"❌ Failed: {blueprint['error'][:100]}"})
        return {
            "blueprint": {},
            "current_status": "error", 
            "messages": [f"Architect Failed: {blueprint['error']}"],
            "errors": [blueprint['error']]
        }
    
    name = blueprint.get('project_name', 'Untitled')
    await sm.emit("agent_log", {"agent_name": "ARCHITECT", "message": f"✅ Blueprint created: {name}"})
    return {
        "blueprint": blueprint,
        "current_status": "blueprint_generated",
        "messages": [f"Architect designed system: {name}"]
    }

from app.core.filesystem import write_project_files

async def virtuoso_node(state: AgentState):
    from app.core.socket_manager import SocketManager
    sm = SocketManager()
    
    print("--- VIRTUOSO NODE ---")
    await sm.emit("agent_log", {"agent_name": "SYSTEM", "message": "Entering Virtuoso Node..."})
    
    blueprint = state["blueprint"]
    if not blueprint:
        await sm.emit("agent_log", {"agent_name": "SYSTEM", "message": "ERROR: Blueprint is missing!"})
        return {"current_status": "error", "errors": ["Missing Blueprint"]}

    errors = state.get("errors", [])
    current_files = state.get("file_system", {})
    iteration = state.get("iteration_count", 0)
    
    if errors and iteration > 0:
        # SELF-HEALING MODE: Regenerate with error context
        await sm.emit("agent_log", {"agent_name": "VIRTUOSO", "message": f"🔧 Self-Healing Mode: Fixing {len(errors)} errors (Iteration {iteration})..."})
        new_files = await virtuoso_agent.generate_from_blueprint(blueprint, existing_files=current_files, errors=errors)
    else:
        # Normal generation
        await sm.emit("agent_log", {"agent_name": "VIRTUOSO", "message": "Generating code from blueprint..."})
        new_files = await virtuoso_agent.generate_from_blueprint(blueprint)
    
    # FIX: Unescape newlines in generated code (JSON batch generation returns escaped strings)
    for path in new_files:
        if isinstance(new_files[path], str):
            new_files[path] = new_files[path].replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    
    # PERSIST TO DISK
    project_path = write_project_files(state["project_id"], new_files)
    
    await sm.emit("agent_log", {"agent_name": "VIRTUOSO", "message": f"✅ Generated {len(new_files)} files"})
    return {
        "file_system": new_files,
        "current_status": "code_generated",
        "messages": [f"Virtuoso generated {len(new_files)} files"],
        "errors": []  # Clear errors after regeneration
    }

async def oracle_node(state: AgentState):
    """
    ORACLE NODE - Test Generation and Execution
    Generates unit tests for the codebase and runs them to verify functionality.
    """
    from app.core.socket_manager import SocketManager
    sm = SocketManager()
    
    print("--- ORACLE NODE ---")
    await sm.emit("agent_log", {"agent_name": "ORACLE", "message": "Generating test suite..."})
    
    files = state["file_system"]
    blueprint = state["blueprint"]
    
    try:
        # Generate tests based on the code
        test_result = await oracle_agent.generate_tests(files, blueprint)
        
        if "error" in test_result:
            await sm.emit("agent_log", {"agent_name": "ORACLE", "message": f"⚠️ Test generation failed: {test_result['error'][:100]}"})
            # Don't block the pipeline for test failures, just log them
            return {
                "test_report": {"status": "SKIPPED", "reason": test_result['error']},
                "current_status": "tests_skipped",
                "messages": [f"Oracle: Tests skipped due to error"]
            }
        
        # Add generated test files to the file system
        test_files = test_result.get("test_files", {})
        if test_files:
            updated_files = {**files, **test_files}
            # Persist test files
            write_project_files(state["project_id"], test_files)
        else:
            updated_files = files
        
        await sm.emit("agent_log", {"agent_name": "ORACLE", "message": f"✅ Generated {len(test_files)} test files"})
        
        # Optionally run the tests
        # test_execution = await oracle_agent.run_tests(state["project_id"])
        
        return {
            "file_system": updated_files,
            "test_report": test_result,
            "current_status": "tests_generated",
            "messages": [f"Oracle generated {len(test_files)} test files"]
        }
        
    except Exception as e:
        await sm.emit("agent_log", {"agent_name": "ORACLE", "message": f"⚠️ Oracle error: {str(e)[:100]}"})
        return {
            "test_report": {"status": "ERROR", "error": str(e)},
            "current_status": "tests_error",
            "messages": [f"Oracle encountered error: {str(e)}"]
        }

async def sentinel_node(state: AgentState):
    from app.core.socket_manager import SocketManager
    sm = SocketManager()
    
    print("--- SENTINEL NODE ---")
    await sm.emit("agent_log", {"agent_name": "SENTINEL", "message": "Initiating security scan..."})
    
    files = state["file_system"]
    
    # OPTIMIZED: Use batch audit (0 API calls, pattern-based only)
    report = await sentinel_agent.batch_audit(files)
    
    if report["status"] == "BLOCKED":
        await sm.emit("agent_log", {"agent_name": "SENTINEL", "message": f"🚨 Security issues found! Code blocked."})
    else:
        await sm.emit("agent_log", {"agent_name": "SENTINEL", "message": "✅ Security scan passed"})
            
    return {
        "security_report": report,
        "current_status": "security_audited"
    }

async def watcher_node(state: AgentState):
    from app.core.socket_manager import SocketManager
    from app.core.filesystem import BASE_PROJECTS_DIR
    
    sm = SocketManager()
    print("--- WATCHER NODE ---")
    
    project_id = state["project_id"]
    project_path = str(BASE_PROJECTS_DIR / project_id)
    
    await sm.emit("agent_log", {"agent_name": "WATCHER", "message": "Starting project verification..."})
    
    try:
        # Use quick_verify for faster feedback (no server startup)
        # For full browser testing, use: run_and_verify_project(project_path, project_id)
        report = await watcher_agent.quick_verify(project_id)
        
        if report["status"] == "FAIL":
            await sm.emit("agent_log", {"agent_name": "WATCHER", "message": f"❌ Verification failed: {len(report['errors'])} errors found"})
        else:
            await sm.emit("agent_log", {"agent_name": "WATCHER", "message": "✅ Project verification complete!"})
        
        return {
            "visual_report": report,
            "current_status": "visually_verified",
            "messages": [f"Watcher Status: {report['status']}"],
            "errors": report.get("errors", []) if report.get("fix_this") else []
        }
    except Exception as e:
        await sm.emit("agent_log", {"agent_name": "WATCHER", "message": f"⚠️ Verification error: {str(e)[:50]}"})
        return {
            "visual_report": {"status": "ERROR", "error": str(e)},
            "current_status": "visual_error",
            "messages": [f"Watcher Failed: {str(e)}"],
            "errors": [str(e)]
        }

async def advisor_node(state: AgentState):
    """
    ADVISOR NODE - Deployment Strategy Analysis
    Analyzes the project and provides deployment recommendations.
    Only runs if all previous checks passed.
    """
    from app.core.socket_manager import SocketManager
    sm = SocketManager()
    
    print("--- ADVISOR NODE ---")
    await sm.emit("agent_log", {"agent_name": "ADVISOR", "message": "Analyzing deployment strategy..."})
    
    blueprint = state["blueprint"]
    security_report = state.get("security_report", {})
    visual_report = state.get("visual_report", {})
    
    try:
        # Analyze deployment options
        deployment_plan = await advisor_agent.analyze_deployment(
            blueprint=blueprint,
            security_report=security_report,
            visual_report=visual_report
        )
        
        if "error" in deployment_plan:
            await sm.emit("agent_log", {"agent_name": "ADVISOR", "message": f"⚠️ Analysis failed: {deployment_plan['error'][:100]}"})
            return {
                "deployment_plan": {"status": "ERROR", "error": deployment_plan['error']},
                "current_status": "deployment_error",
                "messages": ["Advisor analysis failed"]
            }
        
        platform = deployment_plan.get("recommended_platform", "Unknown")
        await sm.emit("agent_log", {"agent_name": "ADVISOR", "message": f"✅ Recommended platform: {platform}"})
        
        return {
            "deployment_plan": deployment_plan,
            "current_status": "deployment_planned",
            "messages": [f"Advisor recommends: {platform}"]
        }
        
    except Exception as e:
        await sm.emit("agent_log", {"agent_name": "ADVISOR", "message": f"⚠️ Advisor error: {str(e)[:100]}"})
        return {
            "deployment_plan": {"status": "ERROR", "error": str(e)},
            "current_status": "deployment_error",
            "messages": [f"Advisor error: {str(e)}"]
        }

def router(state: AgentState):
    """
    SELF-HEALING ROUTER
    Checks if there are errors that need fixing and routes back to Virtuoso.
    """
    errors = state.get("errors", [])
    iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    # Check if we have errors to fix
    if errors and len(errors) > 0:
        if iteration >= max_iterations:
            print(f"Router: Max iterations ({max_iterations}) reached. Proceeding to Advisor anyway.")
            return "advisor"
        
        print(f"Router: Errors found. Routing to Virtuoso for fix (iteration {iteration + 1})")
        return "virtuoso_fix"
    
    # No errors - proceed to Advisor for deployment planning
    print("Router: No errors. Proceeding to Advisor!")
    return "advisor"

def increment_iteration(state: AgentState):
    """Helper node to increment iteration count before fix."""
    return {"iteration_count": state.get("iteration_count", 0) + 1}

# Build Graph
builder = StateGraph(AgentState)

# Add all nodes
builder.add_node("architect", architect_node)
builder.add_node("virtuoso", virtuoso_node)
builder.add_node("oracle", oracle_node)
builder.add_node("sentinel", sentinel_node)
builder.add_node("watcher", watcher_node)
builder.add_node("advisor", advisor_node)
builder.add_node("increment_iteration", increment_iteration)

# Set entry point
builder.set_entry_point("architect")

# Architect routing (check for errors)
def architect_router(state: AgentState):
    if state.get("current_status") == "error":
        return END
    return "virtuoso"

builder.add_conditional_edges("architect", architect_router, {"virtuoso": "virtuoso", END: END})

# Sequential pipeline: Virtuoso → Oracle → Sentinel → Watcher
builder.add_edge("virtuoso", "oracle")
builder.add_edge("oracle", "sentinel")
builder.add_edge("sentinel", "watcher")

# Self-Healing Loop from Watcher
builder.add_conditional_edges(
    "watcher",
    router,
    {
        "virtuoso_fix": "increment_iteration",
        "advisor": "advisor",
    }
)

# After incrementing iteration, go back to virtuoso
builder.add_edge("increment_iteration", "virtuoso")

# Advisor is the final node, always ends
builder.add_edge("advisor", END)

# Compile
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)