import os
import time
import json
import subprocess
from google import genai
from PIL import Image
from dotenv import load_dotenv

# Load API Key from .env
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise ValueError("API Key not found! Please check your .env file.")

# Configure Gemini
client = genai.Client(api_key=API_KEY)

def take_screenshot(filename="screen.png"):
    """Uses ADB to take a screenshot and pull it to the computer."""
    print("Taking screenshot...")
    subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "shell", "screencap", "-p", "/sdcard/screen.png"], capture_output=True)
    subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "pull", "/sdcard/screen.png", filename], capture_output=True)
    return filename

def execute_adb_command(action, x=None, y=None, text=None):
    """Executes the action on the phone via ADB."""
    if action == "click" and x and y:
        print(f"Tapping at ({x}, {y})")
        subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "shell", "input", "tap", str(x), str(y)])
    elif action == "type" and text:
        print(f"Typing: {text}")
        subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "shell", "input", "text", f"'{text}'"])
        # Press Enter
        subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "shell", "input", "keyevent", "66"])
    elif action == "home":
        print("Going to Home Screen")
        subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "shell", "input", "keyevent", "3"])
    elif action == "done":
        print("Goal Achieved!")
        return True
    return False

def ask_gemini_what_to_do(goal, image_path):
    """Sends the screenshot and goal to Gemini and asks for the next move."""
    img = Image.open(image_path)
    
    prompt = f"""
    You are an AI agent controlling an Android phone via ADB. 
    Your current goal is: "{goal}"
    
    Look at the attached screenshot of the phone's current state.
    Determine the single next action you need to take to progress toward the goal.
    
    Respond ONLY with a valid JSON object matching this exact structure:
    {{
        "thought": "Your reasoning for the next action",
        "action": "click",  // Can be "click", "type", "home", or "done"
        "x": 500,           // X coordinate for click (estimate center of the button/icon based on image)
        "y": 1000,          // Y coordinate for click (estimate center of the button/icon based on image)
        "text": ""          // Text to type if action is "type"
    }}
    """
    
    print("Asking Gemini for the next move...")
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=[prompt, img]
    )
    
    # Clean up the markdown JSON block if present
    response_text = response.text.strip()
    if response_text.startswith("```json"):
        response_text = response_text[7:-3]
        
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        print("Failed to parse Gemini's response. Raw response:")
        print(response.text)
        return {"action": "error"}

def run_agent_loop(goal, max_steps=10):
    print(f"Starting Agent Loop. Goal: {goal}")
    for step in range(max_steps):
        print(f"\n--- Step {step + 1} ---")
        
        # 1. Observe
        img_path = take_screenshot()
        
        # 2. Think
        decision = ask_gemini_what_to_do(goal, img_path)
        print(f"Gemini's Thought: {decision.get('thought', 'None')}")
        
        # 3. Act
        action = decision.get("action")
        if action == "error":
            break
            
        is_done = execute_adb_command(
            action=action, 
            x=decision.get("x"), 
            y=decision.get("y"), 
            text=decision.get("text")
        )
        
        if is_done:
            break
            
        # Wait a moment for UI animations to finish and avoid 5 RPM rate limit
        time.sleep(12)

if __name__ == "__main__":
    # Ensure ADB is connected
    subprocess.run([r"C:\Users\soura\OneDrive\Desktop\platform-tools\adb.exe", "devices"])
    
    # Define our very first test goal!
    print("\n" + "="*50)
    print("🤖 DROIDBOT AI AGENT READY")
    print("="*50)
    
    while True:
        user_goal = input("\nWhat would you like me to do on your phone? (or type 'exit' to quit)\n> ")
        
        if user_goal.strip().lower() == 'exit':
            break
            
        if user_goal.strip():
            run_agent_loop(user_goal)
