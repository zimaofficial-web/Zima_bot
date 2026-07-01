"""
info.py — /stats, /active, /tagall

These all read from the members table that gets populated passively
as people talk (see track_member in bot.py).
"""

import time
import html
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from helpers import require_admin, require_group, require_subscription
import db

MENTIONS_PER_MESSAGE = 5
ACTIVE_WINDOW_SECONDS = 7 * 86400  # 7 days


@require_subscription
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group(update):
        return

    chat_id = update.effective_chat.id
    all_members = db.get_members(chat_id)
    active = db.get_active_members(chat_id, ACTIVE_WINDOW_SECONDS)

    await update.message.reply_text(
        f"📊 Group stats\n"
        f"Known members: {len(all_members)}\n"
        f"Active in last 7 days: {len(active)}\n\n"
        f"(\"Known\" = has sent at least one message since the bot joined.)"
    )


@require_subscription
async def active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group(update):
        return

    chat_id = update.effective_chat.id
    members = db.get_active_members(chat_id, ACTIVE_WINDOW_SECONDS)

    if not members:
        await update.message.reply_text("No activity tracked in the last 7 days.")
        return

    now = int(time.time())
    lines = []
    for m in sorted(members, key=lambda r: r["last_seen"], reverse=True):
        name = f"@{m['username']}" if m["username"] else m["first_name"]
        hours_ago = (now - m["last_seen"]) // 3600
        when = "just now" if hours_ago < 1 else f"{hours_ago}h ago"
        lines.append(f"• {name} — {when}")

    await update.message.reply_text("Active in the last 7 days:\n\n" + "\n".join(lines))


@require_subscription
async def tagall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    print(f"[*] /tagall triggered in chat {chat.id} by {update.effective_user.id}")
    if not await require_group(update) or not await require_admin(update):
        print("[-] /tagall failed: Not a group or not an admin")
        return

    members = db.get_members(chat.id)
    if not members:
        await update.message.reply_text(
            "I haven't seen anyone talk yet, so I don't have a member list. "
            "I can only tag people once they've sent at least one message."
        )
        return

    raw_text = update.message.text or update.message.caption or ""
    first_word = raw_text.split(maxsplit=1)[0].lower() if raw_text else ""
    if first_word.startswith("/") or first_word == "@all":
        parts = raw_text.split(maxsplit=1)
        note = parts[1] if len(parts) > 1 else ""
    else:
        note = raw_text

    mentions = []
    for m in members:
        if m["username"]:
            mentions.append(f"@{m['username']}")
        else:
            safe_name = html.escape(m["first_name"] or "User")
            mentions.append(f'<a href="tg://user?id={m["user_id"]}">{safe_name}</a>')

    import asyncio
    try:
        for i in range(0, len(mentions), MENTIONS_PER_MESSAGE):
            batch = mentions[i : i + MENTIONS_PER_MESSAGE]
            text = " ".join(batch)
            if note and i == 0:
                text = f"{note}\n{text}"
            await context.bot.send_message(chat.id, text, parse_mode=ParseMode.HTML)
            await asyncio.sleep(1.0)
        print(f"[+] /tagall successfully sent {len(mentions)} tags in chat {chat.id}")
    except Exception as e:
        print(f"[-] /tagall crashed: {e}")
