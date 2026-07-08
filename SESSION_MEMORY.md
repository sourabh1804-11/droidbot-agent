# DroidBot AI Project - Session Memory & Architecture

## Core Architecture
- **Environment:** Natively runs on a rooted Android device using Termux.
- **Dependencies:** Zero heavy dependencies. We completely removed the `google-genai` SDK to bypass Rust/cryptography compiler errors on Termux.
- **API Communication:** Uses Python's built-in `urllib` to make raw REST POST requests to the Gemini API (`generateContent`).
- **Device Control:** Utilizes Magisk `su` (Root) to execute native shell commands (`input tap`, `input swipe`, `input keyevent`, `input text`), completely bypassing Android Accessibility services.
- **Rate Limit Handling:** Features a robust 3-tier fallback system (`gemini-2.5-flash` → `gemini-2.0-flash` → `gemini-2.0-flash-lite`) if hitting 429/503 errors on the free tier.

## Voice Integration (Walkie-Talkie Mode)
- **Problem:** Android's native `SpeechRecognizer` API and `termux-speech-to-text` caused `BadTokenException` and background pop-up crashes on the user's custom crDroid ROM.
- **Solution:** We built a custom "Walkie-Talkie" system.
- **How it works:**
  1. The user presses `Enter` to start recording.
  2. `termux-microphone-record -f ~/goal.m4a` captures the raw audio.
  3. The user presses `Enter` to stop.
  4. The script base64-encodes the `.m4a` file and sends it directly to `gemini-2.0-flash-lite` via `inlineData` (`mimeType: audio/mp4`) for instantaneous transcription.
  5. The transcribed text is then fed to the main Agent Loop.

## Setup Instructions (for new devices)
1. Install Termux and Termux:API from F-Droid.
2. Grant Magisk Root to Termux.
3. Run the setup script: `pkg update -y && pkg install -y python termux-api && pip install python-dotenv`
4. Copy `mobile_agent.py` and `.env` to `~/` and `chmod 644`.

## Current Status & Next Steps
- **Status:** Fully functional. The agent can see the screen, think, execute root inputs, and listen to raw voice commands.
- **Next Steps:** Expanding automation capabilities, perhaps allowing the agent to scroll dynamically, read deep UI trees if screenshots aren't enough, or run persistent background loops.

> **SYSTEM INSTRUCTION FOR NEW CONVERSATIONS:** 
> When starting a new conversation regarding this project, Jarvis MUST read this `SESSION_MEMORY.md` file first to instantly restore full context of the architecture and previous fixes.
