#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║         KNEO TELEGRAM COMMUNITY BOT                 ║
║  Moderasyon · Hoşgeldin · Pasif Üye · Uyarı Sistemi  ║
╚══════════════════════════════════════════════════════╝

Kurulum:
    pip install python-telegram-bot schedule pillow requests aiohttp

Kullanım:
    BOT_TOKEN=xxxx python kneo_bot.py
"""

import os
import re
import json
import time
import logging
import asyncio
import schedule
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from telegram import Update, ChatMember, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
    ContextTypes,
)

# ─────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────
BOT_TOKEN = "8502930539:AAFP6JRzXjRzJEF2MzHurwTxwSYw4Fn7goI"  # ← Token von @BotFather
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "0"))  # Admin log kanalı ID'si

DATA_FILE = Path("kneo_data.json")

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────
# KÜFÜR / SPAM KELİME LİSTESİ  (Türkçe örnek)
# ─────────────────────────────────────────────────
BANNED_WORDS: list[str] = [
    # Buraya küfür kelimelerini ekleyin
    "aptal", "salak", "gerizekalı", "mal", "s.k", "o.pu",
    # İngilizce
    "idiot", "stupid", "fuck", "shit",
    # Arapça
    "khawal", "ibn",
]

# Spam pattern'leri
SPAM_PATTERNS = [
    r"(bit\.ly|tinyurl|t\.me\/joinchat\/(?!kneo))",  # İzinsiz invite
    r"(\+?\d[\d\s\-]{8,}\d)",                          # Telefon numarası
    r"(https?://(?!t\.me/kneo)[^\s]+\.(casino|bet|porn|xxx))",
    r"(.)\1{6,}",                                       # Tekrar eden karakterler
]

# ─────────────────────────────────────────────────
# VERİ YÖNETİMİ
# ─────────────────────────────────────────────────
def load_data() -> dict:
    """JSON dosyasından veri yükle"""
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "warnings": {},       # {chat_id: {user_id: count}}
        "bans": {},           # {chat_id: [user_id]}
        "last_seen": {},      # {chat_id: {user_id: timestamp}}
        "members": {},        # {chat_id: {user_id: name}}
        "stats": {
            "deleted_messages": 0,
            "warnings_given": 0,
            "temp_bans": 0,
            "perm_bans": 0,
            "welcomed": 0,
        }
    }

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()

# ─────────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────────
def get_chat_key(chat_id: int) -> str:
    return str(chat_id)

def get_user_key(user_id: int) -> str:
    return str(user_id)

def get_warning_count(chat_id: int, user_id: int) -> int:
    return data["warnings"].get(get_chat_key(chat_id), {}).get(get_user_key(user_id), 0)

def add_warning(chat_id: int, user_id: int) -> int:
    ck, uk = get_chat_key(chat_id), get_user_key(user_id)
    data["warnings"].setdefault(ck, {})
    data["warnings"][ck][uk] = data["warnings"][ck].get(uk, 0) + 1
    data["stats"]["warnings_given"] += 1
    save_data(data)
    return data["warnings"][ck][uk]

def reset_warnings(chat_id: int, user_id: int) -> None:
    ck, uk = get_chat_key(chat_id), get_user_key(user_id)
    if ck in data["warnings"] and uk in data["warnings"][ck]:
        del data["warnings"][ck][uk]
    save_data(data)

def update_last_seen(chat_id: int, user_id: int, name: str) -> None:
    ck, uk = get_chat_key(chat_id), get_user_key(user_id)
    data["last_seen"].setdefault(ck, {})[uk] = time.time()
    data["members"].setdefault(ck, {})[uk] = name
    save_data(data)

def is_spam(text: str) -> bool:
    for word in BANNED_WORDS:
        if word.lower() in text.lower():
            return True
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

async def send_log(context: ContextTypes.DEFAULT_TYPE, msg: str) -> None:
    """Admin log kanalına mesaj gönder"""
    logger.info(msg)
    if LOG_CHAT_ID:
        try:
            await context.bot.send_message(LOG_CHAT_ID, f"📋 `{msg}`", parse_mode="Markdown")
        except Exception:
            pass

# ─────────────────────────────────────────────────
# KOMUTLAR
# ─────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot başlatıldığında bilgi mesajı"""
    await update.message.reply_text(
        "👋 *KNEO Bot* aktif!\n\n"
        "Ben bu grubu 7/24 denetliyorum:\n"
        "🚫 Küfür & spam engeli\n"
        "🖼️ Uygunsuz görsel kontrolü\n"
        "👋 Yeni üye karşılama\n"
        "⏰ Pasif üye aktivasyonu\n\n"
        "Sorun? @admin'e yazın.",
        parse_mode="Markdown"
    )

async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Bot istatistiklerini göster (sadece adminler)"""
    if not await is_admin(update, ctx):
        return
    s = data["stats"]
    await update.message.reply_text(
        f"📊 *KNEO Bot İstatistikleri*\n\n"
        f"🗑️ Silinen mesaj: *{s['deleted_messages']}*\n"
        f"⚠️ Verilen uyarı: *{s['warnings_given']}*\n"
        f"⏱️ Geçici ban: *{s['temp_bans']}*\n"
        f"🔨 Kalıcı ban: *{s['perm_bans']}*\n"
        f"👋 Karşılanan üye: *{s['welcomed']}*",
        parse_mode="Markdown"
    )

async def cmd_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Manuel uyarı ver (admin komutu): /warn @kullanici sebep"""
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Uyarmak istediğin mesajı yanıtla: /warn")
        return
    target = update.message.reply_to_message.from_user
    count = add_warning(update.effective_chat.id, target.id)
    await handle_warning(update, ctx, target, count, "Manuel uyarı")

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Kullanıcı banla (admin): /ban"""
    if not await is_admin(update, ctx):
        return
    if not update.message.reply_to_message:
        await update.message.reply_text("Ban uygulamak için mesajı yanıtla: /ban")
        return
    target = update.message.reply_to_message.from_user
    await update.effective_chat.ban_member(target.id)
    await update.message.reply_text(
        f"🔨 {target.full_name} gruptan çıkarıldı.\n_(Admin kararı)_",
        parse_mode="Markdown"
    )
    data["stats"]["perm_bans"] += 1
    save_data(data)
    await send_log(ctx, f"BAN | {target.full_name} | {update.effective_chat.title}")

async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Uyarıları sıfırla (admin): /reset"""
    if not await is_admin(update, ctx):
        return
    if update.message.reply_to_message:
        target = update.message.reply_to_message.from_user
        reset_warnings(update.effective_chat.id, target.id)
        await update.message.reply_text(f"✅ {target.full_name} uyarıları sıfırlandı.")

async def cmd_rules(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Grup kurallarını göster"""
    await update.message.reply_text(
        "📋 *KNEO Grup Kuralları*\n\n"
        "1️⃣ Saygılı ve nazik olun\n"
        "2️⃣ Küfür, hakaret yasak\n"
        "3️⃣ Reklam ve spam yasak\n"
        "4️⃣ Uygunsuz görsel paylaşmak yasak\n"
        "5️⃣ Grup konusuna uygun paylaşım yapın\n"
        "6️⃣ Kişisel bilgi (telefon, adres) paylaşmayın\n\n"
        "⚠️ 3 uyarı = 24 saat ban\n"
        "⚠️ 5 uyarı = kalıcı ban\n\n"
        "📞 Sorun: @kneo_admin",
        parse_mode="Markdown"
    )

# ─────────────────────────────────────────────────
# YENİ ÜYE KARŞILAMA
# ─────────────────────────────────────────────────
async def on_member_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Yeni üye gruba katıldığında karşıla"""
    result = update.chat_member
    if result.new_chat_member.status not in [ChatMember.MEMBER, "member"]:
        return

    new_user = result.new_chat_member.user
    chat = result.chat

    # Üyeyi kaydet
    update_last_seen(chat.id, new_user.id, new_user.full_name)

    # Grup adından kategori ve şehir çıkar
    group_parts = chat.title.split() if chat.title else [""]
    city = group_parts[0] if group_parts else "Şehrinizdeki"

    welcome_msg = (
        f"👋 *Hoş geldin, {new_user.full_name}!*\n\n"
        f"*{chat.title}* grubuna katıldın! 🎉\n\n"
        f"📋 /kurallar – Grup kuralları\n"
        f"📍 Şehir: *{city}*\n"
        f"🤖 Bu grup KNEO Bot tarafından denetlenmektedir.\n\n"
        f"Kendini tanıtabilirsin – seni bekliyoruz! 😊"
    )

    try:
        await ctx.bot.send_message(
            chat.id, welcome_msg, parse_mode="Markdown"
        )
        data["stats"]["welcomed"] += 1
        save_data(data)
        await send_log(ctx, f"WELCOME | {new_user.full_name} | {chat.title}")
    except Exception as e:
        logger.error(f"Karşılama hatası: {e}")

# ─────────────────────────────────────────────────
# MESAJ DENETİMİ
# ─────────────────────────────────────────────────
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Her mesajı denetle"""
    msg: Message = update.message
    if not msg or not msg.from_user:
        return

    user = msg.from_user
    chat = update.effective_chat

    # Son görülme güncelle
    update_last_seen(chat.id, user.id, user.full_name)

    # Admin mesajlarını atla
    if await is_admin(update, ctx):
        return

    text = msg.text or msg.caption or ""

    # ── Metin & link kontrolü ──
    if text and is_spam(text):
        await delete_and_warn(update, ctx, user, "küfür/spam içeriği")
        return

    # ── Fotoğraf kontrolü (basit boyut kontrolü) ──
    if msg.photo:
        # Gerçek uygulamada burada bir görüntü AI API'si çağrılır
        # Örnek: Google Vision SafeSearch, Azure Content Moderator vb.
        photo_ok = await check_photo_safe(msg.photo[-1], ctx)
        if not photo_ok:
            await delete_and_warn(update, ctx, user, "uygunsuz görsel")
            return

    # ── Sticker / GIF kontrolü (opsiyonel) ──
    # if msg.sticker and msg.sticker.is_animated:
    #     pass

async def check_photo_safe(photo, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Gerçek uygulamada Google Vision veya Azure Content Moderator API'si.
    Şu an her fotoğrafı güvenli kabul eder – API key ile değiştirilmeli.
    """
    # TODO: Gerçek API entegrasyonu
    # file = await ctx.bot.get_file(photo.file_id)
    # ... analyze with Vision API ...
    return True  # Placeholder

async def delete_and_warn(update: Update, ctx: ContextTypes.DEFAULT_TYPE, user, reason: str) -> None:
    """Mesajı sil ve uyarı ver"""
    chat = update.effective_chat
    msg = update.message

    # Mesajı sil
    try:
        await msg.delete()
        data["stats"]["deleted_messages"] += 1
    except Exception as e:
        logger.warning(f"Silme hatası: {e}")

    # Uyarı sayısını artır
    count = add_warning(chat.id, user.id)

    await handle_warning(update, ctx, user, count, reason)
    await send_log(ctx, f"DELETE | {user.full_name} | {reason} | Uyarı: {count}/5 | {chat.title}")

async def handle_warning(update, ctx, user, count: int, reason: str) -> None:
    """Uyarı sayısına göre aksiyon al"""
    chat = update.effective_chat

    if count >= 5:
        # Kalıcı ban
        try:
            await chat.ban_member(user.id)
            data["stats"]["perm_bans"] += 1
            save_data(data)
            await ctx.bot.send_message(
                chat.id,
                f"🔨 *{user.full_name}* gruptan kalıcı olarak çıkarıldı.\n"
                f"_Sebep: {reason} (5 uyarı)_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Ban hatası: {e}")

    elif count >= 3:
        # 24 saat geçici ban
        until = datetime.now() + timedelta(hours=24)
        try:
            await chat.ban_member(user.id, until_date=until)
            data["stats"]["temp_bans"] += 1
            save_data(data)
            await ctx.bot.send_message(
                chat.id,
                f"⏱️ *{user.full_name}* 24 saatliğine kısıtlandı.\n"
                f"_Sebep: {reason} ({count}. uyarı)_",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Geçici ban hatası: {e}")
    else:
        # Sadece uyarı
        try:
            await ctx.bot.send_message(
                chat.id,
                f"⚠️ *{user.full_name}*, bu davranışın yasak!\n"
                f"_Sebep: {reason}_\n"
                f"Uyarı: *{count}/5* | /kurallar",
                parse_mode="Markdown"
            )
        except Exception as e:
            logger.error(f"Uyarı mesajı hatası: {e}")

# ─────────────────────────────────────────────────
# PASİF ÜYE KONTROLCİ (Scheduler)
# ─────────────────────────────────────────────────
async def check_inactive_members(app: Application) -> None:
    """30+ gündür yazmayan üyelere mesaj gönder"""
    now = time.time()
    threshold = 30 * 24 * 3600  # 30 gün saniye cinsinden

    for chat_key, members in data["last_seen"].items():
        for user_key, last_ts in members.items():
            if now - last_ts > threshold:
                name = data["members"].get(chat_key, {}).get(user_key, "Merhaba")
                first_name = name.split()[0] if name else "Merhaba"
                try:
                    await app.bot.send_message(
                        int(chat_key),
                        f"👋 *{first_name}*, seni bir süredir göremedik!\n\n"
                        f"Nasılsın? Grubunu özledin mi? 💙\n"
                        f"Yeni etkinliklerimize göz at: kneo-community.com",
                        parse_mode="Markdown"
                    )
                    # Son görülmeyi şimdi olarak güncelle (spam önleme)
                    data["last_seen"][chat_key][user_key] = now
                    logger.info(f"Pasif üye mesajı: {name} / chat {chat_key}")
                except Exception as e:
                    logger.warning(f"Pasif mesaj hatası: {e}")

    save_data(data)

async def send_weekly_message(app: Application) -> None:
    """Her Cumartesi sabah 10:00 grup mesajı"""
    msg = (
        "🌟 *Herkese güzel bir hafta sonu!*\n\n"
        "Bu hafta ne planlıyorsunuz? 😊\n"
        "Yeni etkinlikler için: kneo-community.com/etkinlikler\n\n"
        "_KNEO – Dünyanın her köşesinde Türkler_"
    )
    for chat_key in data["members"].keys():
        try:
            await app.bot.send_message(int(chat_key), msg, parse_mode="Markdown")
            await asyncio.sleep(0.5)  # Rate limit önleme
        except Exception as e:
            logger.warning(f"Haftalık mesaj hatası: {e}")

# ─────────────────────────────────────────────────
# YARDIMCI
# ─────────────────────────────────────────────────
async def is_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    """Kullanıcının admin olup olmadığını kontrol et"""
    try:
        user = update.effective_user
        chat = update.effective_chat
        member = await chat.get_member(user.id)
        return member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except Exception:
        return False

# ─────────────────────────────────────────────────
# ANA FONKSİYON
# ─────────────────────────────────────────────────
def main() -> None:
    """Botu başlat"""
    if BOT_TOKEN == "HIER_DEINEN_TOKEN_EINFÜGEN":
        print("❌ HATA: BOT_TOKEN ayarlanmamış!")
        print("   export BOT_TOKEN='1234567890:ABCdef...'")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    # Komutlar
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("stats",   cmd_stats))
    app.add_handler(CommandHandler("warn",    cmd_warn))
    app.add_handler(CommandHandler("ban",     cmd_ban))
    app.add_handler(CommandHandler("reset",   cmd_reset))
    app.add_handler(CommandHandler("kurallar",cmd_rules))
    app.add_handler(CommandHandler("rules",   cmd_rules))

    # Mesaj denetimi (metin + medya)
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.ALL | filters.VIDEO,
        on_message
    ))

    # Yeni üye karşılama
    app.add_handler(ChatMemberHandler(on_member_join, ChatMemberHandler.CHAT_MEMBER))

    # ── Zamanlayıcı görevler ──
    async def post_init(application: Application) -> None:
        # Her gün sabah 09:00 pasif üye kontrolü
        schedule.every().day.at("09:00").do(
            lambda: asyncio.create_task(check_inactive_members(application))
        )
        # Her Cumartesi 10:00 haftalık mesaj
        schedule.every().saturday.at("10:00").do(
            lambda: asyncio.create_task(send_weekly_message(application))
        )

        async def run_scheduler():
            while True:
                schedule.run_pending()
                await asyncio.sleep(60)

        asyncio.create_task(run_scheduler())

    app.post_init = post_init

    print("🚀 KNEO Bot başlatıldı!")
    print(f"📊 Veri dosyası: {DATA_FILE.absolute()}")
    print("⏹️  Durdurmak için Ctrl+C\n")

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
