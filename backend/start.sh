#!/bin/bash
#
# TA Engine Startup Script
# ========================
#
# Quick start:
#   ./start.sh              # Start everything
#   ./start.sh --bootstrap  # Bootstrap + start
#   ./start.sh --status     # Check status only
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  TA ENGINE"
echo "═══════════════════════════════════════════════════════"
echo ""

# Check MongoDB
check_mongo() {
    if mongosh --eval "db.adminCommand('ping')" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} MongoDB running"
        return 0
    else
        echo -e "${RED}✗${NC} MongoDB not running"
        return 1
    fi
}

# Check Node server
check_node() {
    if curl -s http://localhost:3001/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Node TA Engine running (port 3001)"
        return 0
    else
        echo -e "${YELLOW}○${NC} Node TA Engine not running"
        return 1
    fi
}

# Check Python server
check_python() {
    if curl -s http://localhost:8001/api/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Python API running (port 8001)"
        return 0
    else
        echo -e "${YELLOW}○${NC} Python API not running"
        return 1
    fi
}

# Bootstrap
run_bootstrap() {
    echo ""
    echo "Running bootstrap..."
    python bootstrap.py
}

# Status
show_status() {
    echo ""
    echo "System Status:"
    echo "─────────────────────────────────────────────────────"
    check_mongo || true
    check_node || true
    check_python || true
    
    echo ""
    echo "Data Status:"
    echo "─────────────────────────────────────────────────────"
    python bootstrap.py --status 2>/dev/null | grep -A 20 "Candles:" || echo "Run --bootstrap first"
}

# Start servers
start_servers() {
    echo ""
    echo "Starting servers..."
    echo "─────────────────────────────────────────────────────"
    
    # Check if supervisor is available
    if command -v supervisorctl &> /dev/null; then
        sudo supervisorctl restart backend
        echo -e "${GREEN}✓${NC} Backend restarted via supervisor"
    else
        # Manual start
        echo "Starting Python server..."
        cd "$SCRIPT_DIR"
        nohup python -m uvicorn server:app --host 0.0.0.0 --port 8001 > /tmp/ta_python.log 2>&1 &
        echo -e "${GREEN}✓${NC} Python server started"
        
        echo "Starting Node server..."
        nohup npx tsx src/server.ta.ts > /tmp/ta_node.log 2>&1 &
        echo -e "${GREEN}✓${NC} Node server started"
    fi
    
    sleep 3
    show_status
}

# Main
case "${1:-}" in
    --bootstrap)
        check_mongo
        run_bootstrap
        start_servers
        ;;
    --status)
        show_status
        ;;
    --help)
        echo "Usage: ./start.sh [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --bootstrap   Run bootstrap and start"
        echo "  --status      Show system status"
        echo "  --help        Show this help"
        echo ""
        ;;
    *)
        check_mongo
        start_servers
        ;;
esac

echo ""
echo "═══════════════════════════════════════════════════════"
echo ""
