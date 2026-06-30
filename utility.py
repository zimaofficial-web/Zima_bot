"""
utility.py — /rules, /setrules, /poll, /remind

Reminders use python-telegram-bot's built-in JobQueue, so they fire even
if no one sends a message in between — the bot just needs to stay running.
"""

import re
from telegram import Update
from telegram.ext import ContextTypes

from helpers import require_admin, require_group, require_subscription
import db


@require_subscription
async def set_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group(update) or not await require_admin(update):
        return

    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Usage: /setrules <the rules text>")
        return

    db.set_rules(update.effective_chat.id, text)
    await update.message.reply_text("Rules saved. Members can view them with /rules.")


@require_subscription
async def rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_group(update):
        return

    text = db.get_rules(update.effective_chat.id)
    if not text:
        await update.message.reply_text("No rules have been set yet. An admin can set them with /setrules.")
        return

    await update.message.reply_text(f"Group rules:\n\n{text}")


@require_subscription
async def poll(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /poll Question? | Option 1 | Option 2 | Option 3
    """
    if not await require_group(update):
        return

    raw = " ".join(context.args)
    parts = [p.strip() for p in raw.split("|") if p.strip()]

    if len(parts) < 3:
        await update.message.reply_text(
            "Usage: /poll Question? | Option 1 | Option 2 | ...\n"
            "Need a question and at least 2 options."
        )
        return

    question, options = parts[0], parts[1:]
    await context.bot.send_poll(
        update.effective_chat.id,
        question=question,
        options=options,
        is_anonymous=False,
    )


def _parse_duration(text: str):
    """Parses '30m', '2h', '1d' into seconds. Returns None if invalid."""
    match = re.match(r"^(\d+)([mhd])$", text.strip().lower())
    if not match:
        return None
    value, unit = int(match.group(1)), match.group(2)
    multiplier = {"m": 60, "h": 3600, "d": 86400}[unit]
    return value * multiplier


async def _send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(job.chat_id, f"⏰ Reminder: {job.data}")


@require_subscription
async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Usage: /remind 30m Submit the assignment
           /remind 2h Study session starting
           /remind 1d Exam tomorrow
    """
    if not await require_group(update) or not await require_admin(update):
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /remind <time> <message>\n"
            "Examples: /remind 30m Submit the assignment | /remind 2h Study session | /remind 1d Exam tomorrow"
        )
        return

    seconds = _parse_duration(context.args[0])
    if seconds is None:
        await update.message.reply_text("Time format should be like 30m, 2h, or 1d.")
        return

    message = " ".join(context.args[1:])
    context.job_queue.run_once(
        _send_reminder,
        when=seconds,
        chat_id=update.effective_chat.id,
        data=message,
    )
    await update.message.reply_text(f"Reminder set for {context.args[0]} from now: \"{message}\"")
