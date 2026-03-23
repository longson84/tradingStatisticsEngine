# Trading Statistics Engine - Setup Guide

This project uses **pnpm** for JavaScript package management and **uv** for Python dependency management.

## Prerequisites

- **Node.js** >= 18.0.0
- **pnpm** >= 9.0.0 (`npm install -g pnpm`)
- **uv** (Python package manager) - Install from https://docs.astral.sh/uv/
- **Python** >= 3.12

## Quick Start

### 1. Install Dependencies
```bash
# Install root dependencies (concurrently) and frontend dependencies
pnpm install

# Install Python dependencies
uv sync
```

### 2. Run Both Services
```bash
# Start both backend and frontend
pnpm dev
```

This will start:
- **Backend API**: http://localhost:8002/docs
- **Frontend**: http://localhost:5174

## Available Scripts

### Root Level (pnpm)
```bash
pnpm dev              # Run both backend and frontend
pnpm dev:backend      # Run only FastAPI backend
pnpm dev:frontend     # Run only React frontend
pnpm build            # Build frontend
pnpm lint             # Lint frontend code
pnpm test             # Run Python tests
pnpm setup            # Install all dependencies (pnpm + uv)
pnpm clean            # Clean node_modules and build artifacts
```

### Frontend Only (from frontend/ directory)
```bash
cd frontend
pnpm dev              # Development server
pnpm build            # Production build
pnpm lint             # ESLint
pnpm preview          # Preview production build
```

### Backend Only (uv)
```bash
# Run API server
uv run uvicorn api.main:app --reload --port 8001

# Run tests
uv run pytest
uv run pytest -w      # Watch mode
```

## Project Structure

```
/Users/longson/Projects/tradingStatisticsEngine/
├── api/                    # FastAPI backend
│   ├── main.py            # API entry point
│   ├── routes/            # API routes
│   └── schemas/           # Pydantic schemas
├── frontend/              # React + TypeScript + Vite
│   ├── src/               # Source code
│   ├── package.json       # Frontend dependencies
│   └── pnpm-lock.yaml     # pnpm lock file
├── trading_engine/        # Core Python trading library
├── tests/                 # Python tests
├── pyproject.toml         # Python dependencies (uv)
├── uv.lock               # uv lock file
├── package.json          # Root scripts (pnpm)
├── pnpm-workspace.yaml   # pnpm workspace config
└── pnpm-lock.yaml        # pnpm lock file
```

## Technology Stack

### Backend
- **FastAPI** - Modern, fast web framework
- **uv** - Python package manager
- **Pydantic** - Data validation
- **Trading Engine** - Custom backtesting library

### Frontend
- **React 19** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool
- **pnpm** - Package manager
- **Tailwind CSS** - Styling

## Development Workflow

1. **Backend changes**: Edit Python files, FastAPI auto-reloads
2. **Frontend changes**: Edit React/TypeScript files, Vite auto-reloads
3. **Both services**: Use `pnpm dev` to run everything together

## Package Managers

- **pnpm**: For all JavaScript/TypeScript dependencies
- **uv**: For all Python dependencies
- No npm or yarn usage in this project

## Troubleshooting

### Port Conflicts
- Backend runs on port 8001 (changed from 8000 to avoid conflicts)
- Frontend runs on port 5173 (Vite will auto-increment if busy)

### Clean Install
```bash
pnpm clean
rm -rf node_modules .pnpm-store
uv venv --remove
pnpm setup
```

### Check Versions
```bash
node --version
pnpm --version
uv --version
python --version
```