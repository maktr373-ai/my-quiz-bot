import os
import sqlite3
import csv
import io
import random
from datetime import datetime
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand
from apscheduler.schedulers.background import BackgroundScheduler

# --- BOT CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "8943398504:AAGIjt1WrTe5wivSDU9tqtWSO97DM9FN2iQ")
bot = telebot.TeleBot(BOT_TOKEN)

# Background Scheduler handling
scheduler = BackgroundScheduler()
scheduler.start()

DB_NAME = "quiz_revision.db"

# --- DATABASE ENGINE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS quizzes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        created_at TEXT
    )''')
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
    cursor.execute('''CREATE TABLE IF NOT EXISTS seen_questions (
        user_id INTEGER,
        question_id INTEGER,
        PRIMARY KEY (user_id, question_id)
    )''')
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

CATEGORIES = [
    "BIO", "PHY", "CHEMISTRY", "HISTORY", "GEOGRAPHY", 
    "ECONOMIC", "POLITY", "HINDI", "ENGLISH", "MATHS", "CURRENT AFFAIRS"
]

user_data = {}
active_normal_quiz = {}

def set_bot_menu():
    commands = [
        BotCommand("start", "🤖 Bot ko shuru karein"),
        BotCommand("csv_to_quiz", "📁 CSV file se quiz banayein"),
        BotCommand("quiz", "🎯 Normal Practice Mode open karein"),
        BotCommand("hama_revision", "📚 HAMA REVISION Mode open karein")
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
        header = next(reader, None)
        
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
            f"🎯 *Success!* \n\n📂 Category: `{category}`\n📖 Title: `{title}`\n📊 Total Questions: `{q_count}` save ho gaye.",
            reply_markup=markup, parse_mode="Markdown"
        )
    except Exception as e:
        bot.send_message(chat_id, f"❌ CSV Parse Error: {str(e)}")
    finally:
        if 'conn' in locals(): conn.close()
        if chat_id in user_data: del user_data[chat_id]

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
        bot.send_message(chat_id, f"🏁 *Practice complete!* Total mein se *{quiz['score']}* sahi jawab diye.", parse_mode="Markdown")
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

@bot.message_handler(commands=['hama_revision'])
def hama_revision_dashboard(message):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"revpanel_{cat}") for cat in CATEGORIES]
    markup.add(*buttons)
    bot.send_message(message.chat.id, "📂 **HAMA REVISION DASHBOARD**\n\nNiche se category chunein:", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('revpanel_'))
def category_revision_status(call):
    chat_id = call.message.chat.id
    cat = call.data.split('_')[1]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE category=?)", (cat,))
    total_q_ids = [r[0] for r in cursor.fetchall()]
    
    if not total_q_ids:
        bot.edit_message_text(f"📭 *{cat}* category mein abhi koi questions nahi hain. Pehle CSV upload karein.", chat_id, call.message.message_id, parse_mode="Markdown")
        conn.close()
        return
        
    cursor.execute("SELECT question_id FROM seen_questions WHERE user_id=? AND question_id IN (SELECT id FROM questions WHERE quiz_id IN (SELECT id FROM quizzes WHERE category=?))", (chat_id, cat))
    seen_q_ids = [r[0] for r in cursor.fetchall()]
    unseen_count = len(total_q_ids) - len(seen_q_ids)
    
    cursor.execute("SELECT start_date, run_time, daily_limit, status FROM revision_schedules WHERE user_id=? AND category=?", (chat_id, cat))
    sched = cursor.fetchone()
    conn.close()
    
    status_text = f"🗂️ Category: *{cat}*\n📊 Remaining Unseen Questions: `{unseen_count} / {len(total_q_ids)}` \n\n"
    markup = InlineKeyboardMarkup()
    
    if sched:
        start_date, run_time, daily_limit, status = sched
        today_str = datetime.now().strftime("%Y-%m-%d")
        display_status = status
        if status == 'Running' and start_date > today_str:
            display_status = "⏳ Scheduled"
        status_text += f"⚙️ *Current Status:* `{display_status}`\n🗓️ *Start Date:* `{start_date}`\n⏰ *Time:* `{run_time}`\n🔢 *Daily Limit:* `{daily_limit} Qs/day`"
        markup.row(InlineKeyboardButton("🛑 Stop Schedule", callback_data=f"delsched_{cat}"))
    else:
        status_text += "❌ Scheduling chalu nahi hai."
        if unseen_count > 0:
            markup.row(InlineKeyboardButton("⚙️ Setup Revision Schedule", callback_data=f"setsched_{cat}"))
            
    markup.row(InlineKeyboardButton("⬅️ Back", callback_data="back_rev_main"))
    bot.edit_message_text(status_text, chat_id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_rev_main")
def back_to_revision_main(call):
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = [InlineKeyboardButton(cat, callback_data=f"revpanel_{cat}") for cat in CATEGORIES]
    markup.add(*buttons)
    bot.edit_message_text("📂 **HAMA REVISION DASHBOARD**\n\nNiche se category chunein:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('setsched_'))
def setup_scheduler_start(call):
    cat = call.data.split('_')[1]
    chat_id = call.message.chat.id
    user_data[chat_id] = {'sched_cat': cat}
    bot.delete_message(chat_id, call.message.message_id)
    msg = bot.send_message(chat_id, f"🗓️ *[1/3] Start Date Set* (`DD-MM-YYYY`):")
    bot.register_next_step_handler(msg, process_sched_date)

def process_sched_date(message):
    chat_id = message.chat.id
    date_str = message.text.strip()
    try:
        parsed_date = datetime.strptime(date_str, "%d-%m-%Y")
        user_data[chat_id]['sched_date'] = parsed_date.strftime("%Y-%m-%d")
        msg = bot.send_message(chat_id, "⏰ *[2/3] Daily Time* (`HH:MM` - 24hr format):")
        bot.register_next_step_handler(msg, process_sched_time)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Galat format! Use `DD-MM-YYYY`:")
        bot.register_next_step_handler(msg, process_sched_date)

def process_sched_time(message):
    chat_id = message.chat.id
    time_str = message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
        user_data[chat_id]['sched_time'] = time_str
        msg = bot.send_message(chat_id, "🔢 *[3/3] Daily Question Limit*:")
        bot.register_next_step_handler(msg, process_sched_limit)
    except ValueError:
        msg = bot.send_message(chat_id, "❌ Use 24-hour `HH:MM` format:")
        bot.register_next_step_handler(msg, process_sched_time)

def process_sched_limit(message):
    chat_id = message.chat.id
    limit_str = message.text.strip()
    if not limit_str.isdigit() or int(limit_str) <= 0:
        msg = bot.send_message(chat_id, "❌ Number type karein:")
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
    bot.send_message(chat_id, f"🚀 *Revision Schedule Active!*\nCategory: `{cat}`\nLimit: `{limit} Qs/day`")

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
    bot.edit_message_text(f"🛑 *{cat}* schedule deleted.", chat_id, call.message.message_id)

def setup_cron_job(user_id, category, run_time):
    hour, minute = map(int, run_time.split(':'))
    job_id = f"{user_id}_{category}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
    scheduler.add_job(execute_daily_revision, 'cron', hour=hour, minute=minute, id=job_id, args=[user_id, category])

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
        bot.send_message(user_id, f"✅ *Revision Completed!* \n\n*{category}* poora ho chuka hai!")
        return
        
    random.shuffle(unseen_questions)
    dispatch_pool = unseen_questions[:daily_limit]
    bot.send_message(user_id, f"📚 ⏰ *Hama Revision Time!* \nCategory: *{category}*")
    
    for q in dispatch_pool:
        cursor.execute("INSERT OR IGNORE INTO seen_questions (user_id, question_id) VALUES (?, ?)", (user_id, q[0]))
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton(f"A) {q[2]}", callback_data=f"revans_A_{q[0]}"),
            InlineKeyboardButton(f"B) {q[3]}", callback_data=f"revans_B_{q[0]}"),
            InlineKeyboardButton(f"C) {q[4]}", callback_data=f"revans_C_{q[0]}"),
            InlineKeyboardButton(f"D) {q[5]}", callback_data=f"revans_D_{q[0]}")
        )
        bot.send_message(user_id, f"❓ {q[1]}", reply_markup=markup)
    conn.commit()
    conn.close()

@bot.callback_query_handler(func=lambda call: call.data.startswith('revans_'))
def handle_revision_answer(call):
    _, chosen, q_id = call.data.split('_')
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT correct_option, question FROM questions WHERE id=?", (q_id,))
    res = cursor.fetchone()
    conn.close()
    
    if not res: return
    correct, question_text = res
    if chosen == correct:
        bot.edit_message_text(f"❓ {question_text}\n\n👉 Jawab: *{chosen}* \n\n✅ **Sahi Jawab!**", call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    else:
        bot.edit_message_text(f"❓ {question_text}\n\n👉 Jawab: *{chosen}* \n\n❌ **Galat Jawab!**\n🎯 Sahi answer: *{correct}*", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

def live_reconnect_schedules():
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, category, run_time FROM revision_schedules WHERE status='Running'")
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            setup_cron_job(row[0], row[1], row[2])
    except Ex
