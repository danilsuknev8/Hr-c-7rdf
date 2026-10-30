from datetime import date
import os
import random
import subprocess
from threading import Thread
from flask import Flask
from PIL import Image, ImageEnhance
import telebot
from telebot.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
)

TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

USER_LIMITS = {}
DAILY_LIMIT = 3
MAIN_BOT_URL = "https://t.me/Naketrue_bot"

# --- БАЗА ПРОМОКОДОВ ---
PROMO_CODES = {
    "START2026": 5,
    "BONUS": 3,
    "VIP": 10
}
ACTIVATED_PROMOS = {}
# ------------------------

USER_MODES = {}         
USER_PRESETS = {}       
USER_PENDING_MEDIA = {} 

PRESETS = {
    "preset_light": {
        "name": "🟢 Легкая (для Reels)",
        "speed_min": 0.98,
        "speed_max": 1.02,
        "zoom": 1.02,
        "noise": 1,
    },
    "preset_medium": {
        "name": "🟡 Средняя (для TikTok)",
        "speed_min": 0.95,
        "speed_max": 1.06,
        "zoom": 1.04,
        "noise": 2,
    },
    "preset_hard": {
        "name": "🔴 Жесткая (для Likee)",
        "speed_min": 0.90,
        "speed_max": 1.10,
        "zoom": 1.06,
        "noise": 3,
    },
}

app = Flask("")

@app.route("/")
def home():
  return "Bot is active!"

def run_web():
  app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

def get_user_data(user_id):
  today = date.today()
  if user_id not in USER_LIMITS or USER_LIMITS[user_id]["date"] != today:
    USER_LIMITS[user_id] = {
        "date": today,
        "count": 0,
        "bonus": USER_LIMITS.get(user_id, {}).get("bonus", 0),
    }
  return USER_LIMITS[user_id]

@bot.message_handler(commands=["start"])
def send_welcome(message):
  args = message.text.split()
  user_id = message.from_user.id

  if len(args) > 1 and args[1].startswith("ref_"):
    try:
      referrer_id = int(args[1].split("_")[1])
      if referrer_id != user_id:
        ref_data = get_user_data(referrer_id)
        ref_data["bonus"] += 2
        try:
          bot.send_message(
              referrer_id,
              "🎉 По вашей ссылке зарегистрировался новый пользователь! Вам начислено +2 бонусные попытки.",
          )
        except:
          pass
    except Exception as e:
      print(f"Ref error: {e}")

  ref_link = f"https://t.me/{bot.get_me().username}?start=ref_{user_id}"
  user_data = get_user_data(user_id)
  total_available = DAILY_LIMIT + user_data["bonus"] - user_data["count"]

  welcome_text = (
      f"👋 Привет! Я быстрый бот-комбайн для работы с видео и фото.\n\n"
      f"🛠 **Режимы работы:**\n"
      f"🎬 Уникализация видео/фото\n"
      f"🔵 Видео в кружочек\n"
      f"🎵 Извлечь аудио (MP3)\n"
      f"💧 Добавить водяной знак\n\n"
      f"📥 **Просто присылай видео или фото в чат!**\n\n"
      f"🎁 Попыток сегодня: **{max(0, total_available)}**\n"
      f"🎟 Промокод: `/promo КОД`\n\n"
      f"🔗 Реферальная ссылка: `{ref_link}`"
  )

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton("🎬 Уникализировать", callback_data="mode_uniq"),
      InlineKeyboardButton("🔵 В кружочек", callback_data="mode_circle"),
  )
  markup.add(
      InlineKeyboardButton("🎵 Извлечь аудио", callback_data="mode_audio"),
      InlineKeyboardButton("💧 Водяной знак", callback_data="mode_watermark"),
  )
  markup.add(
      InlineKeyboardButton("⭐ Купить попытки (Stars)", callback_data="buy_stars")
  )
  markup.add(InlineKeyboardButton("🚀 Основной ИИ-бот", url=MAIN_BOT_URL))

  bot.reply_to(message, welcome_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=["promo"])
def handle_promo_code(message):
  user_id = message.from_user.id
  args = message.text.split()

  if len(args) < 2:
    bot.reply_to(message, "❌ Укажи промокод. Пример: `/promo START2026`", parse_mode="Markdown")
    return

  code = args[1].strip().upper()
  if code not in PROMO_CODES:
    bot.reply_to(message, "❌ Неверный или несуществующий промокод.")
    return

  if user_id not in ACTIVATED_PROMOS:
    ACTIVATED_PROMOS[user_id] = set()

  if code in ACTIVATED_PROMOS[user_id]:
    bot.reply_to(message, "⚠️ Ты уже активировал этот промокод ранее!")
    return

  bonus_amount = PROMO_CODES[code]
  user_data = get_user_data(user_id)
  user_data["bonus"] += bonus_amount
  ACTIVATED_PROMOS[user_id].add(code)

  bot.reply_to(
      message,
      f"🎉 Промокод **{code}** успешно активирован! Тебе начислено **+{bonus_amount} попыток**.",
      parse_mode="Markdown"
  )

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
  user_id = call.from_user.id
  data = call.data

  if data == "buy_stars":
    prices = [LabeledPrice(label="Пакет из 10 попыток", amount=5)]
    bot.send_invoice(
        chat_id=call.message.chat.id,
        title="Пакет попыток (10 шт.)",
        description="Покупка 10 дополнительных попыток.",
        invoice_payload="extra_attempts_10",
        provider_token="",
        currency="XTR",
        prices=prices,
    )
    bot.answer_callback_query(call.id)

  elif data.startswith("mode_"):
    mode = data.split("_")[1]
    USER_MODES[user_id] = mode
    mode_names = {
        "uniq": "Уникализация видео/фото",
        "circle": "Видео в кружочек",
        "audio": "Извлечение аудио (MP3)",
        "watermark": "Добавление водяного знака"
    }
    bot.answer_callback_query(call.id, f"Режим: {mode_names.get(mode, '')}")
    bot.edit_message_text(
        f"✅ Выбран режим: **{mode_names.get(mode, '')}**.\nТеперь отправь мне файл!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
    )

  elif data.startswith("preset_"):
    USER_PRESETS[user_id] = data
    bot.answer_callback_query(call.id, "✅ Пресет сохранен!")
    if user_id in USER_PENDING_MEDIA:
      media_message = USER_PENDING_MEDIA.pop(user_id)
      Thread(target=process_video_uniq, args=(media_message,)).start()

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(pre_checkout_query):
  bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=["successful_payment"])
def got_payment(message):
  user_id = message.from_user.id
  if message.successful_payment.invoice_payload == "extra_attempts_10":
    user_data = get_user_data(user_id)
    user_data["bonus"] += 10
    bot.reply_to(message, "✅ Оплата прошла успешно! Вам зачислено +10 попыток.")

@bot.message_handler(content_types=["video", "document"])
def handle_video_input(message):
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  total_available = DAILY_LIMIT + user_data["bonus"] - user_data["count"]

  if total_available <= 0:
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⭐ Купить попытки за Звезды", callback_data="buy_stars"))
    markup.add(InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL))
    bot.reply_to(message, "❌ Лимит исчерпан. Пополни баланс или перейди в основной бот:", reply_markup=markup)
    return

  if message.content_type == "document" and not message.document.mime_type.startswith("video"):
    bot.reply_to(message, "❌ Пришли мне именно видеофайл.")
    return

  mode = USER_MODES.get(user_id, "uniq")

  if mode == "circle":
    Thread(target=process_video_circle, args=(message,)).start()
  elif mode == "audio":
    Thread(target=process_extract_audio, args=(message,)).start()
  elif mode == "watermark":
    Thread(target=process_watermark, args=(message,)).start()
  else:
    USER_PRESETS[user_id] = message
    markup = InlineKeyboardMarkup()
    for key, val in PRESETS.items():
      markup.add(InlineKeyboardButton(val["name"], callback_data=key))
    bot.reply_to(message, "⚙️ Выбери режим уникализации для видео:", reply_markup=markup)

@bot.message_handler(content_types=["photo"])
def handle_photo_input(message):
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  total_available = DAILY_LIMIT + user_data["bonus"] - user_data["count"]

  if total_available <= 0:
    bot.reply_to(message, "❌ Лимит попыток исчерпан. Используй /promo")
    return

  user_data["count"] += 1
  msg = bot.reply_to(message, "📥 Обрабатываю изображение в фоне...")
  Thread(target=process_photo_worker, args=(message, msg.id)).start()

def process_photo_worker(message, msg_id):
  user_id = message.from_user.id
  rnd = random.randint(1000, 9999)
  input_path = f"source_img_{user_id}_{rnd}.jpg"
  output_path = f"uniq_img_{user_id}_{rnd}.jpg"

  try:
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    img = Image.open(input_path)
    width, height = img.size
    img = img.resize((width + random.choice([-1, 1]), height + random.choice([-1, 1])), Image.Resampling.LANCZOS)
    
    ImageEnhance.Brightness(img).enhance(random.uniform(0.98, 1.02))
    ImageEnhance.Contrast(img).enhance(random.uniform(0.98, 1.02)).save(output_path, "JPEG", quality=random.randint(92, 98))

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Создать ИИ-бот", url=MAIN_BOT_URL))

    with open(output_path, "rb") as photo:
      bot.send_photo(message.chat.id, photo, caption="🖼 Картинка уникализирована!", reply_markup=markup)

    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    bot.delete_message(message.chat.id, msg_id)

  except Exception as e:
    print(f"Photo error: {e}")
    bot.edit_message_text(f"❌ Ошибка обработки фото: {e}", message.chat.id, msg_id)

def process_video_circle(message):
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  user_data["count"] += 1

  msg = bot.reply_to(message, "🔵 Принято! Конвертирую видео в кружочек...")
  rnd = random.randint(1000, 9999)
  input_path = f"source_circle_{user_id}_{rnd}.mp4"
  output_path = f"result_circle_{user_id}_{rnd}.mp4"

  try:
    file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", "crop=min(iw\\,ih):min(iw\\,ih),scale=512:512",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", output_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    bot.edit_message_text("📤 Отправляю кружочек...", message.chat.id, msg.id + 1)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL))

    with open(output_path, "rb") as vid:
      bot.send_video_note(message.chat.id, vid, reply_markup=markup, timeout=120)

    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    bot.delete_message(message.chat.id, msg.id + 1)
  except Exception as e:
    print(f"Circle error: {e}")

def process_extract_audio(message):
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  user_data["count"] += 1

  msg = bot.reply_to(message, "🎵 Принято! Извлекаю аудио...")
  rnd = random.randint(1000, 9999)
  input_path = f"source_audio_{user_id}_{rnd}.mp4"
  output_path = f"result_audio_{user_id}_{rnd}.mp3"

  try:
    file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", "-ab", "192k", output_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    bot.edit_message_text("📤 Отправляю MP3...", message.chat.id, msg.id + 1)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL))

    with open(output_path, "rb") as aud:
      bot.send_audio(message.chat.id, aud, caption="🎵 Аудиодорожка извлечена!", reply_markup=markup, timeout=120)

    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    bot.delete_message(message.chat.id, msg.id + 1)
  except Exception as e:
    print(f"Audio error: {e}")

def process_watermark(message):
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  user_data["count"] += 1

  msg = bot.reply_to(message, "💧 Принято! Добавляю водяной знак...")
  rnd = random.randint(1000, 9999)
  input_path = f"source_wm_{user_id}_{rnd}.mp4"
  output_path = f"result_wm_{user_id}_{rnd}.mp4"

  try:
    file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    vf = "drawtext=text='@Naketrue_bot':fontcolor=white:fontsize=24:x=w-tw-15:y=15:box=1:boxcolor=black@0.5:boxborderw=5"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", vf, "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-c:a", "copy", output_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    bot.edit_message_text("📤 Отправляю видео...", message.chat.id, msg.id + 1)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL))

    with open(output_path, "rb") as vid:
      bot.send_video(message.chat.id, vid, caption="💧 Готово!", reply_markup=markup, timeout=120)

    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(output_path): os.remove(output_path)
    bot.delete_message(message.chat.id, msg.id + 1)
  except Exception as e:
    print(f"Watermark error: {e}")

def process_video_uniq(message):
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  user_data["count"] += 1

  preset_key = USER_PRESETS.get(user_id, "preset_medium")
  preset = PRESETS.get(preset_key, PRESETS["preset_medium"])

  msg = bot.reply_to(message, f"📥 Принято! Уникализирую видео ({preset['name']})...")
  rnd = random.randint(1000, 9999)
  input_path = f"source_input_{user_id}_{rnd}.mp4"
  output_dir = "bot_ready"
  os.makedirs(output_dir, exist_ok=True)
  out_file = os.path.join(output_dir, f"uniq_video_{user_id}_{rnd}.mp4")

  try:
    file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    speed = round(random.uniform(preset["speed_min"], preset["speed_max"]), 3)
    pts = round(1 / speed, 4)
    zoom = preset["zoom"]
    noise = preset["noise"]

    vf = f"setpts={pts}*PTS,scale=iw*{zoom}:ih*{zoom},crop=iw/{zoom}:ih/{zoom},noise=alls={noise}:allf=t"

    cmd = [
        "ffmpeg", "-y", "-ss", "0.05", "-i", input_path,
        "-map_metadata", "-1", "-metadata", "make=Apple", "-metadata", "model=iPhone 15 Pro",
        "-vf", vf, "-af", f"atempo={speed}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22",
        "-c:a", "aac", "-b:a", "128k", out_file
    ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    bot.edit_message_text("📤 Отправка файла...", message.chat.id, msg.id)

    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL))

    with open(out_file, "rb") as vid:
      bot.send_video(message.chat.id, vid, caption="🎬 Уникальная копия готова!", reply_markup=markup, timeout=120)

    if os.path.exists(input_path): os.remove(input_path)
    if os.path.exists(out_file): os.remove(out_file)
    bot.delete_message(message.chat.id, msg.id)
  except Exception as e:
    print(f"Video error: {e}")

@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
  markup = InlineKeyboardMarkup()
  markup.add(InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL))
  bot.reply_to(
      message,
      "👋 Пришли видеофайл или фото для обработки.\n🎟 Промокод: `/promo КОД`",
      reply_markup=markup,
      parse_mode="Markdown"
  )

if __name__ == "__main__":
  t = Thread(target=run_web)
  t.start()
  print("🤖 Бот успешно запущен и работает стабильно!")
  bot.infinity_polling(skip_pending=True)
