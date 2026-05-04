#!/usr/bin/env python3
"""KNEO Community Bot – kneo-community.com"""

import logging, re, time, json
from pathlib import Path
from datetime import datetime, timedelta

from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
    ContextTypes,
)

BOT_TOKEN = "8502930539:AAFP6JRzXjRzJEF2MzHurwTxwSYw4Fn7goI"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BANNED_WORDS = ["aptal","salak","gerizekalı","mal","idiot","stupid","fuck","shit","spam","reklam"]

DATA_FILE = Path("kneo_data.json")

def load_data():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {"warnings": {}, "last_seen": {}, "members": {}}

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2))

data = load_data()

def is_spam(text):
    t = text.lower()
    return any(w in t for w in BANNED_WORDS)

async def is_admin(update, ctx):
    try:
        m = await update.effective_chat.get_member(update.effective_user.id)
        return m.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return False

def add_warn(chat_id, user_id):
    ck, uk = str(chat_id), str(user_id)
    data["warnings"].setdefault(ck, {})
    data["warnings"][ck][uk] = data["warnings"][ck].get(uk, 0) + 1
    save_data(data)
    return data["warnings"][ck][uk]

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *KNEO Bot* aktif!\n\n"
        "🚫 Küfür & spam engeli\n"
        "👋 Yeni üye karşılama\n"
        "⚠️ Uyarı sistemi\n\n"
        "🌐 kneo-community.com",
        parse_mode="Markdown"
    )

async def cmd_kurallar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *KNEO Grup Kuralları*\n\n"
        "1️⃣ Saygılı olun\n"
        "2️⃣ Küfür yasak\n"
        "3️⃣ Reklam & spam yasak\n"
        "4️⃣ Uygunsuz görsel yasak\n\n"
        "⚠️ 3 uyarı = 24 saat ban\n"
        "⚠️ 5 uyarı = kalıcı ban\n\n"
        "🌐 kneo-community.com",
        parse_mode="Markdown"
    )

async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message:
        await update.message.reply_text("Uyarmak için bir mesajı yanıtla.")
        return
    target = update.message.reply_to_message.from_user
    count = add_warn(update.effective_chat.id, target.id)
    await do_warning(ctx, update.effective_chat, target, count, "Manuel uyarı")

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    await update.effective_chat.ban_member(target.id)
    await update.message.reply_text(f"🔨 {target.full_name} banlandı.")

async def on_member_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if result.new_chat_member.status != "member": return
    user = result.new_chat_member.user
    try:
        await ctx.bot.send_message(
            result.chat.id,
            f"👋 *Hoş geldin, {user.first_name}!*\n\n"
            f"*{result.chat.title}* grubuna katıldın 🎉\n\n"
            f"📋 /kurallar\n"
            f"🌐 kneo-community.com",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Hoşgeldin hatası: {e}")

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user: return
    if await is_admin(update, ctx): return
    text = msg.text or msg.caption or ""
    if text and is_spam(text):
        try: await msg.delete()
        except: pass
        count = add_warn(update.effective_chat.id, msg.from_user.id)
        await do_warning(ctx, update.effective_chat, msg.from_user, count, "küfür/spam")

async def do_warning(ctx, chat, user, count, reason):
    try:
        if count >= 5:
            await chat.ban_member(user.id)
            await ctx.bot.send_message(chat.id,
                f"🔨 *{user.full_name}* kalıcı banlandı.\n_{reason}_",
                parse_mode="Markdown")
        elif count >= 3:
            await chat.ban_member(user.id, until_date=datetime.now()+timedelta(hours=24))
            await ctx.bot.send_message(chat.id,
                f"⏱️ *{user.full_name}* 24 saat kısıtlandı.\n_{reason}_",
                parse_mode="Markdown")
        else:
            await ctx.bot.send_message(chat.id,
                f"⚠️ *{user.first_name}*, bu davranış yasak!\n"
                f"_Sebep: {reason}_\nUyarı: *{count}/5*",
                parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Uyarı hatası: {e}")

def main():
    logger.info("🚀 KNEO Bot başlatılıyor...")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kurallar", cmd_kurallar))
    app.add_handler(CommandHandler("rules", cmd_kurallar))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.ALL, on_message))
    app.add_handler(ChatMemberHandler(on_member_join, ChatMemberHandler.CHAT_MEMBER))
    logger.info("✅ KNEO Bot aktif!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
