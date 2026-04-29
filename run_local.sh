#!/bin/bash
# run_local.sh
# Script to run the Multi-Agent Productivity Assistant locally without Docker

echo -e "\033[0;36m🚀 Starting Multi-Agent Productivity Assistant (Local Mode without Docker)\033[0m"
echo -e "\033[0;36m==========================================================================\033[0m"

# Array to store PIDs of background processes
PIDS=()

# Cleanup function to kill background processes on exit
cleanup() {
    echo -e "\n\033[0;33m🧹 Stopping all background processes...\033[0m"
    for pid in "${PIDS[@]}"; do
        kill $pid 2>/dev/null
    done
    echo -e "\033[0;32m✅ All processes stopped. Goodbye!\033[0m"
    exit 0
}

# Trap SIGINT (Ctrl+C) and SIGTERM
trap cleanup SIGINT SIGTERM

export PYTHONPATH="$(pwd)"
export FIRESTORE_MODE="mock"
export PORT="8000"
export MCP_TASK_HOST="localhost"
export MCP_TASK_PORT="8001"
export MCP_CALENDAR_HOST="localhost"
export MCP_CALENDAR_PORT="8002"
export MCP_NOTES_HOST="localhost"
export MCP_NOTES_PORT="8003"
export MCP_CRITIC_HOST="localhost"
export MCP_CRITIC_PORT="8004"
export MCP_AUDITOR_HOST="localhost"
export MCP_AUDITOR_PORT="8005"
export MCP_EVENT_MONITOR_HOST="localhost"
export MCP_EVENT_MONITOR_PORT="8006"
export MCP_RESEARCH_HOST="localhost"
export MCP_RESEARCH_PORT="8007"
export MCP_NEWS_HOST="localhost"
export MCP_NEWS_PORT="8008"

# Start MCP Servers
echo -e "\033[0;33m📦 Starting MCP Servers...\033[0m"

start_mcp_server() {
    local name=$1
    local port=$2
    MCP_SERVER=$name MCP_PORT=$port python -m uvicorn backend.mcp_tools.server:app --host 127.0.0.1 --port $port > /dev/null 2>&1 &
    PIDS+=($!)
    echo -e "   \033[0;32m✅ Started $name on port $port (PID: $!)\033[0m"
}

start_mcp_server "task" 8001
start_mcp_server "calendar" 8002
start_mcp_server "notes" 8003
start_mcp_server "critic" 8004
start_mcp_server "auditor" 8005
start_mcp_server "event_monitor" 8006
start_mcp_server "research" 8007
start_mcp_server "news" 8008

echo -e "\033[0;35m🌐 Starting Orchestrator API & Dashboard on http://localhost:8000\033[0m"
echo -e "\033[0;37mPress Ctrl+C to stop everything.\033[0m"
echo -e "\033[0;36m==========================================================================\033[0m"

# Start the main Orchestrator App in foreground
python3 -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

# If uvicorn crashes or is manually stopped, trigger cleanup
cleanup
