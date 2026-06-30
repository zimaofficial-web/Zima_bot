import asyncio
import os
import sqlite3
import time
from telethon import TelegramClient

# Telethon Credentials
API_ID = 32405649
API_HASH = "5cae30bd8cdc3fa9f0c4e481c1b77564"

# Database Configuration
DB_PATH = os.path.join(os.path.dirname(__file__), "bot.db")
TARGET_CHAT_ID = -1002637286707  # Your group chat ID


def save_members_to_db(members_list):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    count = 0
    for m_id, username, first_name in members_list:
        try:
            cursor.execute(
                """INSERT INTO members (chat_id, user_id, username, first_name, last_seen)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(chat_id, user_id) DO UPDATE SET
                     username=excluded.username,
                     first_name=excluded.first_name""",
                (TARGET_CHAT_ID, m_id, username, first_name, int(time.time())),
            )
            count += 1
        except Exception as e:
            print(f"Failed to insert {username or first_name}: {e}")
            
    conn.commit()
    conn.close()
    return count


async def main():
    print("Initializing Telegram Client...")
    # This will create a session file named 'scraper.session' in the same folder
    client = TelegramClient("scraper", API_ID, API_HASH)
    
    await client.start()
    
    print("\nSuccessfully logged in! Fetching group members...")
    
    try:
        # Fetch the group entity
        group = await client.get_input_entity(TARGET_CHAT_ID)
        
        # Fetch all participants
        participants = await client.get_participants(group)
        
        members_to_save = []
        for p in participants:
            if p.bot:
                continue  # Skip bots
            members_to_save.append((p.id, p.username, p.first_name or ""))
            
        print(f"Found {len(members_to_save)} members in the group.")
        
        saved_count = save_members_to_db(members_to_save)
        print(f"Successfully saved {saved_count} members to your database (bot.db)!")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        print("\nMake sure the bot/your account is actively inside the group chat.")
        
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
