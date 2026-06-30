import os
import json
import logging
from telegram import Update
from telegram.ext import ContextTypes
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Ensure history directory exists
HISTORY_DIR = os.path.join(os.path.dirname(__file__), "chat_history")
os.makedirs(HISTORY_DIR, exist_ok=True)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    client = genai.Client(api_key=GEMINI_API_KEY)
else:
    client = None
    logger.warning("GEMINI_API_KEY is not set. AI chat will not work.")

SYSTEM_PROMPT = """
You are a helpful and friendly AI bot named "Zima". 
You assist Zima's friends and users in a Telegram group or DM.
Keep your responses concise, natural, and helpful. 
You are currently talking in a direct message (DM) to a user.
"""

def get_history_file(user_id: int) -> str:
    return os.path.join(HISTORY_DIR, f"{user_id}.json")

def load_history(user_id: int) -> list:
    filepath = get_history_file(user_id)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load history for {user_id}: {e}")
    return []

def save_history(user_id: int, history: list):
    filepath = get_history_file(user_id)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save history for {user_id}: {e}")

async def handle_dm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    user = update.effective_user
    
    if not msg or not msg.text or not user:
        return
        
    if not client:
        await msg.reply_text("My AI brain is offline! The GEMINI_API_KEY is missing from my environment.")
        return

    # Let the user know we are typing
    await context.bot.send_chat_action(chat_id=msg.chat_id, action="typing")
    
    # Load past messages for context
    raw_history = load_history(user.id)
    
    # Convert dict history to google.genai.types.Content objects
    contents = []
    for item in raw_history:
        contents.append(
            types.Content(
                role=item["role"],
                parts=[types.Part.from_text(text=item["text"])]
            )
        )
    
    # Add current message
    current_text = msg.text
    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=current_text)]
        )
    )
    raw_history.append({"role": "user", "text": current_text})
    
    # Keep only the last 40 messages to prevent exceeding context limits over long periods
    if len(contents) > 40:
        contents = contents[-40:]
        raw_history = raw_history[-40:]

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
            )
        )
        
        reply_text = response.text
        if not reply_text:
            reply_text = "I have nothing to say to that..."
            
        await msg.reply_text(reply_text)
        
        # Save response to history
        raw_history.append({"role": "model", "text": reply_text})
        save_history(user.id, raw_history)
        
    except Exception as e:
        logger.error(f"Gemini API Error: {e}")
        await msg.reply_text("I'm sorry, I ran into an error trying to think of a response!")
