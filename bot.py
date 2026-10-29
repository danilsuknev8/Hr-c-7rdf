from datetime import datetime, date
import os
import random
import subprocess
from threading import Thread
from flask import Flask
import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("BOT_TOKEN")  # Токен подтянется из настроек Render
bot = telebot.TeleBot(TOKEN)

# Словарь для хранения попыток пользователей: {user_id: {"date": date, "count": int}}
USER_LIMITS = {}
DAILY_LIMIT = 3
MAIN_BOT_URL = "https://t.me/Naketrue_bot"  # Ссылка на твой основной ИИ-бот

# --- Мини-сервер Flask, чтобы Render не усыплял бота ---
app = Flask("")


@app.route("/")
def home():
  return "Bot is active!"


def run_web():
  app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))


# ------------------------------------------------------


@bot.message_handler(commands=["start"])
def send_welcome(message):
  welcome_text = (
      f"👋 Привет! Я бот для уникализации видео.\n\n"
      f"🎬 Отправь мне видеофайл, и я сделаю его уникальным для обхода систем безопасности (Likee/TikTok).\n"
      f"🎁 У тебя есть **{DAILY_LIMIT} бесплатные попытки** на сегодня."
  )
  bot.reply_to(message, welcome_text, parse_mode="Markdown")


@bot.message_handler(content_types=["video", "document"])
def handle_video(message):
  user_id = message.from_user.id
  today = date.today()

  # Проверяем и обновляем лимиты пользователя
  if user_id not in USER_LIMITS or USER_LIMITS[user_id]["date"] != today:
    USER_LIMITS[user_id] = {"date": today, "count": 0}

  used_attempts = USER_LIMITS[user_id]["count"]

  if used_attempts >= DAILY_LIMIT:
    # Лимит исчерпан — предлагаем перейти в основной бот
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL)
    )

    limit_text = (
        f"❌ Упс! Твои {DAILY_LIMIT} бесплатных попытки на сегодня закончились.\n\n"
        f"💎 Хочешь больше генераций и крутой ИИ-контент? Переходи в наш основной проект!"
    )
    bot.reply_to(message, limit_text, reply_markup=markup, parse_mode="Markdown")
    return

  if message.content_type == "document" and not message.document.mime_type.startswith(
      "video"
  ):
    bot.reply_to(message, "❌ Пришли мне именно видеофайл.")
    return

  # Увеличиваем счетчик использованных попыток
  USER_LIMITS[user_id]["count"] += 1
  current_attempt = USER_LIMITS[user_id]["count"]

  msg = bot.reply_to(
      message,
      f"📥 Скачиваю видео... (Попытка {current_attempt} из {DAILY_LIMIT})",
  )

  try:
    file_info = bot.get_file(
        message.video.file_id if message.video else message.document.file_id
    )
    downloaded_file = bot.download_file(file_info.file_path)

    input_path = "source_input.mp4"
    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    bot.edit_message_text(
        "⚙️ Уникализация через FFmpeg...", message.chat.id, msg.message_id
    )

    output_dir = "bot_ready"
    os.makedirs(output_dir, exist_ok=True)
    copies = 1
    generated_files = []

    for i in range(1, copies + 1):
      out_file = os.path.join(output_dir, f"uniq_{i}.mp4")

      speed = round(random.uniform(0.95, 1.06), 3)
      pts = round(1 / speed, 4)
      zoom = round(random.uniform(1.02, 1.06), 3)
      bright = round(random.uniform(-0.03, 0.03), 3)
      contrast = round(random.uniform(0.96, 1.04), 3)
      sat = round(random.uniform(0.95, 1.05), 3)
      noise = random.randint(1, 3)
      crf = random.randint(19, 24)
      start_cut = round(random.uniform(0.03, 0.12), 2)

      vf = (
          f"setpts={pts}*PTS,"
          f"scale=iw*{zoom}:ih*{zoom},crop=iw/{zoom}:ih/{zoom},"
          f"eq=brightness={bright}:contrast={contrast}:saturation={sat},"
          f"noise=alls={noise}:allf=t"
      )

      cmd = [
          "ffmpeg",
          "-y",
          "-ss",
          str(start_cut),
          "-i",
          input_path,
          "-map_metadata",
          "-1",
          "-metadata",
          "make=Apple",
          "-metadata",
          f"model=iPhone {random.choice(['14', '15', '16'])} Pro",
          "-vf",
          vf,
          "-af",
          f"atempo={speed}",
          "-c:v",
          "libx264",
          "-preset",
          "ultrafast",
          "-crf",
          str(crf),
          "-c:a",
          "aac",
          "-b:a",
          f"{random.choice([128, 160, 192])}k",
          out_file,
      ]

      subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
      generated_files.append(out_file)

    bot.edit_message_text(
        "📤 Отправка готового видео...", message.chat.id, msg.message_id
    )

    # Создаем инлайн-кнопку для перехода в основной бот
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🔥 Создать ИИ-контент", url=MAIN_BOT_URL)
    )

    for file_path in generated_files:
      with open(file_path, "rb") as vid:
        bot.send_video(
            message.chat.id,
            vid,
            caption=(
                f"🎬 Уникальная копия готова!\n"
                f"💡 Осталось попыток на сегодня: {DAILY_LIMIT - current_attempt}/{DAILY_LIMIT}"
            ),
            reply_markup=markup,
            timeout=120,
        )

    os.remove(input_path)
    for file_path in generated_files:
      os.remove(file_path)
    bot.delete_message(message.chat.id, msg.message_id)

  except Exception as e:
    print(f"❌ Ошибка: {e}")
    bot.reply_to(message, f"❌ Произошла ошибка при обработке: {e}")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton("🚀 Запустить ИИ-бот", url=MAIN_BOT_URL)
  )
  bot.reply_to(
      message,
      "👋 Привет! Отправь мне видеофайл для уникализации.\n(Доступно 3 попытки в сутки)",
      reply_markup=markup,
  )
3

if __name__ == "__main__":
  t = Thread(target=run_web)
  t.start()
  print("🤖 Бот с лимитами и воронкой запущен!")
  bot.infinity_polling(skip_pending=True)
