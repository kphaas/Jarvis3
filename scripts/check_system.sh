#!/bin/bash

SKIP_BRAIN_HTTP=${1:-false}

OUTPUT_JSON=false
[[ ! -t 1 ]] && OUTPUT_JSON=true

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ALL_HEALTHY=true

check_service() {
    local node=$1
    local service=$2
    local url=$3
    local ssh_host=$4
    
    # Skip Brain HTTP check if requested (prevents nested SSH issues)
    if [[ "$SKIP_BRAIN_HTTP" == "true" ]] && [[ "$service" == "com.jarvis.brain" ]] && [[ -n "$url" ]]; then
        echo -e "${GREEN}✓${NC} $node: $service - Running (HTTP check skipped)"
        return
    fi
    
    local status="unknown"
    local message=""
    local process_ok=false
    local http_ok=false
    
    if [[ "$ssh_host" == "local" ]]; then
        launchctl list | grep -q "$service" 2>/dev/null && process_ok=true
    else
        ssh "$ssh_host" "launchctl list | grep -q '$service'" 2>/dev/null && process_ok=true
    fi
    
    if [[ -n "$url" ]]; then
        http_code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "$url" 2>/dev/null)
        if [[ "$http_code" == "200" ]] || [[ "$http_code" == "401" ]]; then
            http_ok=true
        fi
    fi
    
    if $process_ok && $http_ok; then
        status="healthy"
        message="OK"
    elif $process_ok && [[ -z "$url" ]]; then
        status="healthy"
        message="Running"
    elif ! $process_ok; then
        status="down"
        message="Process not running"
        ALL_HEALTHY=false
    elif ! $http_ok; then
        status="degraded"
        message="Process running but HTTP unreachable"
        ALL_HEALTHY=false
    fi
    
    if [[ "$status" == "healthy" ]]; then
        echo -e "${GREEN}✓${NC} $node: $service - $message"
    elif [[ "$status" == "degraded" ]]; then
        echo -e "${YELLOW}⚠${NC} $node: $service - $message"
    else
        echo -e "${RED}✗${NC} $node: $service - $message"
    fi
}

echo "JARVIS System Health Check"
echo "=========================="
echo ""

check_service "Brain" "com.jarvis.brain" "http://100.64.166.22:8182/health" "jarvisbrain@100.64.166.22"
check_service "Brain" "postgresql@16" "" "jarvisbrain@100.64.166.22"
check_service "Brain" "com.jarvis.ollama" "" "jarvisbrain@100.64.166.22"

check_service "Gateway" "com.jarvis.gateway" "http://100.112.63.25:8282/health" "infranet@100.112.63.25"

check_service "Endpoint" "com.jarvis.dashboard" "http://100.87.223.31:4000" "local"
check_service "Endpoint" "com.jarvis.voiceui" "http://100.87.223.31:4001/v1/voice/status" "local"
check_service "Endpoint" "com.jarvis.avatar" "http://100.87.223.31:4002/health" "local"

echo ""
if $ALL_HEALTHY; then
    echo -e "${GREEN}System Status: HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}System Status: DEGRADED${NC}"
    exit 1
fi
