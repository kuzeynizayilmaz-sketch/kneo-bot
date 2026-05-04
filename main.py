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

BOT_TOKEN = "8502930539:AAF_jpNsVR4Xhsq2d3uTRtRHntdmMGe2Mbw"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BANNED_WORDS = [
    # Türkçe küfürler
    "aptal", "salak", "gerizekalı", "gerize kalı", "mal", "orospu", "orospu çocuğu",
    "oç", "piç", "piç kurusu", "amk", "amına", "amına koyayım", "siktir",
    "siktirgit", "götü", "ibne", "oğlum", "sürtük", "fahişe", "kaltak",
    "kahpe", "s.k", "a.q", "o.ç", "p.ç", "s.ktir", "göt", "bok",
    "boktan", "yarrak", "yarak", "orospu", "kancık", "şerefsiz", "alçak",
    "haysiyetsiz", "namussuz", "adi", "aşağılık", "it", "köpek", "eşek",
    "eşşek", "serseri", "katil", "beyinsiz", "dangalak", "dingil",
    "geri zekalı", "gerzek", "hıyar", "götveren", "orosbuçocuğu",
    # Almanca Schimpfwörter
    "scheiße", "scheisse", "scheiß", "arschloch", "arsch", "wichser",
    "hurensohn", "hure", "idiot", "vollidiot", "depp", "trottel",
    "blödmann", "blöd", "fick", "ficken", "verdammt", "mist",
    "dummkopf", "spinner", "schwachkopf", "wichse", "schlampe",
    "fotze", "penner", "bastard", "dreckig", "dreckskerl",
    # İngilizce
    "fuck", "fucking", "fucker", "shit", "bullshit", "bitch",
    "asshole", "ass", "bastard", "damn", "cunt", "dick", "cock",
    "pussy", "whore", "slut", "idiot", "moron", "stupid", "retard",
    # Spam
    "spam", "reklam", "kazan", "para kazan", "ücretsiz kazan",
    "bitcoin", "kripto kazan", "bedava para",
]

DATA_FILE = Path("kneo_data.json")

def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except:
            pass
    return {"warnings": {}, "members": {}}

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2))

data = load_data()

def is_bad(text: str) -> bool:
    # Normalize text - remove spaces between letters for evasion attempts
    t = text.lower()
    t_nospace = t.replace(" ", "").replace(".", "").replace("*", "").replace("_", "")
    for w in BANNED_WORDS:
        w_clean = w.replace(" ", "")
        if w_clean in t_nospace:
            return True
        if w in t:
            return True
    return False

async def check_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        m = await update.effective_chat.get_member(update.effective_user.id)
        return m.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except:
        return False

def add_warn(chat_id: int, user_id: int) -> int:
    ck, uk = str(chat_id), str(user_id)
    data["warnings"] = data.get("warnings", {})
    data["warnings"].setdefault(ck, {})
    data["warnings"][ck][uk] = data["warnings"][ck].get(uk, 0) + 1
    save_data(data)
    return data["warnings"][ck][uk]

# ── Commands ──────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *KNEO Bot* aktif!\n\n"
        "🚫 Küfür & spam engeli\n"
        "👋 Yeni üye karşılama\n"
        "⚠️ Uyarı sistemi\n\n"
        "🌐 kneo-community.com",
        parse_mode="Markdown"
    )
    logger.info("Start command received")

async def cmd_kurallar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *KNEO Grup Kuralları*\n\n"
        "1️⃣ Saygılı olun\n"
        "2️⃣ Küfür yasak\n"
        "3️⃣ Reklam & spam yasak\n"
        "4️⃣ Uygunsuz görsel yasak\n\n"
        "⚠️ 3 uyarı → 24 saat ban\n"
        "⚠️ 5 uyarı → kalıcı ban",
        parse_mode="Markdown"
    )

async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Uyarmak için bir mesajı yanıtla.")
        return
    target = update.message.reply_to_message.from_user
    count = add_warn(update.effective_chat.id, target.id)
    await send_warning(ctx, update.effective_chat, target, count, "Admin uyarısı")

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await check_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        return
    target = update.message.reply_to_message.from_user
    await update.effective_chat.ban_member(target.id)
    await update.message.reply_text(f"🔨 {target.full_name} banlandı.")

# ── New member ────────────────────────────────────────

async def on_member_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    new_member = result.new_chat_member
    if new_member.status != "member":
        return
    user = new_member.user
    try:
        await ctx.bot.send_message(
            result.chat.id,
            f"👋 *Hoş geldin, {user.first_name}!*\n\n"
            f"*{result.chat.title}* grubuna katıldın 🎉\n\n"
            f"📋 /kurallar  |  🌐 kneo-community.com",
            parse_mode="Markdown"
        )
        logger.info(f"Welcomed {user.full_name}")
    except Exception as e:
        logger.error(f"Welcome error: {e}")

# ── Message filter ────────────────────────────────────

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user:
        return
    if await check_admin(update, ctx):
        return
    text = msg.text or msg.caption or ""
    if text and is_bad(text):
        try:
            await msg.delete()
            logger.info(f"Deleted bad message from {msg.from_user.full_name}")
        except Exception as e:
            logger.error(f"Delete error: {e}")
        count = add_warn(update.effective_chat.id, msg.from_user.id)
        await send_warning(ctx, update.effective_chat, msg.from_user, count, "küfür/spam")

async def send_warning(ctx, chat, user, count: int, reason: str):
    try:
        if count >= 5:
            await chat.ban_member(user.id)
            await ctx.bot.send_message(
                chat.id,
                f"🔨 *{user.full_name}* kalıcı banlandı.\n_{reason}_",
                parse_mode="Markdown"
            )
        elif count >= 3:
            until = datetime.now() + timedelta(hours=24)
            await chat.ban_member(user.id, until_date=until)
            await ctx.bot.send_message(
                chat.id,
                f"⏱️ *{user.full_name}* 24 saat kısıtlandı.\n_{reason}_",
                parse_mode="Markdown"
            )
        else:
            await ctx.bot.send_message(
                chat.id,
                f"⚠️ *{user.first_name}*, bu davranış yasak!\n"
                f"_Sebep: {reason}_ – Uyarı *{count}/5*",
                parse_mode="Markdown"
            )
    except Exception as e:
        logger.error(f"Warning error: {e}")

# ── Main ──────────────────────────────────────────────

def main():
    logger.info("🚀 KNEO Bot başlatılıyor...")

    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("kurallar", cmd_kurallar))
    application.add_handler(CommandHandler("rules", cmd_kurallar))
    application.add_handler(CommandHandler("warn", cmd_warn))
    application.add_handler(CommandHandler("ban", cmd_ban))
    application.add_handler(
        MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.ALL, on_message)
    )
    application.add_handler(
        ChatMemberHandler(on_member_join, ChatMemberHandler.CHAT_MEMBER)
    )

    logger.info("✅ KNEO Bot aktif! Polling başlatılıyor...")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == "__main__":
    main()
