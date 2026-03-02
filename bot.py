
# ================== الإعدادات ==================
# BOT_TOKEN = "8771343659:AAFO2am_bvULjxqi-iaPy-b_3mLGXwokwAk"
#RENDER_EXTERNAL_URL = os.getenv("https://telegram-ytdl-bot-2.onrender.com")

import os
import math
import yt_dlp
import subprocess
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("https://telegram-ytdl-bot-2.onrender.com")
DEFAULT_MAX_SIZE_MB = 49

app = Flask(__name__)

def sizeof_fmt(num):
    for unit in ['B','KB','MB','GB']:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🎬 أرسل رابط يوتيوب")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("awaiting_size"):
        text = update.message.text
        if text.lower() in ["❌", "cancel"]:
            context.user_data.clear()
            await update.message.reply_text("❌ تم الإلغاء. أرسل رابط جديد.")
            return
        try:
            context.user_data["custom_size"] = float(text)
            context.user_data["awaiting_size"] = False
            await update.message.reply_text("✅ تم حفظ الحجم. اختر الجودة الآن.")
        except ValueError:
            await update.message.reply_text("❌ أدخل رقم صحيح بالميغابايت.")
        return

    url = update.message.text
    context.user_data.clear()
    context.user_data["url"] = url

    ydl_opts = {"quiet": True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title", "")
    duration = info.get("duration", 0)
    formats = info.get("formats", [])

    video_buttons = []
    for f in formats:
        if f.get("height") and f.get("ext") == "mp4":
            size = f.get("filesize") or 0
            label = f"{f['height']}p - {sizeof_fmt(size) if size else '??'}"
            video_buttons.append(
                [InlineKeyboardButton(label, callback_data=f"video|{f['format_id']}")]
            )

    extra_buttons = [
        [InlineKeyboardButton("📏 إدخال حجم مخصص", callback_data="customsize")],
        [InlineKeyboardButton("🎵 تحميل MP3", callback_data="audio")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]

    keyboard = video_buttons[:6] + extra_buttons
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"📌 {title}\n⏱ {math.floor(duration/60)} دقيقة\nاختر الجودة:",
        reply_markup=reply_markup
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        context.user_data.clear()
        await query.edit_message_text("❌ تم الإلغاء. أرسل رابط جديد.")
        return

    if query.data == "customsize":
        context.user_data["awaiting_size"] = True
        await query.edit_message_text("📥 أدخل الحجم بالميغابايت:")
        return

    await query.edit_message_text("⏳ جاري المعالجة...")

    url = context.user_data.get("url")
    data = query.data.split("|")
    target_size = context.user_data.get("custom_size", DEFAULT_MAX_SIZE_MB)

    temp_dir = "/tmp"

    if data[0] == "audio":
        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": os.path.join(temp_dir, "audio.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "32",
            }],
            "nopart": True,
        }
        filename = os.path.join(temp_dir, "audio.mp3")
    else:
        format_id = data[1]
        ydl_opts = {
            "format": format_id,
            "outtmpl": os.path.join(temp_dir, "video.%(ext)s"),
            "nopart": True
        }
        filename = os.path.join(temp_dir, "video.mp4")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if os.path.exists(filename):
        size_mb = os.path.getsize(filename) / (1024 * 1024)

        if size_mb > target_size and filename.endswith(".mp4"):
            compressed = os.path.join(temp_dir, "compressed.mp4")
            subprocess.run([
                "ffmpeg", "-i", filename,
                "-vcodec", "libx264",
                "-crf", "28",
                compressed
            ])
            os.remove(filename)
            filename = compressed

        with open(filename, "rb") as f:
            if filename.endswith(".mp3"):
                await query.message.reply_audio(f)
            else:
                await query.message.reply_video(f)

        os.remove(filename)

    context.user_data.clear()

# -------------------- Webhook Setup --------------------

telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(CallbackQueryHandler(button))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
async def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app.bot)
    await telegram_app.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "Bot is running"

if __name__ == "__main__":
    telegram_app.bot.set_webhook(f"{RENDER_EXTERNAL_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=10000)