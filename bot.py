import os
import csv
import random
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE_PATH = os.path.join(BASE_DIR, "questions.csv")

def find_column(row, standard_names):
    """Yeh function kisi bhi tarah ke column name ko dhoond nikalega"""
    for key in row.keys():
        if key and key.strip().lower() in standard_names:
            return key
    return None

def load_questions_from_csv():
    questions_list = []
    if not os.path.exists(CSV_FILE_PATH):
        return questions_list
    try:
        # 'utf-8-sig' Excel ke BOM characters ko automatically clean kar deta hai
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig', errors='ignore') as file:
            csv_reader = csv.DictReader(file)
            
            # Pehli row check karke columns mapping karenge
            first_row = next(csv_reader, None)
            if first_row is None:
                return questions_list
                
            # Column names ko pehchanna (Flexible Mapping)
            q_col = find_column(first_row, ["question", "questions", "sawal", "q"])
            o1_col = find_column(first_row, ["option1", "option 1", "opt1", "a"])
            o2_col = find_column(first_row, ["option2", "option 2", "opt2", "b"])
            o3_col = find_column(first_row, ["option3", "option 3", "opt3", "c"])
            o4_col = find_column(first_row, ["option4", "option 4", "opt4", "d"])
            c_col = find_column(first_row, ["correct", "correct_option", "answer", "ans", "right"])

            # Pehli row ka data process karenge agar columns sahi mile
            if q_col and o1_col and o2_col and o3_col and o4_col and c_col:
                def extract_data(row_data):
                    try:
                        # Correct option number ko extract karna (e.g. "3" ya "3 " ko integer me badalna)
                        correct_val = "".join(filter(str.isdigit, str(row_data[c_col])))
                        correct_idx = int(correct_val)
                        
                        # Agar index 1 se 4 ke beech hai toh use 0-3 base me convert karna
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

                p1 = extract_data(first_row)
                if p1: questions_list.append(p1)

                # Baki saari rows ko read karenge
                for row in csv_reader:
                    p = extract_data(row)
                    if p: questions_list.append(p)
                    
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return questions_list

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "📊 **CSV File Upload karein:** Aap apni kisi bhi tarah ki `.csv` file directly chat me bhej sakte hain. Bot use turant padh lega!\n\n"
        "🧩 **Quiz Kheliye:** Niche left side wale **Blue Menu Button** par click karke `📝 Start Quiz` par click karein."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = load_questions_from_csv()
    if not questions:
        await update.message.reply_text("⚠️ Database khali hai! Kripya pehle apni ek `.csv` file is chat me bhejें.")
        return
    
    quiz_item = random.choice(questions)
    # Explanation parameter poori tarah se hata diya gaya hai
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=quiz_item["question"],
        options=quiz_item["options"],
        type="quiz",
        correct_option_id=quiz_item["correct"],
        open_period=30
    )

async def handle_csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith('.csv'):
        await update.message.reply_text("⚠️ Kripya sirf `.csv` file hi upload karein!")
        return

    status_message = await update.message.reply_text("📥 File processing chalu hai, thoda intezar karein...")

    try:
        new_file = await context.bot.get_file(document.file_id)
        await new_file.download_to_drive(CSV_FILE_PATH)
        
        # Nayi flexible verification
        test_questions = load_questions_from_csv()
        if test_questions:
            await status_message.edit_text(
                f"✅ **Success! Aapki CSV file update ho gayi hai.**\n"
                f"📊 Total **{len(test_questions)}** sawal mil gaye hain!\n\n"
                f"Ab aap bina kisi dikkat ke Blue Menu se quiz shuru kar sakte hain."
            )
        else:
            await status_message.edit_text(
                "❌ Bot ko file me columns sahi se nahi mile.\n"
                "Kripya check karein ki file me columns ke naam milte-julte hon, jaise: `question`, `option1`, `option2`, `option3`, `option4`, aur `correct`."
            )
            
    except Exception as e:
        await status_message.edit_text(f"❌ File save karne me error aaya: {e}")

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(MessageHandler(filters.Document.FileExtension("csv"), handle_csv_upload))
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
