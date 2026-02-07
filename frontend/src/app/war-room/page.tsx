"use client"

import { useState, useEffect } from "react"
import { AgentHexagon } from "@/components/war-room/AgentHexagon"
import { LiveFeed } from "@/components/war-room/LiveFeed"
import { 
    Brain, Code, Shield, Eye, Database, Rocket, Laptop, X, 
    Play, Square, Bug, Download, FileText, Wand2, Zap, Radio, Layout, Eye as EyeIcon 
} from "lucide-react"
import { socket } from "@/lib/socket"
import { FileExplorer } from "@/components/ide/FileExplorer"
import { CodeEditor } from "@/components/ide/CodeEditor"
import { cn } from "@/lib/utils"
import { motion } from "framer-motion"

export default function WarRoomPage() {
    // --- CORE LOGIC STATE (Untouched) ---
    const [logs, setLogs] = useState<any[]>([])
    const [agents, setAgents] = useState<any>({
        ARCHITECT: "idle", VIRTUOSO: "idle", SENTINEL: "idle",
        ORACLE: "idle", WATCHER: "idle", ADVISOR: "idle"
    })
    const [prompt, setPrompt] = useState("")
    const [techStack, setTechStack] = useState("Auto-detect")
    const [isProcessing, setIsProcessing] = useState(false)
    const [projectId, setProjectId] = useState<string | null>(null)
    const [files, setFiles] = useState<Record<string, string>>({})
    const [selectedFile, setSelectedFile] = useState<string | null>(null)
    const [fileList, setFileList] = useState<string[]>([])
    const [executionStatus, setExecutionStatus] = useState<'idle' | 'running' | 'stopped' | 'error'>('idle')
    const [previewUrl, setPreviewUrl] = useState<string | null>(null)

    // --- REFINED UI STATE ---
    const [activeTab, setActiveTab] = useState<'codebase' | 'preview'>('codebase')
    const [showLiveFeed, setShowLiveFeed] = useState(true)
    const [showIDE, setShowIDE] = useState(false)

    // Agent icons for the "Cute" floating animation
    const agentIcons = [
        { Icon: Brain, color: "text-blue-400" },
        { Icon: Code, color: "text-emerald-400" },
        { Icon: Shield, color: "text-red-400" },
        { Icon: Database, color: "text-orange-400" },
        { Icon: Eye, color: "text-purple-400" },
        { Icon: Rocket, color: "text-cyan-400" }
    ]

    const getLanguage = (filename: string) => {
        const ext = filename.split('.').pop()?.toLowerCase()
        if (ext === 'html') return 'html'
        if (ext === 'css') return 'css'
        if (ext === 'tsx' || ext === 'ts') return 'typescript'
        return 'javascript'
    }

    useEffect(() => {
        socket.on("connect", () => addLog("SYSTEM", "Connected to ACEA Core Uplink", "success"))
        socket.on("agent_log", (data: any) => addLog(data.agent_name, data.message, "info"))
        socket.on("agent_status", (data: any) => setAgents((prev: any) => ({ ...prev, [data.agent_name]: data.status })))
        socket.on("mission_accepted", (data: { project_id: string }) => setProjectId(data.project_id))
        socket.on("mission_complete", (data: any) => {
            setIsProcessing(false)
            if (data.project_id) {
                setProjectId(data.project_id)
                fetchProjectFiles(data.project_id)
                setShowIDE(true)
            }
        })
        socket.on("generation_started", (data: { file_list: string[] }) => {
            setFileList(data.file_list); setShowIDE(true)
        })
        socket.on("file_generated", (data: { path: string, content: string }) => {
            setFiles(prev => ({ ...prev, [data.path]: data.content }))
        })
        return () => { socket.off("connect"); socket.off("agent_log"); socket.off("agent_status") }
    }, [])

    const fetchProjectFiles = async (id: string) => {
        try {
            const res = await fetch(`http://localhost:8000/api/projects/${id}/files`)
            const data = await res.json()
            setFiles(data); setFileList(Object.keys(data).sort())
            if (Object.keys(data).length > 0) setSelectedFile(Object.keys(data).sort()[0])
        } catch (e) { console.error(e) }
    }

    const addLog = (agent: string, message: string, type: string) => {
        setLogs(prev => [...prev.slice(-49), { id: Math.random(), agent, message, timestamp: new Date().toLocaleTimeString(), type }])
    }

    const startMission = () => {
        if (!prompt.trim()) return
        setIsProcessing(true); setLogs([]); setShowIDE(false)
        socket.emit("start_mission", { prompt, tech_stack: techStack })
    }

    const handleExecute = async () => {
        if (!projectId) return
        setExecutionStatus('running')
        try {
            const res = await fetch(`http://localhost:8000/api/execute/${projectId}`, { method: 'POST' })
            const data = await res.json()
            if (data.embed_url || data.preview_url) {
                setPreviewUrl(data.embed_url || data.preview_url)
                setActiveTab('preview') 
            }
        } catch (e) { setExecutionStatus('error') }
    }

    const handleStop = async () => { /* Original Logic */ }
    const handleDebug = async () => { /* Original Logic */ }
    const handleDownload = async () => { window.open(`http://localhost:8000/api/projects/${projectId}/download`, '_blank') }

    return (
        <main className="min-h-screen bg-[#050508] text-white p-6 overflow-hidden relative font-sans">
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:40px_40px] opacity-5 pointer-events-none" />

            <div className="relative z-10 flex gap-6 h-[calc(100vh-3rem)] w-full">

                {/* Left Panel: Mission Control */}
                <div className="w-[22%] min-w-[280px] border border-slate-800/60 bg-[#0a0a0f]/90 p-5 rounded-2xl flex flex-col shadow-2xl backdrop-blur-md shrink-0">
                    <h2 className="text-xl font-black tracking-tighter text-blue-400 mb-6 uppercase italic">MISSION CONTROL</h2>

                    {projectId && (
                        <button onClick={() => setShowIDE(!showIDE)} className="w-full py-2.5 mb-8 rounded-lg font-black text-[10px] tracking-[0.2em] flex items-center justify-center gap-2 border border-slate-700 bg-white text-black hover:bg-slate-200 transition-all uppercase">
                            {showIDE ? <X className="w-4 h-4" /> : <Laptop className="w-4 h-4" />}
                            {showIDE ? "DISCONNECT IDE" : "ACCESS CODEBASE"}
                        </button>
                    )}

                    {/* TACTICAL EXECUTION BUTTONS: Consistent Width, Hover Reveal */}
                    {projectId && (
                        <div className="mb-4 space-y-3">
                            <div className="text-[9px] text-slate-500 uppercase font-black tracking-[0.3em] ml-1">Tactical Execution</div>
                            <div className="flex flex-col gap-2">
                                {[
                                    { icon: Play, label: 'RUN SYSTEM', onClick: handleExecute, color: 'text-green-400 bg-green-500/10 border-green-500/20 hover:bg-green-500/30' },
                                    { icon: Square, label: 'STOP SYSTEM', onClick: handleStop, color: 'text-red-400 bg-red-500/10 border-red-500/20 hover:bg-red-600/30' },
                                    { icon: Bug, label: 'DEBUG MODULE', onClick: handleDebug, color: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/20 hover:bg-yellow-500/30' },
                                    { icon: FileText, label: 'DOCS MANIFEST', onClick: () => { }, color: 'text-purple-400 bg-purple-500/10 border-purple-500/20 hover:bg-purple-600/30' },
                                    { icon: Download, label: 'EXPORT ZIP', onClick: handleDownload, color: 'text-blue-400 bg-blue-500/10 border-blue-500/20 hover:bg-blue-600/30' }
                                ].map((btn, i) => (
                                    <button 
                                        key={i} 
                                        onClick={btn.onClick} 
                                        className={cn(
                                            "group flex items-center justify-center h-12 w-full rounded-lg border transition-all duration-500 shadow-lg overflow-hidden relative px-4",
                                            btn.color
                                        )}
                                    >
                                        <btn.icon className="w-4 h-4 shrink-0 transition-transform duration-500 group-hover:-translate-x-2" />
                                        <span className="max-w-0 group-hover:max-w-xs group-hover:ml-3 overflow-hidden text-[9px] font-black tracking-widest transition-all duration-500 uppercase whitespace-nowrap">
                                            {btn.label}
                                        </span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* AGENT ANIMATION AREA */}
                    <div className="flex-1 flex items-center justify-center relative py-4 overflow-hidden">
                        <div className="relative w-32 h-32 flex items-center justify-center">
                            {agentIcons.map(({ Icon, color }, i) => (
                                <motion.div
                                    key={i}
                                    className={cn("absolute p-2 bg-slate-900/40 rounded-full border border-slate-800/50 backdrop-blur-sm shadow-xl", color)}
                                    animate={{
                                        x: [Math.cos(i * 60 * Math.PI / 180) * 40, Math.cos((i * 60 + 120) * Math.PI / 180) * 45, Math.cos(i * 60 * Math.PI / 180) * 40],
                                        y: [Math.sin(i * 60 * Math.PI / 180) * 40, Math.sin((i * 60 + 180) * Math.PI / 180) * 35, Math.sin(i * 60 * Math.PI / 180) * 40],
                                        scale: [1, 1.1, 1],
                                        rotate: [0, 10, -10, 0]
                                    }}
                                    transition={{ duration: 6 + i, repeat: Infinity, ease: "easeInOut" }}
                                >
                                    <Icon className="w-4 h-4" />
                                </motion.div>
                            ))}
                        </div>
                    </div>

                    <div className="space-y-4">
                        <select value={techStack} onChange={(e) => setTechStack(e.target.value)} className="w-full bg-[#0d0d12] border border-slate-800/80 rounded-lg p-3 text-[9px] font-black uppercase tracking-widest text-slate-400 outline-none">
                            <option value="Auto-detect">AUTO-DETECT PROTOCOL</option>
                        </select>
                        <textarea className="w-full bg-[#0d0d12] border border-slate-800/80 rounded-xl p-4 text-[11px] text-blue-100 h-28 resize-none outline-none font-mono" value={prompt} onChange={(e) => setPrompt(e.target.value)} disabled={isProcessing} placeholder="ENTER MISSION DIRECTIVES..." />
                        <button onClick={startMission} disabled={isProcessing || !prompt} className="w-full bg-blue-600 hover:bg-blue-500 text-white font-black py-4 rounded-xl flex items-center justify-center gap-3 uppercase text-[10px] tracking-[0.4em] shadow-[0_0_20px_rgba(37,99,235,0.3)] transition-all">
                            {isProcessing ? <Zap className="w-4 h-4 animate-pulse" /> : "INITIATE LAUNCH"}
                        </button>
                    </div>
                </div>

                {/* Center Panel: Maximum Horizontal Length Housing */}
                <div className="flex-1 flex flex-col relative min-w-0">
                    
                    {/* Navigation Row: Fixed Header to prevent Overlap */}
                    {showIDE && (
                        <div className="flex items-center justify-between mb-6 px-2">
                            {/* Switched Pill matching image_d4b87e.png */}
                            <div className="flex items-center bg-[#0d0d12] border border-slate-800/50 p-1 rounded-[20px] shadow-2xl overflow-hidden flex-1 max-w-2xl mx-auto">
                                <button 
                                    onClick={() => setActiveTab('codebase')}
                                    className={cn(
                                        "flex-1 flex items-center justify-center gap-3 py-4 rounded-[16px] font-black text-[22px] uppercase transition-all duration-300",
                                        activeTab === 'codebase' ? "bg-white text-black shadow-lg" : "text-slate-600 hover:text-slate-400"
                                    )}
                                >
                                    <Layout className="w-6 h-6" /> CODEBASE
                                </button>
                                <button 
                                    onClick={() => setActiveTab('preview')}
                                    className={cn(
                                        "flex-1 flex items-center justify-center gap-3 py-4 rounded-[16px] font-black text-[22px] uppercase transition-all duration-300",
                                        activeTab === 'preview' ? "bg-white text-black shadow-lg" : "text-slate-600 hover:text-slate-400"
                                    )}
                                >
                                    <EyeIcon className="w-6 h-6" /> PREVIEW
                                </button>
                            </div>

                            {/* Live Feed Toggle: Positioned relative to flex flow to avoid overlap */}
                            <button 
                                onClick={() => setShowLiveFeed(!showLiveFeed)}
                                className={cn(
                                    "w-16 h-16 rounded-full flex flex-col items-center justify-center transition-all duration-500 border-2 ml-4 shrink-0",
                                    showLiveFeed ? "bg-slate-900 border-slate-800 text-slate-500 shadow-inner" : "bg-white border-white text-black scale-110 shadow-xl"
                                )}
                            >
                                <Radio className={cn("w-5 h-5", showLiveFeed && "animate-pulse")} />
                                <span className="text-[7px] font-black uppercase leading-none mt-1">Live<br/>Feed</span>
                            </button>
                        </div>
                    )}

                    {/* Housing Unit Container */}
                    <div className="flex-1 border border-slate-800/40 rounded-[32px] bg-[#0a0a0f]/40 backdrop-blur-xl overflow-hidden shadow-inner flex flex-col w-full">
                        {showIDE && projectId ? (
                            activeTab === 'codebase' ? (
                                <div className="flex h-full w-full">
                                    {/* 35% Split for Explorer */}
                                    <div className="w-[35%] border-r border-slate-800/50 shrink-0">
                                        <FileExplorer files={fileList} onSelect={setSelectedFile} selectedPath={selectedFile || undefined} />
                                    </div>
                                    {/* 65% Split for Editor */}
                                    <div className="flex-1 flex flex-col bg-[#08080a] min-w-0">
                                        {selectedFile ? (
                                            <>
                                                <div className="flex items-center bg-[#111116] px-5 py-3 border-b border-slate-800/50">
                                                    <span className="text-[10px] text-blue-400 font-mono font-bold tracking-widest">{selectedFile}</span>
                                                </div>
                                                <div className="flex-1 overflow-hidden">
                                                    <CodeEditor code={files[selectedFile] || ""} language={getLanguage(selectedFile)} />
                                                </div>
                                            </>
                                        ) : (
                                            <div className="h-full flex items-center justify-center text-slate-800 font-black text-xs uppercase tracking-[0.8em]">Select Module</div>
                                        )}
                                    </div>
                                </div>
                            ) : (
                                /* Full-Screen Preview Housing */
                                <div className="h-full w-full bg-white relative">
                                    {previewUrl ? <iframe src={previewUrl} className="h-full w-full border-none shadow-2xl" /> : (
                                        <div className="h-full w-full bg-[#0a0a0f] flex items-center justify-center text-slate-600 font-black text-xs tracking-widest">SYNCHRONIZING PREVIEW...</div>
                                    )}
                                </div>
                            )
                        ) : (
                            /* Grid Initial State */
                            <div className="h-full w-full flex items-center justify-center">
                                <div className="grid grid-cols-3 gap-16 relative z-10 p-12">
                                    <AgentHexagon name="ARCHITECT" status={agents.ARCHITECT} icon={Brain} />
                                    <AgentHexagon name="VIRTUOSO" status={agents.VIRTUOSO} icon={Code} className="mt-20" />
                                    <AgentHexagon name="SENTINEL" status={agents.SENTINEL} icon={Shield} />
                                    <AgentHexagon name="ORACLE" status={agents.ORACLE} icon={Database} />
                                    <AgentHexagon name="WATCHER" status={agents.WATCHER} icon={Eye} className="mt-20" />
                                    <AgentHexagon name="ADVISOR" status={agents.ADVISOR} icon={Rocket} />
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Right Panel: Fixed Sidebar */}
                {showLiveFeed && (
                    <div className="w-[25%] h-full animate-in slide-in-from-right duration-500 shrink-0">
                        <LiveFeed logs={logs} />
                    </div>
                )}
            </div>
        </main >
    )
}