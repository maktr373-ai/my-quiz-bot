import os
import sqlite3
import csv
import io
import random
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

# --- BOT CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8943398504:AAGIjt1WrTe5wivSDU9tqtWSO97DM9FN2iQ")
bot = telebot.TeleBot(BOT_TOKEN)

# Background Scheduler for handling Custom Time/Date triggers
from apscheduler.schedulers.background import BackgroundScheduler
scheduler = BackgroundScheduler()
scheduler.start()

DB_NAME = "quiz_revision.db"

# --- DATABASE ENGINE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # 1. Table for Quizzes meta info
    cursor.execute('''CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        created_at TEXT
    )''')
    
    # 2. Table for Quiz Questions
    cursor.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        quiz_id INTEGER,
        question TEXT,
        option_a TEXT,
        option_b TEXT,
        option_c TEXT,
        option_d TEXT,
        correct_option TEXT,
        FOREIGN KEY(quiz_id) REFERENCES quizzes(id)
    )''')
    
    # 3. No-Repeat tracking table (Stores seen question per user)
    cursor.execute('''CREATE TABLE IF NOT EXISTS seen_questions (
        user_id INTEGER,
        question_id INTEGER,
        PRIMARY KEY (user_id, question_id)
    )''')
    
    # 4. User Revision Scheduler Table
    cursor.execute('''CREATE TABLE IF NOT EXISTS revision_schedules (
        user_id INTEGER,
        category TEXT,
        start_date TEXT,
        run_time TEXT,
        daily_limit INTEGER,
        status TEXT DEFAULT 'Running',
        PRIMARY KEY (user_id, category)
    )''')
    
    conn.commit()
    conn.close()

init_db()

# Target Exam Categories
CATEGORIES = [
    "BIO", "PHY", "CHEMISTRY", "HISTORY", "GEOGRAPHY", 
    "ECONOMIC", "POLITY", "HINDI", "ENGLISH", "MATHS", "CURRENT AFFAIRS"
]

user_data = {}
active_normal_quiz = {}

# --- SET AUTOMATIC TELEGRAM MENU BUTTONS ---
def set_bot_menu():
    commands = [
        BotCommand("start", "🤖 Bot ko shuru karein"),
        BotCommand("csv_to_quiz", "📁 CSV file se quiz banayein"),
        BotCommand("quiz", "🎯 Normal Practice Mode open karein"),
        BotCommand("hama_revision", "📚 HAMA REVISION Mode open karein") # Naya Menu Option!
    ]
    bot.set_my_commands(commands)

try:
    set_bot_menu()
except Exception as e:
    print(f"Error setting menu: {e}")


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(
        message.chat.id,
        "👋 Swagat hai bhai! Aapka advance Quiz aur Revision system ready hai.\n\n"
        "Niche left side mein **Menu Button** par click karke aap direct options select kar sakte hain:\n"
        "1. `/csv_to_quiz` - New File Upload\n"
        "2. `/quiz` - Normal Practice\n"
        "3. `/hama_revision` - Advanced Revision"
    )

# --- CSV FILE INPUT FLOW ---
@bot.message_handler(commands=['csv_to_quiz'])
def ask_for_file_upload(message):
    bot.send_message(message.chat.id, "📥 Kripya apni `.csv` quiz file yahan upload (attach) karke bhejein:")

@bot.message_handler(content_types=['document'])
def handle_csv_upload(message):
    if message.document.file_name.endswith('.csv'):
        user_data[message.chat.id] = {'file_id': message.document.file_id}
        
        markup = InlineKeyboardMarkup(row_width=2)
        buttons = [InlineKeyboardButton(cat, callback_data=f"cat_{cat}") for cat in CATEGORIES]
        markup.add(*buttons)
        
        bot.reply_to(message, "📥 CSV File mil gayi hai! Kripya is quiz ki **Category** chunein:", reply_markup=markup, parse_mode="Markdown")
    else:
        bot.reply_to(message, "❌ Kripya sirf valid `.csv` format waali file hi upload karein.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('cat_'))
def callback_category_selection(call):
    chat_id = call.message.chat.id
    category = call.data.split('_')[1]
    
    if chat_id in user_data:
        user_data[chat_id]['category'] = category
        bot.edit_message_text(f"✅ Selected Category: *{category}*", chat_id, call.message.message_id, parse_mode="Markdown")
        
        msg = bot.send_message(chat_id, "✍️ Ab is Quiz ka ek **Title (Chapter Name)** likh kar bhejein:")
        bot.register_next_step_handler(msg, process_quiz_title)
    else:
        bot.send_message(chat_id, "⚠️ Session expired. Kripya `/csv_to_quiz` se shuru karein.")

def process_quiz_title(message):
    chat_id = message.chat.id
    title = message.text.strip()
    
    if chat_id not in user_data or 'file_id' not in user_data[chat_id]:
        bot.send_message(chat_id, "❌ Kuch galat hua. Kripya shuru se karein.")
        return

    category = user_data[chat_id]['category']
    file_id = user_data[chat_id]['file_id']
    
    bot.send_message(chat_id, "⏳ Questions ko database mein save kiya ja raha hai...")
    
    file_info = bot.get_file(file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    try:
        csv_data = io.StringIO(downloaded_file.decode('utf-8'))
        reader = csv.reader(csv_data)
        header = next(reader, None)  # Bypass header column
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        cursor.execute("INSERT INTO quizzes (title, category, created_at) VALUES (?, ?, ?)", 
                       (title, category, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        quiz_id = cursor.lastrowid
        
        q_count = 0
        for row in reader:
            if len(row) >= 6:
                cursor.execute(
                    "INSERT INTO questions (quiz_id, question, option_a, option_b, option_c, option_d, correct_option) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (quiz_id, row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip(), row[4].strip(), row[5].strip().upper())
                )
                q_count += 1
                
        conn.commit()
        
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🚀 Start Normal Practice", callback_data=f"playnormal_{quiz_id}"))
        markup.row(InlineKeyboardButton("📁 Keep in Hama Revision Pool", callback_data="keep_pool"))
        
        bot.send_message(
            chat_id, 
            f"🎯 *Success!* \n\n"
            f"📂 Category: `{category}`\n"
            f"📖 Title: `{title}`\n"
            f"📊 Total Questions: `{q_count}` database mein save ho chuke hain.",
            reply_markup=markup, parse_mode="Markdown"
        )
        
    except Exception as e:
        bot.send_message(chat_id, f"❌ CSV Parse karne mein dikkat aayi: {str(e)}")
    finally:
        if 'conn' in locals(): conn.close()
        if chat_id in user_data: del user_data[chat_id]

# --- LEGACY NORMAL PRACTICE MODE TRIGGER ---
@bot.message_handler(commands=['quiz'])
def normal_practice_menu(message):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT category FROM quizzes")
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        bot.send_message(message.chat.id, "📭 Abhi database mein koi quiz nahi hai. Pehle `/csv_to_quiz` se file upload karein!")
        return
        
    markup = InlineKeyboardMarkup(row_width=2)
    for row in rows:
        markup.add(InlineKeyboardButton(row[0], callback_data=f"normcat_{row[0]}"))
    bot.send_message(message.chat.id, "📚 Normal Practice ke liye category chunein:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('normcat_'))
def normcat_selected(call):
    cat = call.data.split('_')[1]
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM quizzes WHERE category=?", (cat,))
    rows = cursor.fetchall()
    conn.close()
    
    markup = InlineKeyboardMarkup(row_width=1)
    for row in rows:
        markup.add(InlineKeyboardButton(row[1], callback_data=f"playnormal_{row[0]}"))
    bot.edit_message_text(f"📖 *{cat}* ke saare available chapters:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('playnormal_'))
def start_legacy_quiz(call):
    quiz_id = call.data.split('_')[1]
    chat_id = call.message.chat.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, question, option_a, option_b, option_c, option_d, correct_option FROM questions WHERE quiz_id=?", (quiz_id,))
    questions = cursor.fetchall()
    conn.close()
    
    if not questions:
        bot.send_message(chat_id, "❌ Is quiz ke andar koi sawal nahi mile.")
        return
        
    active_normal_quiz[chat_id] = {'list': questions, 'index': 0, 'score': 0}
    send_next_normal_question(chat_id)

def send_next_normal_question(chat_id):
    quiz = active_normal_quiz[chat_id]
    idx = quiz['index']
    
    if idx >= len(quiz['list']):
        bot.send_message(chat_id, f"🏁 *Practice complete!* Aapne total {len(quiz['list'])} mein se *{quiz['score']}* sahi jawab diye.", parse_mode="Markdown")
        del active_normal_quiz[chat_id]
        return
        
    q = quiz['list'][idx]
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(f"A) {q[2]}", callback_data=f"ans_A_{q[0]}"),
        InlineKeyboardButton(f"B) {q[3]}", callback_data=f"ans_B_{q[0]}"),
        InlineKeyboardButton(f"C) {q[4]}", callback_data=f"ans_C_{q[0]}"),
        InlineKeyboardButton(f"D) {q[5]}", callback_data=f"ans_D_{q[0]}")
    )
    bot.send_message(chat_id, f"❓ *Sawal {idx+1}:* {q[1]}", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('ans_'))
def handle_normal_answer(call):
    chat_id = call.message.chat.id
    if chat_id not in active_normal_quiz:
        bot.answer_callback_query(call.id, "Session expired!")
        return
        
    _, chosen, q_id = call.data.split('_')
    quiz = active_normal_quiz[chat_id]
    current_q = quiz['list'][quiz['index']]
    correct = current_q[6]
    
    if chosen == correct:
        bot.answer_callback_query(call.id, "✅ Sahi Jawab!")
        quiz['score'] += 1
    else:
        bot.answer_callback_query(call.id, f"❌ Galat! Sahi answer {correct} tha.")
        
    quiz['index'] += 1
    bot.delete_message(chat_id, call.message.message_id)
    send_next_normal_question(chat_id)

@bot.callback_query_handler(func=lambda call: call.data == "keep_pool")
def keep_in_pool_callback(call):
    bot.edit_message_text("📥 Quiz ko pool mein save rakh diya gaya hai. Aap iska revision `/hama_revision` command se active kar sakte hain.", call.message.chat.id, call.message.message_id)


# --- ADVANCED HAMA REVISION PANEL TRIGGER ---
@bot.message_handler(commands=['hama_revision'])
def hama_revision_dashboard(message):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"revpanel_{cat}") for cat in CATEGORIES]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "📂 **HAMA REVISION DASHBOARD**\n\nNiche se category chunein jiska status dekhna hai ya revision schedule karna hai:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('revpanel_'))
def category_revision_status(call):
    chat_id = call.message.chat.id
    cat = call.data.split('_')[1]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check total questions vs unseen ones
    cursor.execute("SELECT id FROM questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE category=?)", (cat,))
    total_q_ids = [r[0] for r in cursor.fetchall()]
    
    if not total_q_ids:
        bot.edit_message_text(f"📭 *{cat}* category mein abhi koi questions nahi hain. Pehle CSV upload karein.", chat_id, call.message.message_id, parse_mode="Markdown")
        conn.close()
        return
        
    cursor.execute("SELECT question_id FROM seen_questions WHERE user_id=? AND question_id IN (SELECT id FROM questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE category=?))", (chat_id, cat))
    seen_q_ids = [r[0] for r in cursor.fetchall()]
    
    unseen_count = len(total_q_ids) - len(seen_q_ids)
    
    # Fetch active schedule configuration
    cursor.execute("SELECT start_date, run_time, daily_limit, status FROM revision_schedules WHERE user_id=? AND category=?", (chat_id, cat))
    sched = cursor.fetchone()
    conn.close()
    
    status_text = f"🗂️ Category: *{cat}*\n"
    status_text += f"📊 Remaining Unseen Questions: `{unseen_count} / {len(total_q_ids)}` \n\n"
    
    markup = InlineKeyboardMarkup()
    
    if sched:
        start_date, run_time, daily_limit, status = sched
        today_str = datetime.now().strftime("%Y-%m-%d")
        display_status = status
        if status == 'Running' and start_date > today_str:
            display_status = "⏳ Scheduled"
            
        status_text += f"⚙️ *Current Status:* `{display_status}`\n🗓️ *Start Date:* `{start_date}`\n⏰ *Time:* `{run_time}`\n🔢 *Daily Limit:* `{daily_limit} Qs/day`"
        markup.row(InlineKeyboardButton("🛑 Stop/Delete Schedule", callback_data=f"delsched_{cat}"))
    else:
        status_text += "❌ Abhi is category ka koi scheduling chalu nahi hai."
        if unseen_count > 0:
            markup.row(InlineKeyboardButton("⚙️ Setup Daily Revision Schedule", callback_data=f"setsched_{cat}"))
            
    markup.row(InlineKeyboardButton("⬅️ Back to Categories", callback_data="back_rev_main"))
    bot.edit_message_text(status_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_rev_main")
def back_to_revision_main(call):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"revpanel_{cat}") for cat in CATEGORIES]
    markup.add(*buttons)
    bot.edit_message_text("📂 **HAMA REVISION DASHBOARD**\n\nNiche se category chunein:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- ENGINE CONFIGURATION SCHEDULER WIZARD ---
@bot.callback_query_handler(func=lambda call: call.data.startswith('setsched_'))
def setup_scheduler_start(call):
    cat = call.data.split('_')[1]
    chat_id = call.message.chat.id
    user_data[chat_id] = {'sched_cat': cat}
    
    bot.delete_message(chat_id, call.message.message_id)
    msg = bot.send_message(chat_id, f"🗓️ *[1/3] Start Date Set Karein*\n\nAap kis date se revision shuru karna chahte hain?\nFormat: `DD-MM-YYYY` (Example: {datetime.now().strftime('%d-%m-%Y')})", parse_mode="Markdown")
    bot.register_next_step_handler(msg, process_sched_date)

def process_sched_date(message):
    chat_id = message.chat.id
    date_str = message.text.strip()
    
    try:
        parsed_date = datetime.strptime(date_str, "%d-%m-%Y")
        db_date_format = parsed_date.strftime("%Y-%m-%d")
        user_data[chat_id]['sched_date'] = db_date_format
        
        msg = bot.send_message(chat_id, "⏰ *[2/3] Daily Time Set Karein*\n\nRozana kis time par questions chahiye?\nFormat: `HH:MM` 24-Hour format mein (Example: `21:30`):", parse_mode="Markdown")
        bot.register_next_step_handler(msg, process_sched_time)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Galat format! Kripya `DD-MM-YYYY` format mein hi date likhein:")
        bot.register_next_step_handler(msg, process_sched_date)

def process_sched_time(message):
    chat_id = message.chat.id
    time_str = message.text.strip()
    
    try:
        datetime.strptime(time_str, "%H:%M")
        user_data[chat_id]['sched_time'] = time_str
        
        msg = bot.send_message(chat_id, "🔢 *[3/3] Daily Question Limit*\n\nRozana kitne naye sawal (questions) check karna chahte hain? (e.g., `10`, `15` or `20`):")
        bot.register_next_step_handler(msg, process_sched_limit)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Galat time format! Kripya 24-hour `HH:MM` format mein likhein (e.g. `18:00`):")
        bot.register_next_step_handler(msg, process_sched_time)

def process_sched_limit(message):
    chat_id = message.chat.id
    limit_str = message.text.strip()
    
    if not limit_str.isdigit() or int(limit_str) <= 0:
        msg = bot.send_message(chat_id, "❌ Kripya ek positive number type karein:")
        bot.register_next_step_handler(msg, process_sched_limit)
        return
        
    limit = int(limit_str)
    cat = user_data[chat_id]['sched_cat']
    start_date = user_data[chat_id]['sched_date']
    run_time = user_data[chat_id]['sched_time']
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO revision_schedules (user_id, category, start_date, run_time, daily_limit, status) VALUES (?, ?, ?, ?, ?, 'Running')",
        (chat_id, cat, start_date, run_time, limit)
    )
    conn.commit()
    conn.close()
    
    del user_data[chat_id]
    setup_cron_job(chat_id, cat, run_time)
    
    bot.send_message(
        chat_id,
        f"🚀 *Revision Schedule Active!*\n\n"
        f"🗂️ Category: `{cat}`\n"
        f"🗓️ Start Date: `{start_date}`\n"
        f"⏰ Daily Time: `{run_time}`\n"
        f"🔢 Daily Limit: `{limit} Questions/Day` \n\n"
        f"Bot theek is time par aapko automatic mixed questions bhej dega."
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('delsched_'))
def delete_revision_schedule(call):
    cat = call.data.split('_')[1]
    chat_id = call.message.chat.id
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM revision_schedules WHERE user_id=? AND category=?", (chat_id, cat))
    conn.commit()
    conn.close()
    
    job_id = f"{chat_id}_{cat}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    bot.edit_message_text(f"🛑 *{cat}* ka revision schedule delete kar diya gaya hai.", chat_id, call.message.message_id, parse_mode="Markdown")

# --- SCHEDULER EXECUTION ENGINE ---
def setup_cron_job(user_id, category, run_time):
    hour, minute = map(int, run_time.split(':'))
    job_id = f"{user_id}_{category}"
    
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        
    scheduler.add_job(
        execute_daily_revision,
        'cron',
        hour=hour,
        minute=minute,
        id=job_id,
        args=[user_id, category]
    )

def execute_daily_revision(user_id, category):
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT start_date, daily_limit, status FROM revision_schedules WHERE user_id=? AND category=?", (user_id, category))
    sched = cursor.fetchone()
    
    if not sched or sched[2] != 'Running' or today_str < sched[0]:
        conn.close()
        return
        
    daily_limit = sched[1]
    
    cursor.execute('''
        SELECT id, question, option_a, option_b, option_c, option_d, correct_option 
        FROM questions 
        WHERE quiz_id IN (SELECT id FROM quizzes WHERE category=?) 
        AND id NOT IN (SELECT question_id FROM seen_questions WHERE user_id=?)
    ''', (category, user_id))
    
    unseen_questions = cursor.fetchall()
    
    if not unseen_questions:
        cursor.execute("UPDATE revision_schedules SET status='Completed' WHERE user_id=? AND category=?", (user_id, category))
        conn.commit()
        conn.close()
        bot.send_message(user_id, f"✅ *Revision Completed!* \n\n*{category}* ke saare questions ka revision poora ho chuka hai!")
        return
        
    random.shuffle(unseen_questions)
    dispatch_pool = unseen_questions[:daily_limit]
