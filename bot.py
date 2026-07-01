Pahile import telebot
import csv
import io
import threading
import time
import os
from flask import Flask
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask('')

@app.route('/')
def home():
    return "Quiz Bot is 24x7 Awake and Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = "8943398504:AAGIjt1WrTe5wivSDU9tqtWSO97DM9FN2iQ" 
bot = telebot.TeleBot(BOT_TOKEN)

# Global data storage
uploaded_quizzes = {}
user_sessions = {}
temp_csv_data = {}
revision_configs = {} # Store user revision settings

# Initialize Background Scheduler for Revision Mode
scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.start()

def set_bot_commands():
    try:
        commands = [
            BotCommand("start", "🤖 Bot ko shuru karein"),
            BotCommand("csv_to_quiz", "📁 CSV file se quiz banayein"),
            BotCommand("quiz", "🎯 Active Quiz Panel open karein")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Menu error: {e}")

@bot.message_handler(commands=['start'])
def start_message(message):
    chat_id = message.chat.id
    text_args = message.text.split()
    
    if len(text_args) > 1 and text_args[1].startswith('startquiz_'):
        quiz_id = text_args[1].replace('startquiz_', '')
        if quiz_id in uploaded_quizzes:
            trigger_quiz_start(chat_id, quiz_id)
            return
        else:
            bot.send_message(chat_id, "⚠️ Yeh quiz abhi available nahi hai ya expire ho chuka hai.")
            return

    welcome_text = (
        "👋 *Welcome to the Smart Quiz Bot!*\n\n"
        "Apni CSV file upload karke aap professional standard quiz bana sakte hain.\n\n"
        "⚙️ *Kaise use karein:*\n"
        "1. `/csv_to_quiz` par click karein.\n"
        "2. Apni `.csv` file bot ko bhejein.\n"
        "3. Quiz ka ek Title (Naam) type karke bhejein."
    )
    bot.send_message(chat_id, welcome_text, parse_mode="Markdown")

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
            bot.send_message(chat_id, "❌ CSV file read karne mein dikkat aayi.")
            return

        temp_csv_data[chat_id] = questions_list
        msg = bot.send_message(chat_id, f"📝 *Sawal process ho gaye hain! (Total: {len(questions_list)})*\n\nAb is Quiz ka ek **Title (Naam)** type karke bhejein.", parse_mode="Markdown")
        bot.register_next_step_handler(msg, save_quiz_title)

    except Exception as e:
        bot.send_message(chat_id, f"❌ File process karne mein error aaya: {str(e)}")

def save_quiz_title(message):
    chat_id = message.chat.id
    quiz_title = message.text.strip()
    
    if chat_id not in temp_csv_data:
        bot.send_message(chat_id, "⚠️ Kuch galat hua. Kripya file dobara upload karein.")
        return
        
    quiz_id = f"q_{chat_id}"
    uploaded_quizzes[quiz_id] = {
        "title": quiz_title,
        "questions": temp_csv_data[chat_id],
        "creator": chat_id
    }
    del temp_csv_data[chat_id]
    
    # Selection Screen between Standard and AUTO-QUIZ
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⚙️ Standard Mode", callback_data=f"mode_standard_{quiz_id}"))
    markup.add(InlineKeyboardButton("🤖 AUTO-QUIZ MODE", callback_data=f"mode_auto_{quiz_id}"))
    
    bot.send_message(
        chat_id, 
        f"✅ *Quiz Ka Naam Saved:* \"{quiz_title}\"\n\nAb select karein ki aap ise kis mode mein chalana chahte hain:", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

# Callback handler for Main Modes
@bot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def handle_main_modes(call):
    chat_id = call.message.chat.id
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
        
    if call.data.startswith("mode_standard_"):
        quiz_id = call.data.replace('mode_standard_', '')
        show_quiz_card(chat_id, quiz_id)
        
    elif call.data.startswith("mode_auto_"):
        quiz_id = call.data.replace('mode_auto_', '')
        
        # Sub-menu inside AUTO-QUIZ
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("📝 Practice Mode", callback_data=f"practice_menu_{quiz_id}"))
        markup.add(InlineKeyboardButton("🔒 Live Mode (Under Dev)", callback_data="live_mode_dev"))
        
        bot.send_message(
            chat_id,
            "🤖 *AUTO-QUIZ MODE SELECTION*\n\nNiche diye gaye options mein se chunein:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

@bot.callback_query_handler(func=lambda call: call.data == "live_mode_dev")
def live_mode_dev_alert(call):
    bot.answer_callback_query(call.id, "Live Mode abhi under development hai! Kripya Practice Mode ka upyog karein.", show_alert=True)

# Callback handler for Practice Sub-Menu
@bot.callback_query_handler(func=lambda call: call.data.startswith('practice_menu_'))
def handle_practice_menu(call):
    chat_id = call.message.chat.id
    quiz_id = call.data.replace('practice_menu_', '')
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
        
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⚡ Flash Quiz (No Timer)", callback_data=f"flash_run_{quiz_id}"))
    markup.add(InlineKeyboardButton("🔄 Revision Mode", callback_data=f"revision_setup_{quiz_id}"))
    
    bot.send_message(
        chat_id,
        "📝 *PRACTICE MODE OPTIONS*\n\n"
        "⚡ *Flash Quiz:* Saare sawal bina timer ke ek sath flash honge.\n"
        "🔄 *Revision Mode:* Fixed daily limit aur daily time par automated test chalega.",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- ⚡ FLASH QUIZ FUNCTIONALITY ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('flash_run_'))
def run_flash_quiz(call):
    chat_id = call.message.chat.id
    quiz_id = call.data.replace('flash_run_', '')
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
        
    if quiz_id not in uploaded_quizzes:
        bot.send_message(chat_id, "⚠️ Quiz data nahi mila.")
        return
        
    questions = uploaded_quizzes[quiz_id]["questions"]
    title = uploaded_quizzes[quiz_id]["title"]
    
    bot.send_message(chat_id, f"⚡ *Flash Quiz Shuru!* (Topic: `{title}`)\nSaare sawal niche aa rahe hain. Bina timer ke aaram se solve karein: 👇", parse_mode="Markdown")
    
    # Instantly dispatch all polls without open_period timer
    for idx, q_data in enumerate(questions):
        try:
            bot.send_poll(
                chat_id=chat_id,
                question=f"❓ {q_data['question']}"[:250],
                options=q_data["options"][:100],
                type='quiz',
                correct_option_id=q_data["correct"],
                is_anonymous=False
            )
            time.sleep(0.5) # Smooth distribution gap
        except:
            pass

# --- 🔄 REVISION MODE SETUP ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('revision_setup_'))
def setup_revision_mode(call):
    chat_id = call.message.chat.id
    quiz_id = call.data.replace('revision_setup_', '')
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
        
    revision_configs[chat_id] = {"quiz_id": quiz_id}
    msg = bot.send_message(chat_id, "🕒 *Revision Ka Time (IST) Set Karein!*\n\nKripya daily test bhejne ka samay type karein. Format -> `HH:MM` (Jaise raat ke 9 baje ke liye: `21:00` ya subah 9 baje ke liye `09:00`):")
    bot.register_next_step_handler(msg, process_revision_time)

def process_revision_time(message):
    chat_id = message.chat.id
    time_str = message.text.strip()
    
    try:
        datetime.strptime(time_str, "%H:%M") # Format validation
        revision_configs[chat_id]["time"] = time_str
        msg = bot.send_message(chat_id, "🔢 *Daily Limit Set Karein!*\n\nRozana revision mein kitne questions bhejne hain? Ek sankhya (number) bheinjein (e.g., `5`, `10`, `15`):")
        bot.register_next_step_handler(msg, process_revision_limit)
    except:
        msg = bot.send_message(chat_id, "❌ Galat format! Kripya sahi format `HH:MM` (e.g. `21:30`) mein hi samay bhejein:")
        bot.register_next_step_handler(msg, process_revision_time)

def process_revision_limit(message):
    chat_id = message.chat.id
    limit_str = message.text.strip()
    
    if not limit_str.isdigit() or int(limit_str) <= 0:
        msg = bot.send_message(chat_id, "❌ Kripya ek valid number bhejein (Jaise 5 ya 10):")
        bot.register_next_step_handler(msg, process_revision_limit)
        return
        
    limit = int(limit_str)
    revision_configs[chat_id]["limit"] = limit
    revision_configs[chat_id]["current_pointer"] = 0 # Track which question index to send next
    
    config = revision_configs[chat_id]
    quiz_id = config["quiz_id"]
    quiz_title = uploaded_quizzes[quiz_id]["title"]
    r_time = config["time"]
    
    # Schedule the Automated Cron Job for this user
    hour, minute = map(int, r_time.split(":"))
    job_id = f"rev_{chat_id}"
    
    # If a job already exists for this user, remove it first
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    scheduler.add_job(
        send_daily_revision, 
        'cron', 
        hour=hour, 
        minute=minute, 
        id=job_id, 
        args=[chat_id]
    )
    
    success_text = (
        f"✅ *Revision Mode successfully activated!*\n\n"
        f"📌 *Quiz:* `{quiz_title}`\n"
        f"🕒 *Daily Time:* `{r_time} IST`\n"
        f"📊 *Daily Question Limit:* `{limit}`\n\n"
        f"Bot rozana is samay par automatic questions bhejta rahega."
    )
    bot.send_message(chat_id, success_text, parse_mode="Markdown")

def send_daily_revision(chat_id):
    config = revision_configs.get(chat_id)
    if not config: return
    
    quiz_id = config["quiz_id"]
    if quiz_id not in uploaded_quizzes: return
    
    questions = uploaded_quizzes[quiz_id]["questions"]
    pointer = config["current_pointer"]
    limit = config["limit"]
    title = uploaded_quizzes[quiz_id]["title"]
    
    if pointer >= len(questions):
        bot.send_message(chat_id, f"🔄 *Revision Complete!* `{title}` ke saare questions pure ho gaye hain. Naya schedule karne ke liye naya CSV upload karein.")
        scheduler.remove_job(f"rev_{chat_id}")
        return

    bot.send_message(chat_id, f"🔄 *Today's Revision Test Live!* (Topic: `{title}`)\nTaiyar ho jaiye: 👇", parse_mode="Markdown")
    
    end_pointer = min(pointer + limit, len(questions))
    for i in range(pointer, end_pointer):
        q_data = questions[i]
        try:
            bot.send_poll(
                chat_id=chat_id,
                question=f"🔄 {q_data['question']}"[:250],
                options=q_data["options"][:100],
                type='quiz',
                correct_option_id=q_data["correct"],
                is_anonymous=False
            )
            time.sleep(1)
        except:
            pass
            
    config["current_pointer"] = end_pointer
    revision_configs[chat_id] = config

# --- ⚙️ STANDARD MODE CORE FUNCTIONALITY ---
def show_quiz_card(chat_id, quiz_id):
    quiz_data = uploaded_quizzes[quiz_id]
    title = quiz_data["title"]
    total_q = len(quiz_data["questions"])
    bot_username = bot.get_me().username
    
    card_text = (
        f"🎲 *Quiz '{title}'*\n\n"
        f"📝 *{total_q} questions*\n"
        f"⏱ *30 sec* per question\n\n"
        f"👥 Tap on buttons below to play!"
    )
    
    markup = InlineKeyboardMarkup()
    btn_start = InlineKeyboardButton("🏁 Start this quiz", callback_data=f"runquiz_{quiz_id}")
    
    share_url = f"https://t.me/{bot_username}?start=startquiz_{quiz_id}"
    btn_group = InlineKeyboardButton("👥 Start quiz in group", url=f"https://t.me/share/url?url={share_url}&text=Hey! Join this Quiz on Group:")
    btn_share = InlineKeyboardButton("🔗 Share quiz", url=f"https://t.me/share/url?url={share_url}&text=Hey! Try this awesome quiz: {title}")
    
    markup.add(btn_start)
    markup.add(btn_group)
    markup.add(btn_share)
    
    bot.send_message(chat_id, card_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('runquiz_'))
def handle_run_quiz_click(call):
    chat_id = call.message.chat.id
    quiz_id = call.data.replace('runquiz_', '')
    try:
        bot.delete_message(chat_id, call.message.message_id)
    except:
        pass
    trigger_quiz_start(chat_id, quiz_id)

def trigger_quiz_start(chat_id, quiz_id):
    if quiz_id not in uploaded_quizzes:
        bot.send_message(chat_id, "⚠️ Quiz data nahi mila.")
        return
        
    user_sessions[chat_id] = {"quiz_id": quiz_id, "current_q": 0, "score": 0, "wrong": 0}
    quiz_title = uploaded_quizzes[quiz_id]["title"]
    
    bot.send_message(chat_id, "🚀 *Quiz shuru ho raha hai...*")
    time.sleep(1.5)
    bot.send_message(chat_id, f"📋 *Topic:* `{quiz_title}`\n\nAll the best! 👍", parse_mode="Markdown")
    time.sleep(2)
    send_question(chat_id)

def send_question(chat_id):
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    
    q_index = user_data["current_q"]
    quiz_id = user_data["quiz_id"]
    questions = uploaded_quizzes[quiz_id]["questions"]
    
    if q_index >= len(questions):
        show_result(chat_id)
        return
        
    q_data = questions[q_index]
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
    except Exception as e:
        user_data["current_q"] += 1
        user_data["wrong"] += 1
        user_sessions[chat_id] = user_data
        send_question(chat_id)

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    chat_id = poll_answer.user.id
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    
    q_index = user_data["current_q"]
    quiz_id = user_data["quiz_id"]
    questions = uploaded_quizzes[quiz_id]["questions"]
    
    if q_index < len(questions):
        q_data = questions[q_index]
        if poll_answer.option_ids[0] == q_data["correct"]: 
            user_data["score"] += 1
        else:
            user_data["wrong"] += 1
            
    user_data["current_q"] += 1
    user_sessions[chat_id] = user_data
    time.sleep(1.5)
    send_question(chat_id)

def show_result(chat_id):
    user_data = user_sessions.get(chat_id)
    if not user_data: return
    
    score = user_data["score"]
    quiz_id = user_data["quiz_id"]
    title = uploaded_quizzes[quiz_id]["title"]
    total = len(uploaded_quizzes[quiz_id]["questions"])
    
    correct = score
    wrong = total - correct
    accuracy = int((correct / total) * 100) if total > 0 else 0
    
    result_text = (
        f"🏁 *Quiz Poora Hua!*\n\n"
        f"📌 *Topic:* `{title}`\n"
        f"📊 *Aapka Score Card:*\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"✅ *Sahi (Correct):* `{correct}`\n"
        f"❌ *Galat (Incorrect):* `{wrong}`\n"
        f"🎯 *Accuracy (सटीकता):* `{accuracy}%`\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    
    bot.send_message(chat_id, result_text, parse_mode="Markdown")
    if chat_id in user_sessions: 
        del user_sessions[chat_id]

@bot.message_handler(commands=['quiz'])
def menu_quiz_call(message):
    chat_id = message.chat.id
    quiz_id = f"q_{chat_id}"
    if quiz_id in uploaded_quizzes:
        show_quiz_card(chat_id, quiz_id)
    else:
        bot.send_message(chat_id, "⚠️ Mujhe koi active quiz nahi mila. Pehle ek file bhejiye! `/csv_to_quiz`")

if __name__ == "__main__":
    set_bot_commands()
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
