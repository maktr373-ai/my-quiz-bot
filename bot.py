import telebot
import csv
import io
import threading
import time
import os
from flask import Flask
from telebot.types import BotCommand

app = Flask('')

@app.route('/')
def home():
    return "Quiz Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = "8943398504:AAGIjt1WrTe5wivSDU9tqtWSO97DM9FN2iQ" 
bot = telebot.TeleBot(BOT_TOKEN)

uploaded_quizzes = {}
user_sessions = {}

def set_bot_commands():
    try:
        commands = [
            BotCommand("start", "🤖 Bot ko shuru karein"),
            BotCommand("csv_to_quiz", "📁 CSV file se quiz banayein"),
            BotCommand("quiz", "🎯 Upload kiya hua Quiz shuru karein")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Menu error: {e}")

@bot.message_handler(commands=['start'])
def start_message(message):
    welcome_text = (
        "👋 *Welcome to the Smart Quiz Bot!*\n\n"
        "Apni CSV file upload karke aap test generate kar sakte hain.\n\n"
        "⚙️ *Kaise use karein:*\n"
        "1. `/csv_to_quiz` par click karein.\n"
        "2. Apni `.csv` file bot ko bhejein.\n"
        "3. `/quiz` daba kar test shuru karein!"
    )
    bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(commands=['csv_to_quiz'])
def ask_for_csv(message):
    instructions = (
        "📁 *Apni CSV File send karein!*\n\n"
        "Kripya check karein ki aapki CSV file ke top row mein `question`, `option1`, `option2`, `option3`, `option4`, aur `correct` columns hon."
    )
    bot.send_message(message.chat.id, instructions, parse_mode="Markdown")

@bot.message_handler(content_types=['document'])
def handle_csv_upload(message):
    chat_id = message.chat.id
    if not message.document.file_name.endswith('.csv'):
        bot.send_message(chat_id, "❌ Galti! Kripya sirf `.csv` format wali file hi upload karein.")
        return

    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        csv_text = downloaded_file.decode('utf-8-sig', errors='ignore')
        lines = [line.strip() for line in csv_text.split('\n') if line.strip()]
        
        if not lines:
            bot.send_message(chat_id, "❌ File khali hai.")
            return
            
        questions_list = []
        start_idx = 1 if 'question' in lines[0].lower() else 0
        
        for line in lines[start_idx:]:
            parts = list(csv.reader([line]))[0]
            if len(parts) >= 6:
                q_text = parts[0].strip()
                opts = [p.strip() for p in parts[1:5] if p.strip()]
                ans_str = parts[5].strip()
                
                if len(opts) < 2:
                    continue
                    
                correct_idx = 0
                for idx, o in enumerate(opts):
                    if ans_str.lower() in o.lower() or o.lower() in ans_str.lower():
                        correct_idx = idx
                        break
                try:
                    if ans_str.isdigit() and 1 <= int(ans_str) <= len(opts):
                        correct_idx = int(ans_str) - 1
                except:
                    pass

                questions_list.append({
                    "question": q_text,
                    "options": opts,
                    "correct": correct_idx
                })
        
        if not questions_list:
            bot.send_message(chat_id, "❌ CSV file read karne mein dikkat aayi. Kripya file check karein.")
            return

        uploaded_quizzes[chat_id] = questions_list
        bot.send_message(chat_id, f"✅ *Zabardast!* Aapke {len(questions_list)} sawal load ho chuke hain.\n\nAb quiz shuru karne ke liye `/quiz` type karein!", parse_mode="Markdown")

    except Exception as e:
        bot.send_message(chat_id, f"❌ File process karne mein error aaya: {str(e)}")

@bot.message_handler(commands=['quiz'])
def start_uploaded_quiz(message):
    chat_id = message.chat.id
    if chat_id not in uploaded_quizzes or not uploaded_quizzes[chat_id]:
        bot.send_message(chat_id, "⚠️ Pehle ek CSV file bhejiye! `/csv_to_quiz` daba kar tareeka dekhein.")
        return
    
    user_sessions[chat_id] = {"current_q": 0, "score": 0, "answered": False}
    bot.send_message(chat_id, "🎯 *Quiz shuru ho raha hai!*", parse_mode="Markdown")
    send_question(chat_id)

def send_question(chat_id):
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    
    q_index = user_data["current_q"]
    questions = uploaded_quizzes[chat_id]
    
    if q_index >= len(questions):
        show_result(chat_id)
        return
        
    q_data = questions[q_index]
    user_data["answered"] = False
    
    try:
        # Explanation parameter ko poori tarah hata diya gaya hai
        bot.send_poll(
            chat_id=chat_id,
            question=q_data["question"][:250], 
            options=q_data["options"][:100],
            type='quiz',
            correct_option_id=q_data["correct"],
            open_period=20,
            is_anonymous=False
        )
        user_sessions[chat_id] = user_data
    except Exception as e:
        user_data["current_q"] += 1
        user_sessions[chat_id] = user_data
        send_question(chat_id)

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    chat_id = poll_answer.user.id
    user_data = user_sessions.get(chat_id)
    if not user_data or chat_id not in uploaded_quizzes: return
    
    user_data["answered"] = True
    q_index = user_data["current_q"]
    
    if q_index < len(uploaded_quizzes[chat_id]):
        q_data = uploaded_quizzes[chat_id][q_index]
        if poll_answer.option_ids[0] == q_data["correct"]: 
            user_data["score"] += 1
            
    user_data["current_q"] += 1
    user_sessions[chat_id] = user_data
    time.sleep(1.5)
    send_question(chat_id)

def show_result(chat_id):
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    score = user_data["score"]
    total = len(uploaded_quizzes[chat_id])
    bot.send_message(chat_id, f"🏁 *Quiz Poora Hua!*\n📊 *Aapka Final Score:* {score}/{total}", parse_mode="Markdown")
    if chat_id in user_sessions: del user_sessions[chat_id]

if __name__ == "__main__":
    set_bot_commands()
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
