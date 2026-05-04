#!/usr/bin/env python3
"""KNEO Community Bot – kneo-community.com"""

import logging, re, time, json
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, ChatMember
from telegram.ext import Application, CommandHandler, MessageHandler, ChatMemberHandler, filters, ContextTypes

BOT_TOKEN = "8502930539:AAFP6JRzXjRzJEF2MzHurwTxwSYw4Fn7goI"

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

BANNED_WORDS = ["aptal","salak","gerizekalı","mal","idiot","stupid","fuck","shit","spam","reklam"]
SPAM_PATTERNS = [r"(bit\.ly|tinyurl)", r"(.)\1{7,}"]

DATA_FILE = Path("kneo_data.json")

def load_data():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {"warnings": {}, "last_seen": {}, "members": {}}

def save_data(d): DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2))

data = load_data()

def is_spam(text):
    t = text.lower()
    for w in BANNED_WORDS:
        if w in t: return True
    for p in SPAM_PATTERNS:
        if re.search(p, text, re.IGNORECASE): return True
    return False

async def is_admin(update, ctx):
    try:
        m = await update.effective_chat.get_member(update.effective_user.id)
        return m.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except: return False

def get_warn(chat_id, user_id): return data["warnings"].get(str(chat_id), {}).get(str(user_id), 0)

def add_warn(chat_id, user_id):
    ck, uk = str(chat_id), str(user_id)
    data["warnings"].setdefault(ck, {})
    data["warnings"][ck][uk] = data["warnings"][ck].get(uk, 0) + 1
    save_data(data)
    return data["warnings"][ck][uk]

def update_seen(chat_id, user_id, name):
    ck, uk = str(chat_id), str(user_id)
    data["last_seen"].setdefault(ck, {})[uk] = time.time()
    data["members"].setdefault(ck, {})[uk] = name
    save_data(data)

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *KNEO Bot* aktif!\n\n🚫 Küfür & spam engeli\n👋 Yeni üye karşılama\n⚠️ Uyarı sistemi\n\n🌐 kneo-community.com",
        parse_mode="Markdown")

async def cmd_kurallar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *KNEO Grup Kuralları*\n\n1️⃣ Saygılı olun\n2️⃣ Küfür yasak\n3️⃣ Reklam & spam yasak\n4️⃣ Uygunsuz görsel yasak\n\n⚠️ 3 uyarı = 24 saat ban\n⚠️ 5 uyarı = kalıcı ban",
        parse_mode="Markdown")

async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message:
        await update.message.reply_text("Uyarmak için bir mesajı yanıtla."); return
    target = update.message.reply_to_message.from_user
    count = add_warn(update.effective_chat.id, target.id)
    await handle_warning(update, ctx, target, count, "Manuel uyarı")

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
    update_seen(result.chat.id, user.id, user.full_name)
    try:
        await ctx.bot.send_message(result.chat.id,
            f"👋 *Hoş geldin, {user.first_name}!*\n\n*{result.chat.title}* grubuna katıldın! 🎉\n\n📋 /kurallar\n🌐 kneo-community.com",
            parse_mode="Markdown")
    except Exception as e: logger.error(f"Hoşgeldin hatası: {e}")

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user: return
    user = msg.from_user
    chat = update.effective_chat
    update_seen(chat.id, user.id, user.full_name)
    if await is_admin(update, ctx): return
    text = msg.text or msg.caption or ""
    if text and is_spam(text):
        try: await msg.delete()
        except: pass
        count = add_warn(chat.id, user.id)
        await handle_warning(update, ctx, user, count, "küfür/spam")

async def handle_warning(update, ctx, user, count, reason):
    chat = update.effective_chat
    if count >= 5:
        try:
            await chat.ban_member(user.id)
            await ctx.bot.send_message(chat.id, f"🔨 *{user.full_name}* kalıcı banlandı. _{reason}_", parse_mode="Markdown")
        except Exception as e: logger.error(e)
    elif count >= 3:
        try:
            await chat.ban_member(user.id, until_date=datetime.now()+timedelta(hours=24))
            await ctx.bot.send_message(chat.id, f"⏱️ *{user.full_name}* 24 saat kısıtlandı. _{reason}_", parse_mode="Markdown")
        except Exception as e: logger.error(e)
    else:
        try:
            await ctx.bot.send_message(chat.id, f"⚠️ *{user.first_name}*, bu davranış yasak!\n_Sebep: {reason}_\nUyarı: *{count}/5*", parse_mode="Markdown")
        except Exception as e: logger.error(e)

def main():
    logger.info("🚀 KNEO Bot başlatılıyor...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("kurallar", cmd_kurallar))
    app.add_handler(CommandHandler("rules", cmd_kurallar))
    app.add_handler(CommandHandler("warn", cmd_warn))
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, on_message))
    app.add_handler(ChatMemberHandler(on_member_join, ChatMemberHandler.CHAT_MEMBER))
    logger.info("✅ KNEO Bot aktif!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
