import os
import random
import subprocess
from threading import Thread
from flask import Flask
import telebot

TOKEN = os.getenv("BOT_TOKEN")  # Токен подтянется из настроек Render
bot = telebot.TeleBot(TOKEN)

# --- Мини-сервер Flask, чтобы Render не усыплял бота ---
app = Flask("")


@app.route("/")
def home():
  return "Bot is active!"


def run_web():
  app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))


# ------------------------------------------------------


@bot.message_handler(content_types=["video", "document"])
def handle_video(message):
  print("📥 Поймал входящий файл от пользователя!")

  if message.content_type == "document" and not message.document.mime_type.startswith(
      "video"
  ):
    bot.reply_to(message, "❌ Пришли мне именно видеофайл.")
    return

  msg = bot.reply_to(message, "📥 Скачиваю видео...")

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

    bot.edit_message_text("📤 Отправка...", message.chat.id, msg.message_id)

    for file_path in generated_files:
      with open(file_path, "rb") as vid:
        bot.send_video(message.chat.id, vid, caption="🎬 Уникальная копия", timeout=120)

    os.remove(input_path)
    for file_path in generated_files:
      os.remove(file_path)
    bot.delete_message(message.chat.id, msg.message_id)

  except Exception as e:
    print(f"❌ Ошибка: {e}")
    bot.reply_to(message, f"Ошибка: {e}")


if __name__ == "__main__":
  # Запускаем Flask в отдельном потоке
  t = Thread(target=run_web)
  t.start()

  print("🤖 Бот запущен на Render!")
  bot.infinity_polling(skip_pending=True)
