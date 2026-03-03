# 04

# أضفت دالة compress_to_size التي تضبط CRF تدريجيًا للوصول إلى الحجم المطلوب.

# الفيديو يتم ضغطه تلقائيًا قبل الإرسال إذا تجاوز الحجم المحدد.

# الحفاظ على جودة الفيديو قدر الإمكان.

import os
import math
import yt_dlp
import subprocess
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import asyncio

BOT_TOKEN = "8771343659:AAFO2am_bvULjxqi-iaPy-b_3mLGXwokwAk"
DEFAULT_MAX_SIZE_MB = 49
TEMP_DIR = "/tmp"

app = Flask(__name__)
bot = Bot(BOT_TOKEN)
telegram_app = ApplicationBuilder().token(BOT_TOKEN).build()

def sizeof_fmt(num):
    for unit in ['B','KB','MB','GB']:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0

def start(update, context):
    context.user_data.clear()
    update.message.reply_text("🎬 أرسل رابط يوتيوب")

def handle_message(update, context):
    if context.user_data.get("awaiting_size"):
        text = update.message.text
        if text.lower() in ["❌", "cancel"]:
            context.user_data.clear()
            update.message.reply_text("❌ تم الإلغاء. أرسل رابط جديد.")
            return
        try:
            context.user_data["custom_size"] = float(text)
            context.user_data["awaiting_size"] = False
            update.message.reply_text("✅ تم حفظ الحجم. اختر الجودة الآن.")
        except ValueError:
            update.message.reply_text("❌ أدخل رقم صحيح بالميغابايت.")
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
            video_buttons.append([InlineKeyboardButton(label, callback_data=f"video|{f['format_id']}")])

    extra_buttons = [
        [InlineKeyboardButton("📏 إدخال حجم مخصص", callback_data="customsize")],
        [InlineKeyboardButton("🎵 تحميل MP3", callback_data="audio")],
        [InlineKeyboardButton("❌ إلغاء", callback_data="cancel")]
    ]

    keyboard = video_buttons[:6] + extra_buttons
    reply_markup = InlineKeyboardMarkup(keyboard)

    update.message.reply_text(
        f"📌 {title}\n⏱ {math.floor(duration/60)} دقيقة\nاختر الجودة:",
        reply_markup=reply_markup
    )

def compress_to_size(input_file, output_file, target_mb):
    # تحويل ميغابايت إلى بايت
    target_bytes = target_mb * 1024 * 1024
    # تقدير CRF مبدئي
    crf = 28
    while True:
        subprocess.run([
            "ffmpeg", "-y", "-i", input_file,
            "-vcodec", "libx264", "-crf", str(crf),
            "-preset", "fast",
            output_file
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        size = os.path.getsize(output_file)
        if size <= target_bytes or crf >= 40:
            break
        crf += 2  # زيادة الضغط تدريجيًا
    return output_file

def button(update, context):
    query = update.callback_query
    query.answer()

    if query.data == "cancel":
        context.user_data.clear()
        query.edit_message_text("❌ تم الإلغاء. أرسل رابط جديد.")
        return

    if query.data == "customsize":
        context.user_data["awaiting_size"] = True
        query.edit_message_text("📥 أدخل الحجم بالميغابايت:")
        return

    query.edit_message_text("⏳ جاري المعالجة...")

    url = context.user_data.get("url")
    data = query.data.split("|")
    target_size = context.user_data.get("custom_size", DEFAULT_MAX_SIZE_MB)

    if data[0] == "audio":
        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": os.path.join(TEMP_DIR, "audio.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "32"}],
            "nopart": True,
        }
        filename = os.path.join(TEMP_DIR, "audio.mp3")
    else:
        format_id = data[1]
        ydl_opts = {"format": format_id, "outtmpl": os.path.join(TEMP_DIR, "video.%(ext)s"), "nopart": True}
        filename = os.path.join(TEMP_DIR, "video.mp4")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    if os.path.exists(filename):
        size_mb = os.path.getsize(filename) / (1024*1024)

        if size_mb > target_size and filename.endswith(".mp4"):
            compressed_file = os.path.join(TEMP_DIR, "compressed.mp4")
            compress_to_size(filename, compressed_file, target_size)
            os.remove(filename)
            filename = compressed_file

        with open(filename, "rb") as f:
            if filename.endswith(".mp3"):
                query.message.reply_audio(f)
            else:
                query.message.reply_video(f)

        os.remove(filename)

    context.user_data.clear()

telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
telegram_app.add_handler(CallbackQueryHandler(button))

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(telegram_app.process_update(update))
    return "ok"

@app.route("/")
def index():
    return "Bot is running"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)