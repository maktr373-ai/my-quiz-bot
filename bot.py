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
temp_csv_data = {}

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
        "3. Quiz ka ek Title (Naam) type karke bhejein.\n"
        "4. `/quiz` daba kar test shuru karein!"
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
        csv_stream = io.StringIO(csv_text.strip())
        
        try:
            dialect = csv.Sniffer().sniff(csv_text[:2000])
            if dialect.delimiter in [',', '\t', ';']:
                reader = csv.reader(csv_stream, dialect)
            else:
                reader = csv.reader(csv_stream, delimiter=',')
        except:
            reader = csv.reader(csv_stream, delimiter=',')

        rows = list(reader)
        if not rows:
            bot.send_message(chat_id, "❌ File khali hai.")
            return
            
        questions_list = []
        first_row_str = "".join(rows[0]).lower()
        start_idx = 1 if ('question' in first_row_str or 'option' in first_row_str) else 0
        
        for row in rows[start_idx:]:
            row = [item.strip() for item in row if item.strip()]
            
            if len(row) >= 6:
                q_text = row[0]
                opts = row[1:5]
                ans_str = row[5]
            elif len(row) > 6:
                ans_str = row[-1]
                opts = row[-5:-1]
                q_text = ", ".join(row[:-5])
            else:
                continue
                
            correct_idx = 0
            for idx, o in enumerate(opts):
                if ans_str.lower() in o.lower() or o.lower() in ans_str.lower():
                    correct_idx = idx
                    break
            try:
                if ans_str.isdigit():
                    num = int(ans_str)
                    if 1 <= num <= len(opts):
                        correct_idx = num - 1
                    elif 0 <= num < len(opts):
                        correct_idx = num
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

        temp_csv_data[chat_id] = questions_list
        msg = bot.send_message(chat_id, f"📝 *Sawal process ho gaye hain! (Total: {len(questions_list)})*\n\nAb is Quiz ka ek **Title (Naam)** type karke bhejein, jaise: `Science Quiz`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_quiz_title)

    except Exception as e:
        bot.send_message(chat_id, f"❌ File process karne mein error aaya: {str(e)}")

def save_quiz_title(message):
    chat_id = message.chat.id
    quiz_title = message.text.strip()
    
    if chat_id not in temp_csv_data:
        bot.send_message(chat_id, "⚠️ Kuch galat hua. Kripya file dobara upload karein.")
        return
        
    uploaded_quizzes[chat_id] = {
        "title": quiz_title,
        "questions": temp_csv_data[chat_id]
    }
    del temp_csv_data[chat_id]
    
    bot.send_message(
        chat_id, 
        f"✅ *Zabardast!* Quiz ka naam *\"{quiz_title}\"* set ho gaya hai.\n\nAb test shuru karne ke liye `/quiz` type karein!", 
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['quiz'])
def start_uploaded_quiz(message):
    chat_id = message.chat.id
    if chat_id not in uploaded_quizzes or not uploaded_quizzes[chat_id]["questions"]:
        bot.send_message(chat_id, "⚠️ Pehle ek CSV file bhejiye! `/csv_to_quiz` daba kar tareeka dekhein.")
        return
    
    user_sessions[chat_id] = {"current_q": 0, "score": 0, "answered": False}
    quiz_title = uploaded_quizzes[chat_id]["title"]
    
    # 1. Sabse pehle message: Quiz shuru ho raha hai
    bot.send_message(chat_id, "🚀 *Quiz shuru ho raha hai...*", parse_mode="Markdown")
    time.sleep(1.5) # Thoda sa gap taaki ek ke baad ek aaye
    
    # 2. Uske baad naya message: Sirf Title
    bot.send_message(chat_id, f"📋 *Topic:* `{quiz_title}`\n\nAll the best! 👍", parse_mode="Markdown")
    time.sleep(2) # Students ko title dekhne ka time milega
    
    # 3. Phir automatic quiz start ho jayega
    send_question(chat_id)

def send_question(chat_id):
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    
    q_index = user_data["current_q"]
    quiz_data = uploaded_quizzes[chat_id]
    questions = quiz_data["questions"]
    
    if q_index >= len(questions):
        show_result(chat_id)
        return
        
    q_data = questions[q_index]
    user_data["answered"] = False
    
    question_text = f"❓ {q_data['question']}"
    
    try:
        bot.send_poll(
            chat_id=chat_id,
            question=question_text[:250], 
            options=q_data["options"][:100],
            type='quiz',
            correct_option_id=q_data["correct"],
            open_period=30, 
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
    questions = uploaded_quizzes[chat_id]["questions"]
    
    if q_index < len(questions):
        q_data = questions[q_index]
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
    questions = uploaded_quizzes[chat_id]["questions"]
    title = uploaded_quizzes[chat_id]["title"]
    total = len(questions)
    
    bot.send_message(
        chat_id, 
        f"🏁 *Quiz Poora Hua!*\n📌 *Topic:* `{title}`\n📊 *Aapka Final Score:* {score}/{total}", 
        parse_mode="Markdown"
    )
    if chat_id in user_sessions: del user_sessions[chat_id]

if __name__ == "__main__":
    set_bot_commands()
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
