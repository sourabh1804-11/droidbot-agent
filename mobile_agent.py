#!/usr/bin/env python3
"""
Mobile AI Agent — runs natively on Android via Termux + Magisk Root.
Uses Gemini Vision REST API (zero heavy dependencies) and root commands.

Only requires: python-dotenv (pure Python, installs instantly)
"""

import os
import re
import sys
import ssl
import time
import json
import base64
import subprocess
import urllib.request
import urllib.error
from dotenv import load_dotenv

# ─── Configuration ───────────────────────────────────────────────────────────

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("ERROR: API Key not found!")
    print("Make sure a .env file exists in the same folder as this script,")
    print("containing: GEMINI_API_KEY=your_key_here")
    sys.exit(1)

# Ordered model fallback chain
MODEL_CHAIN = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Where screenshots are temporarily saved on the device
SCREENSHOT_PATH = "/sdcard/screen.png"

# Free-tier rate limit: 5 requests per minute → wait ≥12s between calls
STEP_DELAY = 13


# ─── Gemini REST API (no SDK needed) ────────────────────────────────────────

def call_gemini_api(model: str, prompt: str, image_bytes: bytes) -> dict:
    """Call Gemini generateContent REST API directly with urllib."""
    url = f"{API_BASE}/{model}:generateContent?key={API_KEY}"

    # Encode image as base64
    b64_image = base64.b64encode(image_bytes).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": "image/png",
                        "data": b64_image
                    }
                }
            ]
        }]
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # Create SSL context (Termux's Python has SSL built in)
    ctx = ssl.create_default_context()

    response = urllib.request.urlopen(req, context=ctx, timeout=60)
    return json.loads(response.read().decode("utf-8"))


# ─── Device Control (Root) ───────────────────────────────────────────────────

def run_root(cmd: str, timeout: int = 10) -> subprocess.CompletedProcess:
    """Execute a single shell command as root via Magisk su."""
    return subprocess.run(
        ["su", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def wake_screen():
    """Ensure the screen is on before we start working."""
    result = run_root("dumpsys power | grep 'Display Power'")
    if "OFF" in result.stdout.upper():
        print("Screen is off — waking up...")
        run_root("input keyevent 26")   # POWER button
        time.sleep(1)
        run_root("input swipe 540 2000 540 800")  # swipe up to dismiss lock
        time.sleep(1)


def take_screenshot() -> str:
    """Capture the current screen to a PNG file on the device."""
    print("📸 Taking screenshot...")
    result = run_root(f"screencap -p {SCREENSHOT_PATH}")
    if result.returncode != 0:
        print(f"  ⚠ screencap error: {result.stderr.strip()}")
    return SCREENSHOT_PATH


def execute_action(action: str, x=None, y=None, text=None,
                   x2=None, y2=None) -> bool:
    """Execute an action on the device. Returns True if goal is done."""
    if action == "click" and x is not None and y is not None:
        print(f"👆 Tapping ({x}, {y})")
        run_root(f"input tap {int(x)} {int(y)}")

    elif action == "long_press" and x is not None and y is not None:
        print(f"👆 Long-pressing ({x}, {y})")
        run_root(f"input swipe {int(x)} {int(y)} {int(x)} {int(y)} 800")

    elif action == "swipe":
        sx, sy = int(x or 540), int(y or 1800)
        ex, ey = int(x2 or 540), int(y2 or 600)
        print(f"👆 Swiping ({sx},{sy}) → ({ex},{ey})")
        run_root(f"input swipe {sx} {sy} {ex} {ey} 300")

    elif action == "type" and text:
        safe = text.replace(" ", "%s").replace("'", "\\'")
        print(f"⌨️  Typing: {text}")
        run_root(f"input text '{safe}'")

    elif action == "keyevent":
        code = text or "66"
        print(f"⌨️  Keyevent {code}")
        run_root(f"input keyevent {code}")

    elif action == "home":
        print("🏠 Going to Home Screen")
        run_root("input keyevent 3")

    elif action == "back":
        print("◀ Going Back")
        run_root("input keyevent 4")

    elif action == "done":
        print("✅ Goal Achieved!")
        return True

    else:
        print(f"⚠ Unknown action: {action}")

    return False


# ─── Gemini Vision ───────────────────────────────────────────────────────────

def ask_gemini(goal: str, image_path: str, step: int, max_steps: int) -> dict:
    """Send screenshot + goal to Gemini and get a structured action back."""

    # Read the screenshot as raw bytes
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    prompt = f"""You are an AI agent running directly on a rooted Android phone.
Your goal: "{goal}"

This is step {step} of {max_steps}. Look at the screenshot and decide the 
SINGLE next action to progress toward the goal.

Available actions:
- "click"      → tap at (x, y)
- "long_press" → long-press at (x, y)
- "swipe"      → swipe from (x, y) to (x2, y2)
- "type"       → type the given text
- "keyevent"   → send a keyevent code (put code in "text", e.g. "66" for Enter, "4" for Back)
- "home"       → go to Home Screen
- "back"       → press the Back button
- "done"       → goal is complete

Respond ONLY with a valid JSON object:
{{
    "thought": "brief reasoning",
    "action": "click",
    "x": 500,
    "y": 1000,
    "x2": null,
    "y2": null,
    "text": ""
}}"""

    # Try each model in the fallback chain
    for model_name in MODEL_CHAIN:
        for attempt in range(2):
            try:
                print(f"🧠 Asking Gemini ({model_name})...")
                result = call_gemini_api(model_name, prompt, image_bytes)

                # Extract the text from the response
                raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                if not raw:
                    print("  ⚠ Gemini returned an empty response.")
                    return {"action": "error"}

                # Strip markdown code fences if present
                cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
                cleaned = re.sub(r"\s*```$", "", cleaned)

                return json.loads(cleaned)

            except json.JSONDecodeError:
                print(f"  ⚠ Could not parse JSON. Raw:\n{raw}")
                return {"action": "error"}

            except urllib.error.HTTPError as e:
                code = e.code
                body = e.read().decode("utf-8", errors="replace")
                if code == 429 or "RESOURCE_EXHAUSTED" in body:
                    print(f"  ⏳ {model_name} rate-limited. Trying next model...")
                    break  # skip to next model
                elif code == 503:
                    wait = 15 * (attempt + 1)
                    print(f"  ⏳ {model_name} busy. Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    print(f"  ❌ HTTP {code}: {body[:200]}")
                    return {"action": "error"}

            except Exception as e:
                print(f"  ❌ Error: {e}")
                return {"action": "error"}

    print("  ❌ All models exhausted / rate-limited.")
    return {"action": "error"}


# ─── Agent Loop ──────────────────────────────────────────────────────────────

def run_agent(goal: str, max_steps: int = 15):
    """The core Observe → Think → Act loop."""
    print(f"\n🎯 Goal: {goal}")
    speak(f"Got it. Working on: {goal}")
    print("-" * 50)

    for step in range(1, max_steps + 1):
        print(f"\n--- Step {step}/{max_steps} ---")

        # 1. Observe
        img_path = take_screenshot()

        # 2. Think
        decision = ask_gemini(goal, img_path, step, max_steps)
        thought = decision.get("thought", "(no reasoning)")
        print(f"💭 Thought: {thought}")

        # 3. Act
        action = decision.get("action", "error")
        if action == "error":
            speak("Something went wrong. Stopping.")
            print("Stopping due to error.")
            break

        is_done = execute_action(
            action=action,
            x=decision.get("x"),
            y=decision.get("y"),
            text=decision.get("text"),
            x2=decision.get("x2"),
            y2=decision.get("y2"),
        )

        if is_done:
            speak("Done! Goal achieved.")
            break

        # Respect free-tier rate limits
        time.sleep(STEP_DELAY)

    print("\n" + "=" * 50)
    print("Agent loop finished.")


# ─── Voice I/O (Termux:API) ─────────────────────────────────────────────────

VOICE_ENABLED = False  # set to True after we confirm termux-api is available


import shutil

def check_voice_support():
    """Check if Termux:API is installed for voice features."""
    global VOICE_ENABLED
    try:
        if shutil.which("termux-speech-to-text"):
            VOICE_ENABLED = True
            return True
    except Exception:
        pass
    return False


def speak(text: str):
    """Speak text aloud using Termux:API TTS. Silent fallback if unavailable."""
    print(f"🔊 {text}")
    if not VOICE_ENABLED:
        return
    try:
        subprocess.Popen(
            ["termux-tts-speak", "-r", "1.2", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def transcribe_audio(audio_path: str) -> str:
    """Send raw audio to Gemini for perfect transcription."""
    print("☁️  Sending audio to Gemini for transcription...")
    try:
        with open(audio_path, "rb") as f:
            audio_b64 = base64.b64encode(f.read()).decode("utf-8")
            
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-lite-preview-02-05:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": "Transcribe the following voice command precisely. Only output the transcribed text, nothing else."},
                    {
                        "inlineData": {
                            "mimeType": "audio/mp4",
                            "data": audio_b64
                        }
                    }
                ]
            }]
        }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"), 
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  ⚠ Transcription error: {e}")
        return ""


def listen() -> str:
    """Record raw audio and transcribe via Gemini."""
    audio_path = os.path.expanduser("~/goal.m4a")
    if os.path.exists(audio_path):
        os.remove(audio_path)
        
    input("\n🎤 Press [ENTER] to START speaking...")
    subprocess.run(["termux-microphone-record", "-f", audio_path])
    
    input("🔴 RECORDING... Press [ENTER] to STOP...")
    subprocess.run(["termux-microphone-record", "-q"])
    
    time.sleep(1)  # Ensure file is saved
    if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
        print("  ⚠ Audio file not found or empty.")
        return ""
        
    transcription = transcribe_audio(audio_path)
    if transcription:
        print(f"\n✨ You said: \"{transcription}\"")
        return transcription
    return ""


def get_user_input() -> str:
    """Get input via voice (preferred) or keyboard fallback."""
    print("\n💬 Say a command, or type one below.")
    print("   (Say 'exit' or type 'exit' to quit)")

    # Try voice first
    voice_input = listen()
    if voice_input:
        return voice_input

    # Fall back to typed input
    print("   Didn't catch that. You can type instead:")
    return input("> ")


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("🤖  MOBILE AI AGENT  (Termux + Magisk Root)")
    print("=" * 50)

    # Pre-flight: verify root access
    print("\nChecking root access...")
    try:
        r = run_root("id")
        if "uid=0" in r.stdout:
            print("✅ Root access confirmed!")
        else:
            print("⚠ Root check returned unexpected output:")
            print(f"   {r.stdout.strip()}")
            print("   The script may still work — Magisk might prompt you.")
    except Exception as e:
        print(f"⚠ Could not verify root: {e}")
        print("  Make sure Magisk is installed and grant permission when prompted.")

    # Check for voice support
    print("\nChecking voice support...")
    if check_voice_support():
        print("✅ Voice control enabled! (Termux:API detected)")
        speak("Mobile AI Agent ready. What would you like me to do?")
    else:
        print("ℹ️  Voice not available — using keyboard input.")
        print("   To enable voice, install Termux:API app from F-Droid,")
        print("   then run: pkg install termux-api")

    # Wake the screen so Gemini sees something useful
    wake_screen()

    # Interactive loop
    while True:
        user_goal = get_user_input()

        if user_goal.strip().lower() in ("exit", "quit", "q", "stop"):
            speak("Goodbye!")
            print("Goodbye! 👋")
            break

        if user_goal.strip():
            run_agent(user_goal.strip())
