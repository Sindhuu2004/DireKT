#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  SilverEdge — One-command launcher (Mac / Linux)
#  Usage:  chmod +x start.sh && ./start.sh
# ─────────────────────────────────────────────────────────
set -e

CYAN='\033[0;36m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

echo -e "${CYAN}"
echo "  ███████╗██╗██╗   ██╗███████╗██████╗ ███████╗██████╗  ██████╗ ███████╗"
echo "  ██╔════╝██║██║   ██║██╔════╝██╔══██╗██╔════╝██╔══██╗██╔════╝ ██╔════╝"
echo "  ███████╗██║██║   ██║█████╗  ██████╔╝█████╗  ██║  ██║██║  ███╗█████╗  "
echo "  ╚════██║██║╚██╗ ██╔╝██╔══╝  ██╔══██╗██╔══╝  ██║  ██║██║   ██║██╔══╝  "
echo "  ███████║██║ ╚████╔╝ ███████╗██║  ██║███████╗██████╔╝╚██████╔╝███████╗"
echo "  ╚══════╝╚═╝  ╚═══╝  ╚══════╝╚═╝  ╚═╝╚══════╝╚═════╝  ╚═════╝ ╚══════╝"
echo -e "${NC}"
echo -e "  MCX Silver Algorithmic Trading Platform"
echo ""

# ── Check .env ───────────────────────────────────────────
if [ ! -f backend/.env ]; then
  echo -e "${YELLOW}⚠  backend/.env not found — copying from .env.example${NC}"
  cp backend/.env.example backend/.env
  echo -e "${RED}✗  Please fill in your credentials in backend/.env then re-run.${NC}"
  echo ""
  echo "  Required keys:"
  echo "    ANGEL_ONE_API_KEY, ANGEL_ONE_CLIENT_ID, ANGEL_ONE_PASSWORD"
  echo "    ANGEL_ONE_TOTP_SECRET, DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN"
  echo "    SECRET_KEY  (generate: python3 -c \"import secrets; print(secrets.token_hex(32))\")"
  exit 1
fi

# ── Backend ──────────────────────────────────────────────
echo -e "${CYAN}[1/4]${NC} Setting up Python virtual environment…"
cd backend
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
echo -e "${CYAN}[2/4]${NC} Installing Python dependencies…"
pip install -q -r requirements.txt
echo -e "${GREEN}✓  Backend dependencies installed${NC}"

echo -e "${CYAN}[3/4]${NC} Starting FastAPI backend on port 8000…"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
echo -e "${GREEN}✓  Backend PID: $BACKEND_PID${NC}"
cd ..

# ── Frontend ─────────────────────────────────────────────
echo -e "${CYAN}[4/4]${NC} Installing frontend dependencies…"
cd frontend
if [ ! -d "node_modules" ]; then
  npm install --silent
fi
echo -e "${GREEN}✓  Frontend dependencies installed${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Platform is starting!${NC}"
echo -e "${GREEN}  Dashboard  →  http://localhost:3000${NC}"
echo -e "${GREEN}  API Docs   →  http://localhost:8000/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Press Ctrl+C to stop all services."
echo ""

# Start frontend (blocking)
npm run dev

# Cleanup on exit
kill $BACKEND_PID 2>/dev/null
echo -e "${YELLOW}  All services stopped.${NC}"
