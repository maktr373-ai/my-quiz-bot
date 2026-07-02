import os
import csv
import io
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Global session databases
QUESTIONS_DATABASE = []
BOT_STATE = {} # User ka current state save karne ke liye

CATEGORIES = [
    "Physics", "Chemistry", "Biology", "History", "Geography", 
    "Polity", "Economics", "Current Affairs", "English", "Hindi", "Math"
]

def find_column(row, standard_names):
    for key in row.keys():
        if key and key.strip().lower() in standard_names:
            return key
    return None

def parse_csv_data(csv_text):
    """Super Flexible CSV Parser: Yeh har ek valid row ko read karega bina skip kiye"""
    questions_list = []
    try:
        # Line breaks aur commas ko safely handle karne ke liye dictreader use karenge
        f = io.StringIO(csv_text.strip())
        csv_reader = csv.DictReader(f)
        
        # Headers clean up (spaces hatane ke liye)
        fieldnames = [field.strip().lower() if field else "" for field in csv_reader.fieldnames]
        
        # Re-map clean headers to original row mapping
        f.seek(0)
        next(csv_reader) # skip header row
        
        for row in csv_reader:
            if not row:
                continue
            
            # Clean keys of the row to match columns easily
            clean_row = {k.strip().lower() if k else "": v for k, v in row.items()}
            
            q_col = find_column(clean_row, ["question", "questions", "sawal", "q"])
            o1_col = find_column(clean_row, ["option1", "option 1", "opt1", "a"])
            o2_col = find_column(clean_row, ["option2", "option 2", "opt2", "b"])
            o3_col = find_column(clean_row, ["option3", "option 3", "opt3", "c"])
            o4_col = find_column(clean_row, ["option4", "option 4", "opt4", "d"])
            c_col = find_column(clean_row, ["correct", "correct_option", "answer", "ans", "right"])
            
            if q_col and o1_col and o2_col and o3_col and o4_col and c_col:
                try:
                    if not clean_row[q_col] or not clean_row[q_col].strip():
                        continue
                    
                    # Extract only digits from correct option
                    correct_val = "".join(filter(str.isdigit, str(clean_row[c_col])))
                    if not correct_val:
                        continue
                    
                    correct_idx = int(correct_val)
                    if correct_idx >= 1:
                        correct_idx = correct_idx - 1 # 0-based for Telegram Poll
                        
                    questions_list.append({
                        "question": clean_row[q_col].strip(),
                        "options": [
                            clean_row[o1_col].strip(),
                            clean_row[o2_col].strip(),
                            clean_row[o3_col].strip(),
                            clean_row[o4_col].strip()
                        ],
                        "correct": correct_idx
                    })
                except Exception as e:
                    print(f"Row skip hui due to error: {e}")
                    continue
    except Exception as e:
        print(f"Error parsing CSV: {e}")
    return questions_list

def get_main_keyboard():
    """Permanent Screen Buttons jo user se kabhi gayab nahi honge"""
    keyboard = [[KeyboardButton("📝 Start Quiz"), KeyboardButton("ℹ️ Help & Info")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, permanent=True)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "📊 **Kaise Use Karein:**\n"
        "1. Apni `.csv` file directly chat me bhejें.\n"
        "2. Bot aapse **Category** aur **Quiz Title** poochega.\n"
        "3. Uske baad niche diye gaye **📝 Start Quiz** button par click karke test shuru karein!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

async def handle_csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    document = update.message.document
    if not document or not document.file_name.endswith('.csv'):
        return

    status_message = await update.message.reply_text("📥 File read ki ja rahi hai, kripya thoda intezar karein...")
    try:
        new_file = await context.bot.get_file(document.file_id, read_timeout=60)
        file_bytes = await new_file.download_as_bytearray()
        csv_text = file_bytes.decode('utf-8', errors='ignore')
        
        parsed_questions = parse_csv_data(csv_text)
        if parsed_questions:
            # Temporary state me questions ko save kar rahe hain jab tak configuration poori na ho
            BOT_STATE[user_id] = {
                "temp_questions": parsed_questions,
                "category": None,
                "title": None,
                "stage": "WAITING_CATEGORY"
            }
            
            # Category chunne ke liye buttons generate karna
            category_buttons = [[KeyboardButton(cat)] for cat in CATEGORIES]
            category_markup = ReplyKeyboardMarkup(category_buttons, resize_keyboard=True, one_time_keyboard=True)
            
            await status_message.delete()
            await update.message.reply_text(
                f"✅ **CSV File Success! Total {len(parsed_questions)} sawal load ho gaye hain.**\n\n"
                f"📂 Ab is Quiz ke liye niche di gayi list me se **Category** choose karein:",
                reply_markup=category_markup
            )
        else:
            await status_message.edit_text("⚠️ Columns match nahi ho paye. File me question, option1, option2, option3, option4, correct hona zaroori hai.")
    except Exception as e:
        await status_message.edit_text(f"❌ Error aaya: {e}")

async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    global QUESTIONS_DATABASE

    # Handle Permanent Buttons First
    if text == "📝 Start Quiz":
        if not QUESTIONS_DATABASE:
            await update.message.reply_text("⚠️ Abhi database khali hai! Kripya pehle apni ek `.csv` file mujhe bhejें.", reply_markup=get_main_keyboard())
            return
        
        state = BOT_STATE.get(user_id, {})
        quiz_title = state.get("title", "The Academic Quiz")
        category = state.get("category", "General")
        
        quiz_item = random.choice(QUESTIONS_DATABASE)
        full_question_text = f"🔹 [{category}] {quiz_title} 🔹\n\n❓ {quiz_item['question']}"
        
        try:
            await context.bot.send_poll(
                chat_id=update.effective_chat.id,
                question=full_question_text[:300], # Telegram limit handle karne ke liye
                options=quiz_item["options"],
                type="quiz",
                correct_option_id=quiz_item["correct"],
                open_period=30
            )
        except Exception as e:
            await update.message.reply_text("❌ Quiz poll bhejne me error aaya. Check karein sawal ya options zyada bade toh nahi hain.")
        return

    elif text == "ℹ️ Help & Info":
        help_text = "💡 **Bot Guide:**\n\n1. `.csv` file bhejein\n2. Category chunein\n3. Title type karein\n4. '📝 Start Quiz' button daba kar test shuru karein."
        await update.message.reply_text(help_text, parse_mode="Markdown", reply_markup=get_main_keyboard())
        return

    # Handle State Machine Configuration Flow
    if user_id in BOT_STATE:
        state = BOT_STATE[user_id]
        
        if state["stage"] == "WAITING_CATEGORY":
            if text in CATEGORIES:
                state["category"] = text
                state["stage"] = "WAITING_TITLE"
                await update.message.reply_text(f"🎯 Category *{text}* set ho gayi!\n\nAb is Quiz ka ek **Title** type karke bhejiye (e.g., 'Chapter 1 Test'):", parse_mode="Markdown")
            else:
                await update.message.reply_text("⚠️ Kripya niche diye gaye buttons me se hi category choose karein.")
            return
            
        elif state["stage"] == "WAITING_TITLE":
            state["title"] = text
            # Sab set hone ke baad final global database me daal rahe hain
            QUESTIONS_DATABASE = state["temp_questions"]
            state["stage"] = "READY"
            
            success_msg = (
                f"🎉 **Quiz Setup Complete!**\n\n"
                f"📂 **Category:** {state['category']}\n"
                f"📝 **Title:** {state['title']}\n"
                f"📊 **Total Questions:** {len(QUESTIONS_DATABASE)}\n\n"
                f"Ab aap niche diye gaye **📝 Start Quiz** button par click karke test shuru kar sakte hain!"
            )
            await update.message.reply_text(success_msg, reply_markup=get_main_keyboard())
            return

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).read_timeout(60).write_timeout(60).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_csv_upload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    print("Bot starting with category and flexible csv support...")
    app.run_polling(close_loop=False, drop_pending_updates=True)

if __name__ == "__main__":
    main()
