import os
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = "8771343659:AAFO2am_bvULjxqi-iaPy-b_3mLGXwokwAk"

# تخزين الرابط مؤقتاً لكل مستخدم
user_links = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("أرسل رابط يوتيوب")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    user_links[update.message.from_user.id] = url

    keyboard = [
        [InlineKeyboardButton("360p", callback_data="360")],
        [InlineKeyboardButton("720p", callback_data="720")],
        [InlineKeyboardButton("1080p", callback_data="1080")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("اختر الدقة:", reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    quality = query.data
    user_id = query.from_user.id
    url = user_links.get(user_id)

    if not url:
        await query.edit_message_text("أعد إرسال الرابط")
        return

    await query.edit_message_text("جاري التحميل...")

    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
        'outtmpl': f'{user_id}.mp4',
        'merge_output_format': 'mp4'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        with open(f"{user_id}.mp4", "rb") as video:
            await context.bot.send_video(chat_id=user_id, video=video)

        os.remove(f"{user_id}.mp4")

    except Exception as e:
        await context.bot.send_message(chat_id=user_id, text="حدث خطأ أثناء التحميل")

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(button))

app.run_polling()