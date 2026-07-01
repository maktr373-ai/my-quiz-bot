import telebot
import time
import threading
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8943398504:AAGIjt1WrTe5wivSDU9tqtWSO97DM9FN2iQ" 
bot = telebot.TeleBot(BOT_TOKEN)

QUIZ_DATA = {
    "gk": [
        {"question": "1. Bharat ki Rajdhani kya hai?", "options": ["Mumbai", "Kolkata", "New Delhi", "Chennai"], "correct": 2, "explanation": "New Delhi hai."},
        {"question": "2. Ek saal mein kitne din hote hain?", "options": ["360", "365", "370", "355"], "correct": 1, "explanation": "365 din hote hain."}
    ],
    "science": [
        {"question": "1. Paani (Water) ka chemical formula kya hai?", "options": ["CO2", "H2O", "O2", "NaCl"], "correct": 1, "explanation": "H2O hota hai."},
        {"question": "2. Humare shareer ki sabse badi haddi kaun si hai?", "options": ["Femur", "Stapes", "Skull", "Spine"], "correct": 0, "explanation": "Femur hai."}
    ]
}

user_sessions = {}

def set_bot_commands():
    try:
        commands = [
            BotCommand("start", "🤖 Bot ko shuru karein"),
            BotCommand("quiz", "🎯 Naya Quiz shuru karein")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Menu error: {e}")

@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id, "👋 *Welcome!* \n\nQuiz khelne ke liye `/quiz` type karein.", parse_mode="Markdown")

@bot.message_handler(commands=['quiz'])
def choose_category(message):
    chat_id = message.chat.id
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🌍 General Knowledge (GK)", callback_data="cat_gk"))
    markup.add(InlineKeyboardButton("🧪 Science", callback_data="cat_science"))
    bot.send_message(chat_id, "📚 *Pehle ek Category chunein:*", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def start_category_quiz(call):
    chat_id = call.message.chat.id
    category = call.data.split("_")[1]
    user_sessions[chat_id] = {"category": category, "current_q": 0, "score": 0, "answered": False, "poll_id": None}
    bot.delete_message(chat_id, call.message.message_id)
    bot.send_message(chat_id, f"🎯 *Quiz shuru! Har sawal ke liye 15 seconds hain.*", parse_mode="Markdown")
    send_question(chat_id)

def send_question(chat_id):
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    category = user_data["category"]
    q_index = user_data["current_q"]
    questions = QUIZ_DATA[category]
    if q_index >= len(questions):
        show_result(chat_id)
        return
    q_data = questions[q_index]
    user_data["answered"] = False
    poll = bot.send_poll(chat_id=chat_id, question=q_data["question"], options=q_data["options"], type='quiz', correct_option_id=q_data["correct"], explanation=q_data["explanation"], open_period=15, is_anonymous=False)
    user_data["poll_id"] = poll.poll.id
    user_sessions[chat_id] = user_data
    threading.Thread(target=start_timer_check, args=(chat_id, q_index)).start()

def start_timer_check(chat_id, q_index):
    time.sleep(16)
    user_data = user_sessions.get(chat_id)
    if user_data and user_data["current_q"] == q_index and not user_data["answered"]:
        bot.send_message(chat_id, "⏰ *Time Out!* Aapne samay par jawab nahi diya.")
        user_data["current_q"] += 1
        user_sessions[chat_id] = user_data
        send_question(chat_id)

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    chat_id = poll_answer.user.id
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    user_data["answered"] = True
    category = user_data["category"]
    q_index = user_data["current_q"]
    q_data = QUIZ_DATA[category][q_index]
    if poll_answer.option_ids[0] == q_data["correct"]: user_data["score"] += 1
    user_data["current_q"] += 1
    user_sessions[chat_id] = user_data
    time.sleep(1.5)
    send_question(chat_id)

def show_result(chat_id):
    user_data = user_sessions.get(chat_id)
    category = user_data["category"]
    score = user_data["score"]
    total = len(QUIZ_DATA[category])
    bot.send_message(chat_id, f"🏁 *Quiz Poora Hua!*\n📊 *Score:* {score}/{total}", parse_mode="Markdown")
    if chat_id in user_sessions: del user_sessions[chat_id]

set_bot_commands()
print("Bot ready...")
bot.infinity_polling()
  
