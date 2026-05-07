#!/usr/bin/env python3
"""
KNEO Community Bot – kneo-community.com
Otomatik link yönetimi + moderasyon
"""

import logging, re, json, asyncio
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Update, ChatMember, ChatPermissions
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ChatMemberHandler, filters, ContextTypes,
)
from telegram.error import TelegramError

BOT_TOKEN = "8502930539:AAF_jpNsVR4Xhsq2d3uTRtRHntdmMGe2Mbw"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Dosyalar ────────────────────────────────────────
LINKS_FILE = Path("group_links.json")
DATA_FILE  = Path("kneo_data.json")

def load_links():
    if LINKS_FILE.exists():
        try: return json.loads(LINKS_FILE.read_text())
        except: pass
    return {}

def save_links(links):
    LINKS_FILE.write_text(json.dumps(links, ensure_ascii=False, indent=2))

def load_data():
    if DATA_FILE.exists():
        try: return json.loads(DATA_FILE.read_text())
        except: pass
    return {"warnings": {}, "members": {}}

def save_data(d):
    DATA_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2))

group_links = load_links()
data = load_data()

# ── Yasaklı kelimeler ────────────────────────────────
BANNED_WORDS = [
    # Türkçe
    "aptal","salak","gerizekalı","mal","orospu","oç","piç","amk","siktir",
    "götü","ibne","sürtük","fahişe","kaltak","kahpe","s.k","a.q","o.ç",
    "bok","yarrak","yarak","kancık","şerefsiz","alçak","haysiyetsiz",
    "namussuz","beyinsiz","dangalak","gerzek","hıyar",
    # Almanca
    "scheiße","scheisse","arschloch","arsch","wichser","hurensohn","hure",
    "vollidiot","depp","trottel","blödmann","fick","ficken","schlampe",
    "fotze","penner","dreckskerl",
    # İngilizce
    "fuck","fucking","fucker","shit","bullshit","bitch","asshole",
    "cunt","dick","cock","pussy","whore","slut","moron","retard",
    # Spam
    "reklam","kazan","para kazan","ücretsiz kazan","kripto kazan","bedava para",
]

def is_bad(text: str) -> bool:
    t = text.lower().replace(" ","").replace(".","").replace("*","")
    return any(w.replace(" ","") in t for w in BANNED_WORDS)

async def is_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    try:
        m = await update.effective_chat.get_member(update.effective_user.id)
        return m.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]
    except: return False

def add_warn(chat_id, user_id):
    ck, uk = str(chat_id), str(user_id)
    data["warnings"].setdefault(ck, {})
    data["warnings"][ck][uk] = data["warnings"][ck].get(uk, 0) + 1
    save_data(data)
    return data["warnings"][ck][uk]

# ── Otomatik Link Yönetimi ───────────────────────────

async def create_invite_link(ctx, chat_id: int) -> str | None:
    """Kalıcı davet linki oluştur veya mevcut olanı döndür."""
    chat_key = str(chat_id)
    
    # Mevcut link var mı?
    if chat_key in group_links:
        return group_links[chat_key]["link"]
    
    try:
        # Yeni kalıcı link oluştur
        link = await ctx.bot.create_chat_invite_link(
            chat_id=chat_id,
            name="KNEO Community Link",
            creates_join_request=False,
            # expire_date=None → kalıcı
            # member_limit=None → sınırsız
        )
        
        # Kaydet
        chat = await ctx.bot.get_chat(chat_id)
        group_links[chat_key] = {
            "link": link.invite_link,
            "chat_title": chat.title,
            "created_at": datetime.now().isoformat(),
        }
        save_links(group_links)
        logger.info(f"✅ Yeni link oluşturuldu: {chat.title} → {link.invite_link}")
        return link.invite_link
        
    except TelegramError as e:
        logger.error(f"Link oluşturma hatası ({chat_id}): {e}")
        return None

# ── Komutlar ────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text(
            "👋 *KNEO Community Bot*\n\n"
            "🌐 www.kneo-community.com\n\n"
            "Beni bir gruba admin olarak ekle, gerisini ben hallederim!\n\n"
            "Komutlar:\n"
            "/link – Grup davet linkini göster\n"
            "/kurallar – Grup kuralları\n"
            "/warn – Üye uyar (admin)\n"
            "/ban – Üye banla (admin)",
            parse_mode="Markdown"
        )
    else:
        invite = await create_invite_link(ctx, chat.id)
        msg = f"👋 Merhaba! KNEO Bot aktif.\n🌐 kneo-community.com"
        if invite:
            msg += f"\n🔗 Davet linki: {invite}"
        await update.message.reply_text(msg)

async def cmd_link(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Grubun davet linkini göster veya oluştur."""
    chat = update.effective_chat
    if chat.type == "private":
        await update.message.reply_text("Bu komutu bir grupta kullan!")
        return
    
    invite = await create_invite_link(ctx, chat.id)
    if invite:
        await update.message.reply_text(
            f"🔗 *{chat.title}* davet linki:\n{invite}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ Link oluşturulamadı. Bot admin yetkisi var mı?"
        )

async def cmd_links_all(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tüm grup linklerini listele (sadece özel mesajda)."""
    if update.effective_chat.type != "private":
        return
    if not group_links:
        await update.message.reply_text("Henüz kayıtlı link yok.")
        return
    
    msg = "📋 *Tüm Grup Linkleri:*\n\n"
    for key, info in group_links.items():
        msg += f"• {info.get('chat_title','?')}\n  {info['link']}\n\n"
    
    # Mesaj çok uzunsa böl
    if len(msg) > 4000:
        parts = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode="Markdown")
    else:
        await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_export(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Linkleri JSON dosyası olarak gönder."""
    if update.effective_chat.type != "private":
        return
    if not group_links:
        await update.message.reply_text("Henüz kayıtlı link yok.")
        return
    
    # JSON dosyası oluştur ve gönder
    LINKS_FILE.write_text(json.dumps(group_links, ensure_ascii=False, indent=2))
    await ctx.bot.send_document(
        chat_id=update.effective_chat.id,
        document=open(LINKS_FILE, 'rb'),
        filename="kneo_group_links.json",
        caption=f"📥 {len(group_links)} grup linki"
    )

async def cmd_kurallar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *KNEO Grup Kuralları*\n\n"
        "1️⃣ Saygılı olun\n"
        "2️⃣ Küfür yasak\n"
        "3️⃣ Reklam & spam yasak\n"
        "4️⃣ Uygunsuz içerik yasak\n"
        "5️⃣ DM'den rahatsız etmek yasak\n\n"
        "⚠️ 3 uyarı → 24 saat ban\n"
        "⚠️ 5 uyarı → kalıcı ban\n\n"
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
    await do_warning(ctx, update.effective_chat, target, count, "Admin uyarısı")

async def cmd_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    await update.effective_chat.ban_member(target.id)
    await update.message.reply_text(f"🔨 {target.full_name} banlandı.")

async def cmd_unban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await is_admin(update, ctx): return
    if not update.message.reply_to_message: return
    target = update.message.reply_to_message.from_user
    await update.effective_chat.unban_member(target.id)
    await update.message.reply_text(f"✅ {target.full_name} banı kaldırıldı.")

# ── Yeni üye karşılama ───────────────────────────────

async def on_member_join(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    new_member = result.new_chat_member

    # Bot eklendiğinde otomatik link oluştur
    if new_member.user.id == ctx.bot.id:
        logger.info(f"Bot gruba eklendi: {result.chat.title}")
        await asyncio.sleep(2)
        await create_invite_link(ctx, result.chat.id)
        return

    if new_member.status not in ("member", "administrator"):
        return

    user = new_member.user
    await send_welcome(ctx, result.chat.id, user)


async def on_new_member_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Fallback: new_chat_members message event"""
    msg = update.message
    if not msg or not msg.new_chat_members:
        return
    for user in msg.new_chat_members:
        if user.id == ctx.bot.id:
            await asyncio.sleep(2)
            await create_invite_link(ctx, msg.chat.id)
            continue
        await send_welcome(ctx, msg.chat.id, user)


async def send_welcome(ctx, chat_id: int, user):
    try:
        await ctx.bot.send_message(
            chat_id,
            f"🌐 www.kneo-community.com\n\n"
            f"*HOŞ GELDİN {user.first_name}!* 👋\n\n"
            f"➪ DM'den rahatsız etmek yok\n"
            f"➪ Hassas + argo konular yasak\n"
            f"➪ Saygı şart\n\n"
            f"🔒 *Filtre sistemi aktif*\n"
            f"Küfür eden, reklam yapan ve uygunsuz içerik paylaşanlar "
            f"otomatik olarak bloklanır.\n\n"
            f"_Kurallara uy, gerisi serbest_ ✅",
            parse_mode="Markdown"
        )
        logger.info(f"Welcomed {user.full_name} in chat {chat_id}")
    except Exception as e:
        logger.error(f"Welcome error: {e}")

# ── Mesaj denetimi ───────────────────────────────────

async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.from_user: return
    if await is_admin(update, ctx): return

    text = msg.text or msg.caption or ""
    if text and is_bad(text):
        try: await msg.delete()
        except: pass
        count = add_warn(update.effective_chat.id, msg.from_user.id)
        await do_warning(ctx, update.effective_chat, msg.from_user, count, "küfür/spam")

async def do_warning(ctx, chat, user, count: int, reason: str):
    try:
        if count >= 5:
            await chat.ban_member(user.id)
            await ctx.bot.send_message(chat.id,
                f"🔨 *{user.full_name}* kalıcı banlandı.\n_{reason}_",
                parse_mode="Markdown")
        elif count >= 3:
            until = datetime.now() + timedelta(hours=24)
            await chat.ban_member(user.id, until_date=until)
            await ctx.bot.send_message(chat.id,
                f"⏱️ *{user.full_name}* 24 saat kısıtlandı.\n_{reason}_",
                parse_mode="Markdown")
        else:
            await ctx.bot.send_message(chat.id,
                f"⚠️ *{user.first_name}*, bu davranış yasak!\n"
                f"_Sebep: {reason}_ – Uyarı *{count}/5*",
                parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Warning error: {e}")

# ── Ana ──────────────────────────────────────────────

def main():
    logger.info("🚀 KNEO Bot başlatılıyor...")
    logger.info(f"📋 Kayıtlı link sayısı: {len(group_links)}")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",    cmd_start))
    app.add_handler(CommandHandler("link",     cmd_link))
    app.add_handler(CommandHandler("links",    cmd_links_all))
    app.add_handler(CommandHandler("export",   cmd_export))
    app.add_handler(CommandHandler("kurallar", cmd_kurallar))
    app.add_handler(CommandHandler("rules",    cmd_kurallar))
    app.add_handler(CommandHandler("warn",     cmd_warn))
    app.add_handler(CommandHandler("ban",      cmd_ban))
    app.add_handler(CommandHandler("unban",    cmd_unban))
    app.add_handler(MessageHandler(
        filters.TEXT | filters.PHOTO | filters.Document.ALL, on_message))
    app.add_handler(MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_member_message))
    app.add_handler(ChatMemberHandler(
        on_member_join, ChatMemberHandler.CHAT_MEMBER))

    logger.info("✅ KNEO Bot aktif!")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
