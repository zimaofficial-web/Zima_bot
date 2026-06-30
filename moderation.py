"""
moderation.py — handles /mute, /unmute, /kick, and automatic link checking.
"""

import time
import logging
from telegram import Update, ChatPermissions, ChatMember
from telegram.ext import ContextTypes

from helpers import require_admin, require_group, resolve_target_user, is_admin, require_subscription

logger = logging.getLogger(__name__)


async def check_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scans group messages for links. If found and sender is not admin, deletes message."""
    msg = update.effective_message
    if not msg or msg.chat.type not in ("group", "supergroup"):
        return

    # Check for URL entities in text or caption
    entities = msg.entities or []
    if msg.caption_entities:
        entities = list(entities) + list(msg.caption_entities)

    has_link = False
    for entity in entities:
        if entity.type in ("url", "text_link"):
            has_link = True
            break

    if has_link:
        # Check if the user is an admin
        if not await is_admin(update):
            try:
                await msg.delete()
                logger.info(f"Deleted link message from user {msg.from_user.id} in chat {msg.chat_id}")
            except Exception as e:
                logger.error(f"Failed to delete link message: {e}")


@require_subscription
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mutes a member for a specified number of minutes (default 60)."""
    if not await require_group(update) or not await require_admin(update):
        return

    target_id, target_name = await resolve_target_user(update, context)
    if not target_id:
        await update.message.reply_text(
            "Could not resolve user. Reply to their message or use /mute @username [minutes]."
        )
        return

    # Default duration: 60 minutes
    minutes = 60
    args = context.args
    msg = update.effective_message

    if msg.reply_to_message:
        if args and args[0].isdigit():
            minutes = int(args[0])
    else:
        if len(args) > 1 and args[1].isdigit():
            minutes = int(args[1])

    # Check if target is an admin
    chat = update.effective_chat
    try:
        member = await chat.get_member(target_id)
        if member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            await update.message.reply_text("Cannot mute an administrator.")
            return

        permissions = ChatPermissions(can_send_messages=False)
        until = int(time.time()) + (minutes * 60)
        
        await context.bot.restrict_chat_member(
            chat_id=chat.id,
            user_id=target_id,
            permissions=permissions,
            until_date=until
        )
        await update.message.reply_text(f"🔇 Muted {target_name} for {minutes} minutes.")
    except Exception as e:
        await update.message.reply_text(f"Failed to mute user: {e}")


@require_subscription
async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lifts mute restrictions on a user."""
    if not await require_group(update) or not await require_admin(update):
        return

    target_id, target_name = await resolve_target_user(update, context)
    if not target_id:
        await update.message.reply_text(
            "Could not resolve user. Reply to their message or use /unmute @username."
        )
        return

    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_audios=True,
            can_send_documents=True,
            can_send_photos=True,
            can_send_videos=True,
            can_send_video_notes=True,
            can_send_voice_notes=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True
        )
        await context.bot.restrict_chat_member(
            chat_id=update.effective_chat.id,
            user_id=target_id,
            permissions=permissions
        )
        await update.message.reply_text(f"🔊 Unmuted {target_name}.")
    except Exception as e:
        await update.message.reply_text(f"Failed to unmute user: {e}")


@require_subscription
async def kick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kicks a member from the group (allows rejoining via invite link)."""
    if not await require_group(update) or not await require_admin(update):
        return

    target_id, target_name = await resolve_target_user(update, context)
    if not target_id:
        await update.message.reply_text(
            "Could not resolve user. Reply to their message or use /kick @username."
        )
        return

    chat = update.effective_chat
    try:
        member = await chat.get_member(target_id)
        if member.status in (ChatMember.ADMINISTRATOR, ChatMember.OWNER):
            await update.message.reply_text("Cannot kick an administrator.")
            return

        # Ban the user
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_id)
        # Immediately unban so they can rejoin via invite link
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target_id)
        await update.message.reply_text(f"👢 Kicked {target_name} from the group.")
    except Exception as e:
        await update.message.reply_text(f"Failed to kick user: {e}")
