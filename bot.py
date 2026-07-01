"""
bot.py — entrypoint. Wires all the command modules together.

Setup:
1. pip install -r requirements.txt
2. Get a bot token from @BotFather
3. export TELEGRAM_BOT_TOKEN="your:token" (or edit BOT_TOKEN below)
4. In @BotFather: Bot Settings > Group Privacy > Turn OFF
   (otherwise the bot can't see regular messages, only commands)
5. Add the bot to your group and make it an ADMIN
   (needed for mute/kick to work, and for /tagall to function properly)
6. python3 bot.py

Commands:
  Info:
    /stats        - member counts (known vs active)
    /active       - who's talked in the last 7 days
    /tagall       - tag everyone known [admin only]

  Utility:
    /rules        - show the saved rules
    /setrules     - set the rules text [admin only]
    /poll         - Question | Opt1 | Opt2 | ...
    /remind       - /remind 30m Submit the assignment [admin only]

  Moderation [admin only]:
    /mute         - reply or /mute @user [minutes], default 60
    /unmute       - lift a mute
    /kick         - remove someone from the group
"""

import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, PreCheckoutQueryHandler

import db
import info
import utility
import moderation
import ai_chat

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def track_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs on every non-command group message. Builds the member list passively."""
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user or msg.chat.type not in ("group", "supergroup"):
        return
    db.save_member(msg.chat.id, user.id, user.username, user.first_name or "there")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Study group bot is online.\n\n"
        "Info: /stats /active /tagall\n"
        "Utility: /rules /setrules /poll /remind\n"
        "Moderation (admin): /mute /unmute /kick\n\n"
        "Send /help anytime to see this again."
    )


async def precheckout_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    if query.invoice_payload.startswith("sub_"):
        await query.answer(ok=True)
    else:
        await query.answer(ok=False, error_message="Invalid subscription payload.")


async def successful_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    payment = msg.successful_payment
    payload = payment.invoice_payload
    
    if payload.startswith("sub_"):
        try:
            chat_id = int(payload.split("_")[1])
            db.add_subscription(chat_id, 30)
            await msg.reply_text(
                f"🎉 Payment of {payment.total_amount} {payment.currency} successful! "
                f"This group now has an active subscription for 30 days."
            )
        except Exception as e:
            logger.error(f"Error handling successful payment: {e}")
            await msg.reply_text("An error occurred while activating your subscription. Please contact the owner.")


async def auth_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from helpers import OWNER_ID
    user = update.effective_user
    if not user or user.id != OWNER_ID:
        await update.message.reply_text("This command is owner-only.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /authgroup <chat_id> [days]")
        return

    try:
        chat_id = int(args[0])
        days = int(args[1]) if len(args) > 1 else 30
        db.add_subscription(chat_id, days)
        await update.message.reply_text(f"Successfully authorized chat {chat_id} for {days} days.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")


async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    await update.message.reply_text(f"The ID of this chat is: {chat.id}")


def main():
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        raise SystemExit("Set your bot token: edit BOT_TOKEN in bot.py or export TELEGRAM_BOT_TOKEN=xxxx")

    db.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("authgroup", auth_group))
    app.add_handler(CommandHandler("id", get_id))

    # payments
    app.add_handler(PreCheckoutQueryHandler(precheckout_callback))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment_callback))

    # info
    app.add_handler(CommandHandler("stats", info.stats))
    app.add_handler(CommandHandler("active", info.active))
    app.add_handler(CommandHandler("tagall", info.tagall))
    app.add_handler(MessageHandler((filters.TEXT | filters.CAPTION) & filters.ChatType.GROUPS & filters.Regex(r'(?i)\b@all\b'), info.tagall))

    # utility
    app.add_handler(CommandHandler("rules", utility.rules))
    app.add_handler(CommandHandler("setrules", utility.set_rules))
    app.add_handler(CommandHandler("poll", utility.poll))
    app.add_handler(CommandHandler("remind", utility.remind))

    # moderation
    app.add_handler(CommandHandler("mute", moderation.mute))
    app.add_handler(CommandHandler("unmute", moderation.unmute))
    app.add_handler(CommandHandler("kick", moderation.kick))

    # passive tracking and link checking
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, moderation.check_links), group=0)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.COMMAND, track_member), group=1)

    # AI direct messages
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, ai_chat.handle_dm))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
