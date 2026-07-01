"""
helpers.py — small shared utilities used across command modules.
"""

from telegram import Update, ChatMember
from telegram.ext import ContextTypes


async def is_admin(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    member = await chat.get_member(user.id)
    return member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER)


async def require_admin(update: Update) -> bool:
    """Returns False if the caller isn't an admin (silently ignores them)."""
    if not await is_admin(update):
        return False
    return True


async def require_group(update: Update) -> bool:
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("This only works in groups.")
        return False
    return True


async def resolve_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Figures out who a moderation command (e.g. /warn) is targeting.
    Supports either replying to the person's message, or /warn @username.
    Returns (user_id, display_name) or (None, None) if it can't be resolved.
    """
    msg = update.effective_message

    if msg.reply_to_message:
        u = msg.reply_to_message.from_user
        return u.id, (u.username or u.first_name)

    if context.args:
        username = context.args[0].lstrip("@")
        # Bots can't look up arbitrary users by username without them being
        # known already, so we check our own member table first.
        from db import get_members
        for m in get_members(update.effective_chat.id):
            if m["username"] and m["username"].lower() == username.lower():
                return m["user_id"], m["username"]

    return None, None


def fmt_duration(seconds: int) -> str:
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h"


# ---------- subscriptions & billing ----------
import time
from telegram import LabeledPrice
from db import is_subscribed

OWNER_ID = 6221448885


async def send_subscription_invoice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return
    
    # Cooldown check: limit invoices to once per 60 seconds per group chat
    last_sent = context.chat_data.get("last_invoice_sent", 0) if context.chat_data else 0
    if time.time() - last_sent < 60:
        return
    if context.chat_data is not None:
        context.chat_data["last_invoice_sent"] = time.time()

    try:
        await context.bot.send_invoice(
            chat_id=chat.id,
            title="Study Group Bot Subscription",
            description="Unlock all features (tagall, stats, reminders, rules, and moderation) for 30 days.",
            payload=f"sub_{chat.id}",
            provider_token="",  # Empty for Telegram Stars
            currency="XTR",
            prices=[LabeledPrice("30-Day Access", 2500)]  # 2,500 Telegram Stars
        )
    except Exception as e:
        # Fallback if bot cannot send invoice (e.g. not admin, or api error)
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"⚠️ This group requires an active subscription. However, I could not send the invoice: {e}\n"
                 f"Please contact the bot owner (@Pa_zima) to activate this group."
        )


def require_subscription(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        chat = update.effective_chat
        
        # Subscriptions only apply in groups. DMs/Private chats are bypassed.
        if not chat or chat.type not in ("group", "supergroup"):
            return await func(update, context, *args, **kwargs)
            
        # Check if chat is subscribed (exempt the current group ID)
        if chat.id == -1002637286707:
            return await func(update, context, *args, **kwargs)

        if not is_subscribed(chat.id):
            print(f"[-] Command blocked: Chat {chat.id} is not subscribed. Sending invoice...")
            await send_subscription_invoice(update, context)
            return
            
        return await func(update, context, *args, **kwargs)
    return wrapper
