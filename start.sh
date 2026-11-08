#!/bin/bash
echo "🚀 Starting Offline AI Personal Manager..."

# Kill anything running on ports 3000 and 8000
kill $(lsof -t -i:3000) 2>/dev/null
kill $(lsof -t -i:8000) 2>/dev/null

# Activate virtual environment
source venv/bin/activate

# Start Python server in background
cd ai-engine
uvicorn main:app --port 8000 &
cd ..

echo "⏳ Waiting for Python server..."
sleep 5

echo "✅ Starting Node.js server..."
node backend/server.js