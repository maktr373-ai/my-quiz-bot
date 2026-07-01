import telebot
import csv
import io
import threading
import time
import os
from flask import Flask
from telebot.types import BotCommand

# Render Port issue fix karne ke liye web server
app = Flask('')

@app.route('/')
def home():
    return "Quiz Bot is running successfully!"

def run_flask():
    # Render dynamic port deta hai, agar na mile toh default 10000 use karega
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

def parse_correct_option(val, options_count=4):
    if val is None:
        return 0
    clean = str(val).strip().lower().replace('.', '').replace(')', '')
    
    abc_map = {'a': 0, 'b': 1, 'c': 2, 'd': 3, 'e': 4, 'f': 5}
    if clean in abc_map:
        return abc_map[clean]
        
    roman_map = {'i': 0, 'ii': 1, 'iii': 2, 'iv': 3, 'v': 4, 'vi': 5}
    if clean in roman_map:
        return roman_map[clean]
        
    try:
        num = int(clean)
        if 1 <= num <= options_count:
            return num - 1
        if 0 <= num < options_count:
            return num
    except ValueError:
        pass
        
    return 0

@bot.message_handler(commands=['start'])
def start_message(message):
    welcome_text = (
        "👋 *Welcome to the Ultra-Flexible Quiz Bot!*\n\n"
        "Ab aap kisi bhi format ki CSV file upload kar sakte hain. Bot options aur sahi jawab (A/a, 1, i) ko khud samajh lega!\n\n"
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
        "Aapki CSV file mein yeh columns hone chahiye:\n"
        "`question,option1,option2,option3,option4,correct`\n\n"
        "🔥 *Flexibility:* `correct` column mein kuch bhi likhein:\n"
        "• Letters: *A, B, C, D* ya *a, b, c, d*\n"
        "• Numbers: *1, 2, 3, 4*\n"
        "• Roman: *I, II, III, IV*"
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
        csv_stream = io.StringIO(csv_text)
        reader = csv.DictReader(csv_stream)
        
        questions_list = []
        for row in reader:
            clean_row = {str(k).strip().lower(): v for k, v in row.items() if k}
            
            q_text = clean_row.get('question') or clean_row.get('questions') or clean_row.get('sawal')
            if not q_text:
                continue
                
            options = []
            for i in range(1, 7):
                opt = clean_row.get(f'option{i}') or clean_row.get(f'option_{i}') or clean_row.get(f'opt{i}')
                if opt and str(opt).strip():
                    options.append(str(opt).strip())
            
            if len(options) < 2:
                continue
                
            correct_val = clean_row.get('correct') or clean_row.get('answer') or clean_row.get('ans')
            correct_index = parse_correct_option(correct_val, len(options))
            
            explanation = clean_row.get('explanation') or clean_row.get('exp') or "Sahi jawab!"
            
            questions_list.append({
                "question": str(q_text).strip(),
                "options": options,
                "correct": correct_index,
                "explanation": str(explanation).strip()
            })
        
        if not questions_list:
            bot.send_message(chat_id, "❌ CSV file mein koi sahi data nahi mila.")
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
    bot.send_message(chat_id, "🎯 *Quiz shuru ho raha hai! Har sawal ke liye 15 seconds hain.*", parse_mode="Markdown")
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
        poll = bot.send_poll(
            chat_id=chat_id,
            question=q_data["question"],
            options=q_data["options"],
            type='quiz',
            correct_option_id=q_data["correct"],
            explanation=q_data["explanation"],
            open_period=15,
            is_anonymous=False
        )
        user_sessions[chat_id] = user_data
        threading.Thread(target=start_timer_check, args=(chat_id, q_index)).start()
    except Exception as e:
        user_data["current_q"] += 1
        user_sessions[chat_id] = user_data
        send_question(chat_id)

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
    # Background thread mein Flask ko run karna taaki Render port active rahe
    threading.Thread(target=run_flask, daemon=True).start()
    print("Flexible Quiz Bot with Port Fixer is ready...")
    bot.infinity_polling()
