import telebot
import csv
import io
import threading
import time
import os
from flask import Flask
from telebot.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton

app = Flask('')

@app.route('/')
def home():
    return "Quiz Bot is running perfectly!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

BOT_TOKEN = "8943398504:AAGIjt1WrTe5wivSDU9tqtWSO97DM9FN2iQ" 
bot = telebot.TeleBot(BOT_TOKEN)

# In-memory storage (Note: Render restart par yeh reset ho sakta hai)
uploaded_quizzes = {}
user_sessions = {}
temp_csv_data = {}

def set_bot_commands():
    try:
        commands = [
            BotCommand("start", "🤖 Bot ko shuru karein"),
            BotCommand("csv_to_quiz", "📁 CSV file se quiz banayein"),
            BotCommand("quiz", "🎯 Apna banaya hua Quiz chalayein")
        ]
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Menu error: {e}")

@bot.message_handler(commands=['start'])
def start_message(message):
    # Agar user share button se ya direct quiz shuru karne aaya hai
    text_args = message.text.split()
    if len(parts := text_args) > 1 and parts[1].startswith('startquiz_'):
        quiz_id = parts[1].replace('startquiz_', '')
        if quiz_id in uploaded_quizzes:
            trigger_quiz_start(message.chat.id, quiz_id)
            return
        else:
            bot.send_message(message.chat.id, "⚠️ Yeh quiz abhi available nahi hai ya expire ho chuka hai.")
            return

    welcome_text = (
        "👋 *Welcome to the Smart Quiz Bot!*\n\n"
        "Apni CSV file upload karke aap professional standard quiz bana sakte hain.\n\n"
        "⚙️ *Kaise use karein:*\n"
        "1. `/csv_to_quiz` par click karein.\n"
        "2. Apni `.csv` file bot ko bhejein.\n"
        "3. Quiz ka ek Title (Naam) type karke bhejein.\n"
        "4. Standard Mode choose karke apna Shareable Quiz Card taiyar karein!"
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
        
    # Unique quiz ID create karenge text sharing ke liye
    quiz_id = f"q_{chat_id}"
    uploaded_quizzes[quiz_id] = {
        "title": quiz_title,
        "questions": temp_csv_data[chat_id],
        "creator": chat_id
    }
    del temp_csv_data[chat_id]
    
    # Mode puchne ke liye buttons
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⚙️ Standard Mode", callback_data=f"mode_standard_{quiz_id}"))
    markup.add(InlineKeyboardButton("🔒 Live Mode (Coming Soon)", callback_data="mode_live_soon"))
    
    bot.send_message(
        chat_id, 
        f"✅ *Quiz Ka Naam Saved:* \"{quiz_title}\"\n\nAb select karein ki aap ise kis mode mein chalana chahte hain:", 
        reply_markup=markup,
        parse_mode="Markdown"
    )

@telebot.callback_query_handler(func=lambda call: call.data.startswith('mode_'))
def handle_modes(call):
    chat_id = call.message.chat.id
    if call.data == "mode_live_soon":
        bot.answer_callback_query(call.id, "Live mode abhi under development hai! Kripya Standard Mode chunein.", show_alert=True)
        return
        
    quiz_id = call.data.replace('mode_standard_', '')
    if quiz_id not in uploaded_quizzes:
        bot.send_message(chat_id, "⚠️ Quiz data nahi mila.")
        return
        
    bot.delete_message(chat_id, call.message.message_id)
    show_quiz_card(chat_id, quiz_id)

def show_quiz_card(chat_id, quiz_id):
    quiz_data = uploaded_quizzes[quiz_id]
    title = quiz_data["title"]
    total_q = len(quiz_data["questions"])
    bot_username = bot.get_me().username
    
    # Official QuizBot jaisa format panel card
    card_text = (
        f"🎲 *Quiz '{title}'*\n\n"
        f"📝 *{total_q} questions*\n"
        f"⏱ *30 sec* per question\n\n"
        f"👥 Tap on buttons below to play!"
    )
    
    markup = InlineKeyboardMarkup()
    # 1. Start This Quiz Button (Personal chat me start karega)
    btn_start = InlineKeyboardButton("🏁 Start this quiz", callback_data=f"runquiz_{quiz_id}")
    # 2. Start Quiz in Group Button
    btn_group = InlineKeyboardButton("👥 Start quiz in group", switch_inline_query_chosen_chat=telebot.types.SwitchInlineQueryChosenChat(query=f"start_{quiz_id}", allow_user_chats=False, allow_bot_chats=False, allow_group_chats=True, allow_channel_chats=True))
    # 3. Share Quiz Button
    share_url = f"https://t.me/{bot_username}?start=startquiz_{quiz_id}"
    btn_share = InlineKeyboardButton("🔗 Share quiz", url=f"https://t.me/share/url?url={share_url}&text=Hey! Try this awesome quiz: {title}")
    
    markup.add(btn_start)
    markup.add(btn_group)
    markup.add(btn_share)
    
    bot.send_message(chat_id, card_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith('runquiz_'))
def handle_run_quiz_click(call):
    chat_id = call.message.chat.id
    quiz_id = call.data.replace('runquiz_', '')
    bot.delete_message(chat_id, call.message.message_id)
    trigger_quiz_start(chat_id, quiz_id)

def trigger_quiz_start(chat_id, quiz_id):
    if quiz_id not in uploaded_quizzes:
        bot.send_message(chat_id, "⚠️ Quiz data nahi mila.")
        return
        
    user_sessions[chat_id] = {"quiz_id": quiz_id, "current_q": 0, "score": 0}
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
    
    bot.send_message(
        chat_id, 
        f"🏁 *Quiz Poora Hua!*\n📌 *Topic:* `{title}`\n📊 *Aapka Final Score:* {score}/{total}", 
        parse_mode="Markdown"
    )
    
    # Quiz khatam hone ke baad wapas Card generate kar dena taaki replay kiya ja sake
    time.sleep(1)
    show_quiz_card(chat_id, quiz_id)
    if chat_id in user_sessions: del user_sessions[chat_id]

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
