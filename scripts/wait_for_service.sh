#!/bin/bash

wait_for_postgres() {
    echo "Waiting for Postgres..."
    for i in {1..30}; do
        if /opt/homebrew/Cellar/postgresql@16/16.13/bin/pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
            echo "Postgres ready"
            return 0
        fi
        sleep 2
    done
    echo "Postgres failed to start after 60s"
    return 1
}

wait_for_process() {
    local service_name=$1
    local max_wait=${2:-30}
    echo "Waiting for process: $service_name..."
    for i in $(seq 1 $max_wait); do
        if launchctl list | grep -q "$service_name"; then
            echo "$service_name running"
            return 0
        fi
        sleep 2
    done
    echo "$service_name failed to start"
    return 1
}

wait_for_http() {
    local url=$1
    local max_wait=${2:-60}
    echo "Waiting for HTTP: $url..."
    for i in $(seq 1 $max_wait); do
        if curl -s -f -m 2 "$url" >/dev/null 2>&1 || curl -s -m 2 "$url" 2>&1 | grep -q "Unauthorized"; then
            echo "$url ready"
            return 0
        fi
        sleep 2
    done
    echo "$url failed to respond"
    return 1
}

case "$1" in
    postgres) wait_for_postgres ;;
    process) wait_for_process "$2" "$3" ;;
    http) wait_for_http "$2" "$3" ;;
    *) echo "Usage: $0 {postgres|process|http} [args]"; exit 1 ;;
esac
