import os
import csv
import io
import random
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Global list taaki data memory me safely save rahe
QUESTIONS_DATABASE = []

def find_column(row, standard_names):
    for key in row.keys():
        if key and key.strip().lower() in standard_names:
            return key
    return None

def parse_csv_data(csv_text):
    """CSV text ko read karke questions list return karta hai (Super Flexible)"""
    questions_list = []
    try:
        f = io.StringIO(csv_text)
        csv_reader = csv.DictReader(f)
        
        first_row = next(csv_reader, None)
        if first_row is None:
            return questions_list
            
        q_col = find_column(first_row, ["question", "questions", "sawal", "q"])
        o1_col = find_column(first_row, ["option1", "option 1", "opt1", "a"])
        o2_col = find_column(first_row, ["option2", "option 2", "opt2", "b"])
        o3_col = find_column(first_row, ["option3", "option 3", "opt3", "c"])
        o4_col = find_column(first_row, ["option4", "option 4", "opt4", "d"])
        c_col = find_column(first_row, ["correct", "correct_option", "answer", "ans", "right"])

        def extract_data(row_data):
            try:
                if not row_data[q_col]: return None
                correct_val = "".join(filter(str.isdigit, str(row_data[c_col])))
                correct_idx = int(correct_val)
                if correct_idx >= 1:
                    correct_idx = correct_idx - 1
                return {
                    "question": row_data[q_col].strip(),
                    "options": [
                        row_data[o1_col].strip(),
                        row_data[o2_col].strip(),
                        row_data[o3_col].strip(),
                        row_data[o4_col].strip()
                    ],
                    "correct": correct_idx
                }
            except:
                return None

        if q_col and o1_col and o2_col and o3_col and o4_col and c_col:
            p1 = extract_data(first_row)
            if p1: questions_list.append(p1)
            for row in csv_reader:
                p = extract_data(row)
                if p: questions_list.append(p)
    except Exception as e:
        print(f"Error parsing CSV: {e}")
    return questions_list

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "📊 **CSV File Kaise Upload Karein:**\n"
        "Aap apni naye sawalon wali `.csv` file directly is chat me bhej dijiye. Bot use turant set kar lega.\n\n"
        "🧩 **Quiz Shuru Karein:** Niche left side wale **Blue Menu Button** par click karke `📝 Start Quiz` choose karein."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global QUESTIONS_DATABASE
    if not QUESTIONS_DATABASE:
        await update.message.reply_text("⚠️ Abhi database khali hai! Kripya pehle apni ek `.csv` file mujhe bhejें.")
        return
    
    quiz_item = random.choice(QUESTIONS_DATABASE)
    try:
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=quiz_item["question"],
            options=quiz_item["options"],
            type="quiz",
            correct_option_id=quiz_item["correct"],
            open_period=30
        )
    except Exception as e:
        await update.message.reply_text("❌ Quiz send karne me dikkat aayi. Kripya check karein ki option ka size lamba toh nahi hai.")

async def handle_csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global QUESTIONS_DATABASE
    document = update.message.document
    
    if not document.file_name.endswith('.csv'):
        await update.message.reply_text("⚠️ Kripya sirf `.csv` format wali file hi bhejें!")
        return

    status_message = await update.message.reply_text("📥 File mil gayi hai, data load kiya ja raha hai...")

    try:
        # File ko byte arrays me download karke text me convert karenge
        new_file = await context.bot.get_file(document.file_id)
        file_bytes = await new_file.download_as_bytearray()
        csv_text = file_bytes.decode('utf-8', errors='ignore')
        
        # Data load karenge
        parsed_questions = parse_csv_data(csv_text)
        
        if parsed_questions:
            QUESTIONS_DATABASE = parsed_questions
            await status_message.edit_text(
                f"✅ **Success! Aapki CSV file update ho gayi hai.**\n"
                f"📊 Total **{len(QUESTIONS_DATABASE)}** sawal load ho chuke hain!\n\n"
                f"Ab aap Blue Menu se `📝 Start Quiz` par click karke test kar sakte hain."
            )
        else:
            await status_message.edit_text(
                "⚠️ File khali hai ya columns match nahi hue. "
                "Kripya check karein ki file me `question`, `option1`, `option2`, `option3`, `option4`, `correct` columns hain ya nahi."
            )
    except Exception as e:
        await status_message.edit_text(f"❌ File handle karne me error aaya: {e}")

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    # Direct document filter lagaya hai taaki handle karne me crash na ho
    app.add_handler(MessageHandler(filters.Document.ALL, handle_csv_upload))
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
