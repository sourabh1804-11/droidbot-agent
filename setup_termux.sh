#!/data/data/com.termux/files/usr/bin/bash
# ─── DroidBot Mobile Agent - One-Shot Setup ───
# Run this inside Termux to install everything and get the agent running.

set -e

echo "=========================================="
echo "🤖 DroidBot Mobile Agent - Setup"
echo "=========================================="

echo ""
echo "📦 Step 1/5: Granting storage access..."
termux-setup-storage <<< "y" 2>/dev/null || true
sleep 2

echo ""
echo "📦 Step 2/5: Updating Termux packages..."
pkg update -y

echo ""
echo "📦 Step 3/5: Installing Python + native libraries..."
pkg install -y python python-cryptography python-pillow

echo ""
echo "📦 Step 4/5: Installing Python AI packages..."
pip install python-dotenv google-genai

echo ""
echo "📦 Step 5/5: Copying agent files to Termux home..."
cp /sdcard/Download/mobile_agent.py ~/mobile_agent.py
cp /sdcard/Download/.env ~/.env

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "To run the AI agent, type:"
echo "  python ~/mobile_agent.py"
echo ""
