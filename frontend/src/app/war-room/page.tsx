"use client"

import { useState, useEffect } from "react"
import { AgentHexagon } from "@/components/war-room/AgentHexagon"
import { LiveFeed } from "@/components/war-room/LiveFeed"
import { Brain, Code, Shield, Eye, Database, Rocket, Laptop, X } from "lucide-react"
import { socket } from "@/lib/socket"
import { FileExplorer } from "@/components/ide/FileExplorer"
import { CodeEditor } from "@/components/ide/CodeEditor"

// Agent name to icon mapping
const AGENT_ICONS = {
    ARCHITECT: Brain,
    VIRTUOSO: Code,
    ORACLE: Database,
    SENTINEL: Shield,
    WATCHER: Eye,
    ADVISOR: Rocket
}

export default function WarRoomPage() {
    const [logs, setLogs] = useState<any[]>([])
    const [agents, setAgents] = useState<any>({
        ARCHITECT: "idle",
        VIRTUOSO: "idle",
        ORACLE: "idle",
        SENTINEL: "idle",
        WATCHER: "idle",
        ADVISOR: "idle"
    })
    const [prompt, setPrompt] = useState("")
    const [isProcessing, setIsProcessing] = useState(false)

    // IDE State
    const [projectId, setProjectId] = useState<string | null>(null)
    const [showIDE, setShowIDE] = useState(false)
    const [files, setFiles] = useState<Record<string, string>>({})
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const [fileList, setFileList] = useState<string[]>([])

    useEffect(() => {
        // Listen for connection
        socket.on("connect", () => {
            addLog("SYSTEM", "Connected to ACEA Core Uplink", "success")
        })

        socket.on("disconnect", () => {
            addLog("SYSTEM", "Connection lost - attempting reconnection", "error")
        })

        // Enhanced agent log listener with status inference
        socket.on("agent_log", (data: any) => {
            const agentName = data.agent_name
            const message = data.message
            
            addLog(agentName, message, "info")
            
            // Infer agent status from log messages
            // This provides real-time feedback even without explicit status events
            if (agentName !== "SYSTEM") {
                // Set agent to "active" when they start working
                if (
                    message.includes("analyzing") ||
                    message.includes("generating") ||
                    message.includes("scanning") ||
                    message.includes("verifying") ||
                    message.includes("Starting") ||
                    message.includes("Initiating")
                ) {
                    setAgents((prev: any) => ({ ...prev, [agentName]: "active" }))
                }
                
                // Set to "success" when they complete
                else if (
                    message.includes("✅") ||
                    message.includes("complete") ||
                    message.includes("passed") ||
                    message.includes("success")
                ) {
                    setAgents((prev: any) => ({ ...prev, [agentName]: "success" }))
                }
                
                // Set to "error" on failure
                else if (
                    message.includes("❌") ||
                    message.includes("Failed") ||
                    message.includes("ERROR")
                ) {
                    setAgents((prev: any) => ({ ...prev, [agentName]: "error" }))
                }
                
                // Set to "warning" for issues
                else if (
                    message.includes("⚠️") ||
                    message.includes("warning") ||
                    message.includes("issue")
                ) {
                    setAgents((prev: any) => ({ ...prev, [agentName]: "warning" }))
                }
            }
        })

        // Explicit agent status updates (if backend sends them)
        socket.on("agent_status", (data: any) => {
            setAgents((prev: any) => ({ ...prev, [data.agent_name]: data.status }))
        })

        // Listen for Mission Acceptance (Gets Project ID early)
        socket.on("mission_accepted", (data: { project_id: string }) => {
            setProjectId(data.project_id)
            addLog("SYSTEM", `Mission ID Assigned: ${data.project_id}`, "info")
        })

        // Listen for completion
        socket.on("mission_complete", (data: any) => {
            setIsProcessing(false)
            addLog("SYSTEM", "🎉 Mission Objective Complete - All systems nominal", "success")

            // Mark all agents as complete
            setAgents({
                ARCHITECT: "success",
                VIRTUOSO: "success",
                ORACLE: "success",
                SENTINEL: "success",
                WATCHER: "success",
                ADVISOR: "success"
            })

            if (data.project_id) {
                setProjectId(data.project_id)
                fetchProjectFiles(data.project_id)
                setShowIDE(true) // Auto-open IDE
            }
        })

        // Listen for errors
        socket.on("mission_error", (data) => {
            setIsProcessing(false)
            addLog("SYSTEM", `Critical Failure: ${data.detail}`, "error")
            
            // Reset agents to idle on error
            setAgents({
                ARCHITECT: "error",
                VIRTUOSO: "idle",
                ORACLE: "idle",
                SENTINEL: "idle",
                WATCHER: "idle",
                ADVISOR: "idle"
            })
        })

        // Listen for Real-Time Generation Events
        socket.on("generation_started", (data: { total_files: number, file_list: string[] }) => {
            addLog("VIRTUOSO", `Planned ${data.total_files} files. Starting stream...`, "info")
            setFileList(data.file_list)
            setShowIDE(true) // Auto-open IDE immediately
        })

        socket.on("file_generated", (data: { path: string, content: string, status: string }) => {
            // Update files state incrementally
            setFiles(prev => ({
                ...prev,
                [data.path]: data.content
            }))
            addLog("VIRTUOSO", `✅ Generated: ${data.path}`, "success")
        })

        socket.on("file_status", (data: { path: string, status: string }) => {
            if (data.status === 'generating') {
                addLog("VIRTUOSO", `🔧 Developing: ${data.path}...`, "info")
            }
        })

        // Cleanup on unmount
        return () => {
            socket.off("connect")
            socket.off("disconnect")
            socket.off("agent_log")
            socket.off("agent_status")
            socket.off("mission_accepted")
            socket.off("mission_complete")
            socket.off("mission_error")
            socket.off("generation_started")
            socket.off("file_generated")
            socket.off("file_status")
        }
    }, [])

    const fetchProjectFiles = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/projects/${id}/files`)
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`)
            }
            const data = await res.json()
            // data is dict {path: content} from backend
            setFiles(data)
            const paths = Object.keys(data).sort()
            setFileList(paths)
            if (paths.length > 0) setSelectedFile(paths[0])
            
            addLog("SYSTEM", `Loaded ${paths.length} files`, "success")
        } catch (e) {
            console.error("Failed to fetch files", e)
            addLog("SYSTEM", "Failed to load project files", "error")
        }
    }

    const addLog = (agent: string, message: string, type: "info" | "success" | "warning" | "error") => {
        setLogs(prev => [...prev.slice(-49), {
            id: Date.now().toString() + Math.random(),
            agent,
            message,
            timestamp: new Date().toLocaleTimeString(),
            type
        }])
    }

    const startMission = () => {
        if (!prompt.trim()) return
        
        setIsProcessing(true)
        setLogs([]) // Clear previous logs
        setShowIDE(false) // Reset view
        setFiles({}) // Clear previous files
        setFileList([])
        setSelectedFile(null)
        
        // Reset all agents to idle
        setAgents({
            ARCHITECT: "idle",
            VIRTUOSO: "idle",
            ORACLE: "idle",
            SENTINEL: "idle",
            WATCHER: "idle",
            ADVISOR: "idle"
        })
        
        addLog("SYSTEM", "⚡ Initializing Autonomous Sequence...", "warning")
        addLog("SYSTEM", `Mission Objective: "${prompt.substring(0, 100)}${prompt.length > 100 ? '...' : ''}"`, "info")

        // Emit start event to backend
        socket.emit("start_mission", { prompt })
    }

    const resetMission = () => {
        setIsProcessing(false)
        setPrompt("")
        setProjectId(null)
        setShowIDE(false)
        setFiles({})
        setFileList([])
        setSelectedFile(null)
        setAgents({
            ARCHITECT: "idle",
            VIRTUOSO: "idle",
            ORACLE: "idle",
            SENTINEL: "idle",
            WATCHER: "idle",
            ADVISOR: "idle"
        })
        addLog("SYSTEM", "Mission reset - ready for new objective", "info")
    }

    return (
        <main className="min-h-screen bg-slate-950 text-white p-6 overflow-hidden relative font-sans">
            {/* Background Grid */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#4f4f4f2e_1px,transparent_1px),linear-gradient(to_bottom,#4f4f4f2e_1px,transparent_1px)] bg-[size:14px_24px] pointer-events-none" />

            <div className="relative z-10 grid grid-cols-12 gap-6 h-[calc(100vh-3rem)]">

                {/* Left Panel: Metrics & Input */}
                <div className="col-span-3 border border-slate-800 bg-slate-950/80 p-4 rounded-xl backdrop-blur-md flex flex-col">
                    <h2 className="text-xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent mb-6">MISSION CONTROL</h2>

                    <div className="space-y-4 mb-4">
                        {/* Status Indicators */}
                        <div className="p-3 bg-slate-900/50 border border-slate-800 rounded flex justify-between items-center">
                            <div className="text-slate-500 text-xs uppercase">Security Level</div>
                            <div className="text-green-400 font-mono font-bold">DEFCON 5</div>
                        </div>
                        
                        <div className="p-3 bg-slate-900/50 border border-slate-800 rounded flex justify-between items-center">
                            <div className="text-slate-500 text-xs uppercase">Active Agents</div>
                            <div className="text-blue-400 font-mono font-bold">
                                {Object.values(agents).filter(s => s === 'active' || s === 'success').length}/6
                            </div>
                        </div>

                        {projectId && (
                            <>
                                <button
                                    onClick={() => setShowIDE(!showIDE)}
                                    className={`w-full py-2 rounded font-bold text-sm flex items-center justify-center gap-2 transition-colors ${
                                        showIDE 
                                            ? 'bg-slate-800 text-white hover:bg-slate-700' 
                                            : 'bg-purple-600 hover:bg-purple-500 text-white'
                                    }`}
                                >
                                    {showIDE ? <X className="w-4 h-4" /> : <Laptop className="w-4 h-4" />}
                                    {showIDE ? "CLOSE IDE" : "OPEN CODEBASE"}
                                </button>
                                
                                <button
                                    onClick={resetMission}
                                    className="w-full py-2 rounded font-bold text-sm flex items-center justify-center gap-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 border border-red-600/50 transition-colors"
                                >
                                    RESET MISSION
                                </button>
                            </>
                        )}
                    </div>

                    <div className="mt-auto">
                        <label className="text-xs text-slate-400 uppercase font-bold mb-2 block">Mission Objective</label>
                        <textarea
                            className="w-full bg-slate-900 border border-slate-700 rounded p-3 text-sm text-white focus:outline-none focus:border-blue-500 h-32 mb-4 resize-none"
                            placeholder="Describe the software you want to build... (e.g., 'Build a todo app with Next.js and FastAPI backend')"
                            value={prompt}
                            onChange={(e) => setPrompt(e.target.value)}
                            disabled={isProcessing}
                        />
                        
                        {/* Status bar */}
                        {isProcessing && (
                            <div className="text-xs text-blue-400 animate-pulse mb-2 text-center font-mono">
                                ⚡ Processing Mission Data...
                            </div>
                        )}
                        
                        <button
                            onClick={startMission}
                            disabled={isProcessing || !prompt.trim()}
                            className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed text-white font-bold py-3 rounded shadow-lg transition-all flex items-center justify-center gap-2"
                        >
                            {isProcessing ? (
                                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            ) : (
                                <Rocket className="w-4 h-4" />
                            )}
                            {isProcessing ? "EXECUTING..." : "INITIATE LAUNCH"}
                        </button>
                    </div>
                </div>

                {/* Center Panel: Visualization OR IDE */}
                <div className="col-span-6 flex items-center justify-center relative border border-slate-800/50 rounded-xl bg-slate-950/50 backdrop-blur-sm overflow-hidden">
                    {showIDE && projectId ? (
                        <div className="absolute inset-0 flex flex-row">
                            <FileExplorer
                                files={fileList}
                                onSelect={setSelectedFile}
                                selectedPath={selectedFile || undefined}
                            />
                            <div className="flex-1 bg-[#1e1e1e]">
                                {selectedFile ? (
                                    <CodeEditor
                                        code={files[selectedFile] || ""}
                                        language={
                                            selectedFile.endsWith('.json') ? 'json' :
                                            selectedFile.endsWith('.tsx') || selectedFile.endsWith('.ts') ? 'typescript' :
                                            selectedFile.endsWith('.jsx') || selectedFile.endsWith('.js') ? 'javascript' :
                                            selectedFile.endsWith('.py') ? 'python' :
                                            selectedFile.endsWith('.html') ? 'html' :
                                            selectedFile.endsWith('.css') ? 'css' :
                                            'plaintext'
                                        }
                                    />
                                ) : (
                                    <div className="h-full flex items-center justify-center text-slate-500">
                                        Select a file to view source
                                    </div>
                                )}
                            </div>
                        </div>
                    ) : (
                        <>
                            {/* Agent Hexagon Grid - FIXED: Now shows all 6 agents in proper order */}
                            <div className="grid grid-cols-3 gap-8 place-items-center relative z-10">
                                {/* Top Row */}
                                <AgentHexagon name="ARCHITECT" status={agents.ARCHITECT} icon={AGENT_ICONS.ARCHITECT} />
                                <AgentHexagon name="VIRTUOSO" status={agents.VIRTUOSO} icon={AGENT_ICONS.VIRTUOSO} className="mt-12" />
                                <AgentHexagon name="ORACLE" status={agents.ORACLE} icon={AGENT_ICONS.ORACLE} />

                                {/* Bottom Row */}
                                <AgentHexagon name="SENTINEL" status={agents.SENTINEL} icon={AGENT_ICONS.SENTINEL} />
                                <AgentHexagon name="WATCHER" status={agents.WATCHER} icon={AGENT_ICONS.WATCHER} className="mt-12" />
                                <AgentHexagon name="ADVISOR" status={agents.ADVISOR} icon={AGENT_ICONS.ADVISOR} />
                            </div>
                            
                            {/* Animated background circles */}
                            <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-20">
                                <circle cx="50%" cy="50%" r="200" fill="none" stroke="currentColor" className="text-blue-500 animate-spin-slow" strokeDasharray="10 10" />
                                <circle cx="50%" cy="50%" r="150" fill="none" stroke="currentColor" className="text-cyan-500 animate-spin-slow-reverse" strokeDasharray="5 5" />
                            </svg>
                        </>
                    )}
                </div>

                {/* Right Panel: Live Feed */}
                <div className="col-span-3 h-full">
                    <LiveFeed logs={logs} />
                </div>
            </div>
        </main>
    )
}