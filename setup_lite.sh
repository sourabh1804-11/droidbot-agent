#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=========================================="
echo "🤖 DroidBot Mobile Agent - Lite Setup"
echo "=========================================="

echo "📦 Step 1/4: Granting storage access..."
termux-setup-storage <<< "y" 2>/dev/null || true
sleep 2

echo "📦 Step 2/4: Updating packages & installing dependencies..."
pkg update -y
pkg install -y python termux-api

echo "📦 Step 3/4: Installing python-dotenv..."
pip install python-dotenv

echo "📦 Step 4/4: Setting up files..."
cp /sdcard/Download/mobile_agent.py ~/mobile_agent.py
cp /sdcard/Download/mobile_agent.py ~/agent.py
cp /sdcard/Download/.env ~/.env
chmod 644 ~/mobile_agent.py ~/agent.py ~/.env

echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo "To run the agent with voice, type:"
echo "  python ~/agent.py"
