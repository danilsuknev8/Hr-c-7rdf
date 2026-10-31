from datetime import date, datetime
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

# --- НАСТРОЙКИ АДМИНА ---
ADMIN_ID = 7878856735  # <--- ЗАМЕНИ НА СВОЙ REAL ID
# ------------------------

USER_LIMITS = {}
DAILY_LIMIT = 3
TOTAL_GENERATIONS_COUNT = 0
REGISTERED_USERS = set()  # Множество для отслеживания уникальных пользователей (рефералы)

# --- БАЗА ПРОМОКОДОВ ---
PROMO_CODES = {
    "START2026": 5,
    "BONUS": 3,
    "VIP": 10
}
ACTIVATED_PROMOS = {}
DAILY_BONUS_TRACKER = {} 

USER_PRESETS = {}       
USER_COUNTS = {}        
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

def send_main_menu(chat_id, user_id, text_prefix=""):
  user_data = get_user_data(user_id)
  total_available = DAILY_LIMIT + user_data["bonus"] - user_data["count"]
  
  # Генерируем реферальную ссылку
  try:
    bot_username = bot.get_me().username
  except:
    bot_username = "bot"
  ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"

  menu_text = (
      f"{text_prefix}\n\n"
      f"👋 Главное меню:\n"
      f"🎬 **Уникализация видео и фото**\n\n"
      f"📥 **Просто присылай видео или фото в чат!**\n\n"
      f"🎁 Попыток сегодня: **{max(0, total_available)}**\n"
      f"🎟 Промокод: `/promo КОД`\n"
      f"🔗 Реферальная ссылка: `{ref_link}`"
  )

  markup = InlineKeyboardMarkup()
  markup.add(
      InlineKeyboardButton("🎁 Забрать ежедневный бонус", callback_data="claim_daily"),
      InlineKeyboardButton("⭐ Купить попытки (Stars)", callback_data="buy_stars")
  )

  if user_id == ADMIN_ID:
    markup.add(InlineKeyboardButton("👑 Админ-панель", callback_data="admin_panel"))

  bot.send_message(chat_id, menu_text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=["start"])
def send_welcome(message):
  args = message.text.split()
  user_id = message.from_user.id

  # Реферальная логика для новых пользователей
  if user_id not in REGISTERED_USERS:
    REGISTERED_USERS.add(user_id)
    if len(args) > 1 and args[1].startswith("ref_"):
      try:
        referrer_id = int(args[1].split("_")[1])
        if referrer_id != user_id:
          ref_data = get_user_data(referrer_id)
          ref_data["bonus"] += 2
          try:
            bot.send_message(
                referrer_id,
                "🎉 По вашей реферальной ссылке зарегистрировался новый пользователь! Вам начислено **+2 бонусные попытки**.",
                parse_mode="Markdown"
            )
          except:
            pass
      except Exception as e:
        print(f"Ref error: {e}")

  send_main_menu(message.chat.id, user_id, "👋 Привет! Я быстрый бот для уникализации контента.")

@bot.message_handler(commands=["admin"])
def admin_command(message):
  if message.from_user.id != ADMIN_ID:
    return

  total_users = len(REGISTERED_USERS)
  active_today = sum(1 for uid, data in USER_LIMITS.items() if data["date"] == date.today())
  
  admin_text = (
      f"👑 **Панель администратора**\n\n"
      f"👥 Всего пользователей: `{total_users}`\n"
      f"🟢 Активных сегодня: `{active_today}`\n"
      f"🎬 Всего генераций за сессию: `{TOTAL_GENERATIONS_COUNT}`\n"
      f"📦 Активных промокодов: `{len(PROMO_CODES)}`\n\n"
      f"📌 **Доступные команды:**\n"
      f"• Рассылка текста или медиа: `/broadcast Текст` (прикрепи фото/видео по желанию)\n"
      f"• Выдать бонусы: `/addbonus ID кол-во`\n"
      f"• Создать промокод: `/addpromo КОД кол-во`\n"
      f"• Инфо о юзере: `/userinfo ID`"
  )

  markup = InlineKeyboardMarkup()
  markup.add(InlineKeyboardButton("📊 Обновить статистику", callback_data="admin_panel"))
  markup.add(InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_menu"))

  bot.reply_to(message, admin_text, parse_mode="Markdown", reply_markup=markup)

# Универсальный обработчик рассылки (поддерживает текст, фото, видео, документы)
@bot.message_handler(content_types=["text", "photo", "video", "document"], func=lambda message: (message.text and message.text.startswith("/broadcast")) or (message.caption and message.caption.startswith("/broadcast")))
def broadcast_command(message):
  if message.from_user.id != ADMIN_ID:
    return

  # Извлекаем текст (из сообщения или подписи к медиа)
  raw_text = message.caption if message.caption else message.text
  broadcast_text = raw_text[len("/broadcast"):].strip() if raw_text else ""

  status_msg = bot.reply_to(message, "📢 Начинаю рассылку...")

  success, failed = 0, 0
  for uid in list(REGISTERED_USERS):
    try:
      if message.photo:
        bot.send_photo(uid, message.photo[-1].file_id, caption=broadcast_text, parse_mode="Markdown")
      elif message.video:
        bot.send_video(uid, message.video.file_id, caption=broadcast_text, parse_mode="Markdown")
      elif message.document:
        bot.send_document(uid, message.document.file_id, caption=broadcast_text, parse_mode="Markdown")
      else:
        if broadcast_text:
          bot.send_message(uid, f"📢 **Сообщение от администратора:**\n\n{broadcast_text}", parse_mode="Markdown")
      success += 1
    except:
      failed += 1

  bot.edit_message_text(
      f"✅ **Рассылка завершена!**\n\n📨 Успешно: `{success}`\n❌ Ошибок: `{failed}`",
      message.chat.id,
      status_msg.message_id,
      parse_mode="Markdown"
  )

@bot.message_handler(commands=["addbonus"])
def addbonus_command(message):
  if message.from_user.id != ADMIN_ID:
    return

  args = message.text.split()
  if len(args) < 3:
    bot.reply_to(message, "❌ Формат: `/addbonus ID количество`", parse_mode="Markdown")
    return

  try:
    target_id, amount = int(args[1]), int(args[2])
    user_data = get_user_data(target_id)
    user_data["bonus"] += amount

    bot.reply_to(message, f"✅ Пользователю `{target_id}` начислено `+{amount}` попыток.", parse_mode="Markdown")
    try:
      bot.send_message(target_id, f"🎁 Администратор начислил вам **+{amount} бонусных попыток**!")
    except:
      pass
  except Exception as e:
    bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["addpromo"])
def addpromo_command(message):
  if message.from_user.id != ADMIN_ID:
    return

  args = message.text.split()
  if len(args) < 3:
    bot.reply_to(message, "❌ Формат: `/addpromo КОД количество`", parse_mode="Markdown")
    return

  code = args[1].strip().upper()
  try:
    amount = int(args[2])
    PROMO_CODES[code] = amount
    bot.reply_to(message, f"✅ Промокод **{code}** на `{amount}` попыток успешно создан!", parse_mode="Markdown")
  except Exception as e:
    bot.reply_to(message, f"❌ Ошибка: {e}")

@bot.message_handler(commands=["userinfo"])
def userinfo_command(message):
  if message.from_user.id != ADMIN_ID:
    return

  args = message.text.split()
  if len(args) < 2:
    bot.reply_to(message, "❌ Формат: `/userinfo ID`", parse_mode="Markdown")
    return

  try:
    target_id = int(args[1])
    if target_id not in USER_LIMITS:
      bot.reply_to(message, "❌ Данные пользователя не найдены в активной сессии памяти.")
      return

    u_data = USER_LIMITS[target_id]
    avail = DAILY_LIMIT + u_data["bonus"] - u_data["count"]
    info_text = (
        f"👤 **Информация о пользователе `{target_id}`:**\n\n"
        f"📅 Дата активности: `{u_data['date']}`\n"
        f"🔄 Использовано сегодня: `{u_data['count']}`\n"
        f"🎁 Бонусные попытки: `{u_data['bonus']}`\n"
        f"⭐ Доступно всего: `{max(0, avail)}`"
    )
    bot.reply_to(message, info_text, parse_mode="Markdown")
  except Exception as e:
    bot.reply_to(message, f"❌ Ошибка: {e}")

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

  elif data == "claim_daily":
    now = datetime.now()
    last_claim = DAILY_BONUS_TRACKER.get(user_id)

    if last_claim and (now - last_claim).total_seconds() < 86400:
      remaining_seconds = int(86400 - (now - last_claim).total_seconds())
      hours = remaining_seconds // 3600
      minutes = (remaining_seconds % 3600) // 60
      bot.answer_callback_query(
          call.id,
          f"⏳ Бонус уже получен! Следующий будет доступен через {hours} ч. {minutes} мин.",
          show_alert=True
      )
    else:
      DAILY_BONUS_TRACKER[user_id] = now
      user_data = get_user_data(user_id)
      user_data["bonus"] += 2  
      bot.answer_callback_query(call.id, "🎁 Успешно! Вам начислено +2 бонусные попытки.", show_alert=True)
      
      try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
      except:
        pass
      send_main_menu(call.message.chat.id, user_id, "🎁 Ежедневный бонус успешно получен (+2 попытки)!")

  elif data == "admin_panel":
    if user_id != ADMIN_ID:
      bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
      return

    total_users = len(REGISTERED_USERS)
    active_today = sum(1 for uid, d in USER_LIMITS.items() if d["date"] == date.today())
    
    admin_text = (
        f"👑 **Панель администратора**\n\n"
        f"👥 Всего пользователей: `{total_users}`\n"
        f"🟢 Активных сегодня: `{active_today}`\n"
        f"🎬 Всего генераций: `{TOTAL_GENERATIONS_COUNT}`\n"
        f"📦 Активных промокодов: `{len(PROMO_CODES)}`\n\n"
        f"📌 Команды: `/broadcast`, `/addbonus`, `/addpromo`, `/userinfo`"
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("📊 Обновить", callback_data="admin_panel"))
    markup.add(InlineKeyboardButton("🔙 В главное меню", callback_data="back_to_menu"))
    
    try:
      bot.edit_message_text(admin_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    except:
      pass
    bot.answer_callback_query(call.id)

  elif data == "back_to_menu":
    try:
      bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
      pass
    send_main_menu(call.message.chat.id, user_id, "👋 Главное меню:")
    bot.answer_callback_query(call.id)

  elif data.startswith("preset_"):
    USER_PRESETS[user_id] = data
    bot.answer_callback_query(call.id, "✅ Пресет сохранен!")
    
    markup = InlineKeyboardMarkup(row_width=5)
    markup.add(
        InlineKeyboardButton("1", callback_data="count_1"),
        InlineKeyboardButton("2", callback_data="count_2"),
        InlineKeyboardButton("3", callback_data="count_3"),
        InlineKeyboardButton("4", callback_data="count_4"),
        InlineKeyboardButton("5", callback_data="count_5"),
    )
    bot.edit_message_text(
        "🔢 Выбери количество уникальных копий:",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

  elif data.startswith("count_"):
    count = int(data.split("_")[1])
    USER_COUNTS[user_id] = count
    bot.answer_callback_query(call.id, f"✅ Выбрано копий: {count}")
    
    if user_id in USER_PENDING_MEDIA:
      media_message = USER_PENDING_MEDIA.pop(user_id)
      if media_message.content_type == "photo":
        Thread(target=process_photo_worker, args=(media_message, count)).start()
      else:
        Thread(target=process_video_uniq, args=(media_message, count)).start()

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
    markup.add(
        InlineKeyboardButton("🎁 Получить бонус", callback_data="claim_daily"),
        InlineKeyboardButton("⭐ Купить за Звезды", callback_data="buy_stars")
    )
    bot.reply_to(message, "❌ Лимит исчерпан. Забери ежедневный бонус или пополни баланс:", reply_markup=markup)
    return

  if message.content_type == "document" and not message.document.mime_type.startswith("video"):
    bot.reply_to(message, "❌ Пришли мне именно видеофайл.")
    return

  USER_PENDING_MEDIA[user_id] = message
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
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎁 Получить бонус", callback_data="claim_daily"),
        InlineKeyboardButton("⭐ Купить за Звезды", callback_data="buy_stars")
    )
    bot.reply_to(message, "❌ Лимит попыток исчерпан. Используй бонус или /promo:", reply_markup=markup)
    return

  USER_PENDING_MEDIA[user_id] = message
  markup = InlineKeyboardMarkup(row_width=5)
  markup.add(
      InlineKeyboardButton("1", callback_data="count_1"),
      InlineKeyboardButton("2", callback_data="count_2"),
      InlineKeyboardButton("3", callback_data="count_3"),
      InlineKeyboardButton("4", callback_data="count_4"),
      InlineKeyboardButton("5", callback_data="count_5"),
  )
  bot.reply_to(message, "🔢 Выбери количество уникальных копий для фото:", reply_markup=markup)

def process_photo_worker(message, count):
  global TOTAL_GENERATIONS_COUNT
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  
  user_data["count"] += 1
  msg = bot.reply_to(message, f"📥 Создаю {count} уникальных копий фото...")

  try:
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    rnd = random.randint(1000, 9999)
    input_path = f"source_img_{user_id}_{rnd}.jpg"
    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    for i in range(count):
      output_path = f"uniq_img_{user_id}_{rnd}_{i}.jpg"
      img = Image.open(input_path)
      width, height = img.size
      img = img.resize((width + random.choice([-1, 1]), height + random.choice([-1, 1])), Image.Resampling.LANCZOS)
      
      ImageEnhance.Brightness(img).enhance(random.uniform(0.98, 1.02))
      ImageEnhance.Contrast(img).enhance(random.uniform(0.98, 1.02)).save(output_path, "JPEG", quality=random.randint(92, 98))

      with open(output_path, "rb") as photo:
        bot.send_photo(message.chat.id, photo, caption=f"🖼 Копия №{i+1}")

      if os.path.exists(output_path):
        os.remove(output_path)
      TOTAL_GENERATIONS_COUNT += 1

    if os.path.exists(input_path):
      os.remove(input_path)
    
    bot.delete_message(message.chat.id, msg.id)
    send_main_menu(message.chat.id, user_id, f"✅ Успешно создано {count} копий фото!")

  except Exception as e:
    print(f"Photo error: {e}")
    bot.edit_message_text(f"❌ Ошибка обработки фото: {e}", message.chat.id, msg.id)

def process_video_uniq(message, count):
  global TOTAL_GENERATIONS_COUNT
  user_id = message.from_user.id
  user_data = get_user_data(user_id)
  
  user_data["count"] += 1

  preset_key = USER_PRESETS.get(user_id, "preset_medium")
  preset = PRESETS.get(preset_key, PRESETS["preset_medium"])

  msg = bot.reply_to(message, f"📥 Создаю {count} уникальных копий видео ({preset['name']})...")
  rnd = random.randint(1000, 9999)
  input_path = f"source_input_{user_id}_{rnd}.mp4"
  output_dir = "bot_ready"
  os.makedirs(output_dir, exist_ok=True)

  try:
    file_info = bot.get_file(message.video.file_id if message.video else message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open(input_path, "wb") as f:
      f.write(downloaded_file)

    for i in range(count):
      out_file = os.path.join(output_dir, f"uniq_video_{user_id}_{rnd}_{i}.mp4")
      
      speed = round(random.uniform(preset["speed_min"], preset["speed_max"]), 3)
      pts = round(1 / speed, 4)
      zoom = preset["zoom"]
      noise = preset["noise"]

      vf = f"setpts={pts}*PTS,scale=iw*{zoom}:ih*{zoom},crop=iw/{zoom}:ih/{zoom},noise=alls={noise}:allf=t"

      cmd = [
          "ffmpeg", "-y", "-ss", str(round(random.uniform(0.01, 0.08), 2)), "-i", input_path,
          "-map_metadata", "-1", "-metadata", "make=Apple", "-metadata", f"model=iPhone {random.choice(['14', '15', '16'])} Pro",
          "-vf", vf, "-af", f"atempo={speed}",
          "-c:v", "libx264", "-preset", "ultrafast", "-crf", str(random.randint(20, 23)),
          "-c:a", "aac", "-b:a", "128k", out_file
      ]

      subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

      with open(out_file, "rb") as vid:
        bot.send_video(message.chat.id, vid, caption=f"🎬 Уникальная копия №{i+1}", timeout=120)

      if os.path.exists(out_file):
        os.remove(out_file)
      TOTAL_GENERATIONS_COUNT += 1

    if os.path.exists(input_path):
      os.remove(input_path)
      
    bot.delete_message(message.chat.id, msg.id)
    send_main_menu(message.chat.id, user_id, f"✅ Успешно создано {count} копий видео!")

  except Exception as e:
    print(f"Video error: {e}")
    bot.edit_message_text(f"❌ Ошибка видео: {e}", message.chat.id, msg.id)

@bot.message_handler(func=lambda message: True)
def fallback_handler(message):
  send_main_menu(message.chat.id, message.from_user.id, "👋 Пришли видеофайл или фото для уникализации.")

if __name__ == "__main__":
  t = Thread(target=run_web)
  t.start()
  print("🤖 Бот успешно запущен со всеми функциями!")
  bot.infinity_polling(skip_pending=True)
