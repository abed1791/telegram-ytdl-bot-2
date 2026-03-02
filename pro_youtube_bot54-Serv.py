#bot54
import os
import math
import yt_dlp
import threading
from flask import Flask, send_from_directory
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ===== الإعدادات =====
BOT_TOKEN = "8771343659:AAFO2am_bvULjxqi-iaPy-b_3mLGXwokwAk"
BASE_URL = "https://telegram-ytdl-bot-1-qhnq.onrender.com"
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# ===== Flask =====
app_web = Flask(__name__)

@app_web.route("/download/<path:filename>")
def download_file(filename):
    return send_from_directory(DOWNLOAD_DIR, filename, as_attachment=True)

# ===== أدوات =====
def sizeof_fmt(num):
    for unit in ['B','KB','MB','GB']:
        if num < 1024.0:
            return f"{num:.2f} {unit}"
        num /= 1024.0
    return f"{num:.2f} TB"

def base_ydl_opts():
    return {
        "quiet": True,
        "nocheckcertificate": True,
        "cookiefile": "cookies.txt",  # مهم
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }

# ===== Handlers البوت =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🎬 أرسل رابط يوتيوب")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    context.user_data.clear()
    context.user_data["url"] = url

    try:
        with yt_dlp.YoutubeDL(base_ydl_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        await update.message.reply_text("❌ فشل استخراج الفيديو (قد تحتاج تحديث cookies)")
        return

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

    keyboard = video_buttons[:6]
    keyboard.append([InlineKeyboardButton("🎵 تحميل MP3", callback_data="audio")])

    await update.message.reply_text(
        f"📌 {title}\n⏱ {math.floor(duration/60)} دقيقة\nاختر الجودة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ جاري المعالجة...")

    url = context.user_data.get("url")
    if not url:
        await query.message.reply_text("❌ حدث خطأ، أعد إرسال الرابط")
        return

    data = query.data.split("|")

    if data[0] == "audio":
        output_name = "audio.mp3"
        filepath = os.path.join(DOWNLOAD_DIR, output_name)

        ydl_opts = base_ydl_opts()
        ydl_opts.update({
            "format": "bestaudio",
            "outtmpl": os.path.join(DOWNLOAD_DIR, "audio.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio","preferredcodec": "mp3","preferredquality": "64"}],
            "nopart": True,
        })
    else:
        format_id = data[1]
        output_name = "video.mp4"
        filepath = os.path.join(DOWNLOAD_DIR, output_name)

        ydl_opts = base_ydl_opts()
        ydl_opts.update({
            "format": format_id,
            "outtmpl": os.path.join(DOWNLOAD_DIR, "video.%(ext)s"),
            "nopart": True,
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except Exception:
        await query.message.reply_text("❌ فشل التحميل (تحقق من صلاحية cookies)")
        return

    if os.path.exists(filepath):
        link = f"{BASE_URL}/download/{output_name}"
        await query.message.reply_text(f"✅ تم الانتهاء\n🔗 رابط التحميل:\n{link}")
    else:
        await query.message.reply_text("❌ لم يتم إنشاء الملف")

    context.user_data.clear()

# ===== تشغيل البوت و Flask =====
def run_bot():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button))
    app.run_polling()

if __name__ == "__main__":
    # Thread لتشغيل البوت
    threading.Thread(target=run_bot).start()
    # Flask

    app_web.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)), debug=False, use_reloader=False)
