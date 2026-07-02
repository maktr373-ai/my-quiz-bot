import os
import csv
import random
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Default file name jahan naye questions save honge
CSV_FILE_PATH = "questions.csv"

def load_questions_from_csv():
    questions_list = []
    if not os.path.exists(CSV_FILE_PATH):
        return questions_list
    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                questions_list.append({
                    "question": row["question"],
                    "options": [row["option1"], row["option2"], row["option3"], row["option4"]],
                    "correct": int(row["correct"]),
                    "explanation": row["explanation"]
                })
    except Exception as e:
        print(f"Error reading CSV: {e}")
    return questions_list

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "📊 **Nayi CSV File Upload karein:** Aap koi bhi `.csv` file directly is chat me bhej sakte hain, bot use automatically set kar lega!\n\n"
        "🧩 **Quiz Shuru Karein:** Niche left side wale **Blue Menu Button** par click karke `📝 Start Quiz` select karein."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = load_questions_from_csv()
    if not questions:
        await update.message.reply_text("⚠️ Sorry! Database me koi sawal nahi mila. Kripya pehle ek CSV file upload karein.")
        return
    
    quiz_item = random.choice(questions)
    await context.bot.send_poll(
        chat_id=update.effective_chat.id,
        question=quiz_item["question"],
        options=quiz_item["options"],
        type="quiz",
        correct_option_id=quiz_item["correct"],
        explanation=quiz_item["explanation"],
        open_period=30
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📌 **Bot Information:**\n"
        "1. Nayi questions file lagane ke liye direct `.csv` file attach karke bhej dein.\n"
        "2. Quiz khelne ke liye Blue Menu me se **📝 Start Quiz** par click karein."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# --- NAYA FUNCTION: CSV FILE HANDLE KARNE KE LIYE ---
async def handle_csv_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    
    # Check karenge ki file `.csv` hi hai na
    if not document.file_name.endswith('.csv'):
        await update.message.reply_text("⚠️ Kripya sirf `.csv` format wali file hi upload karein!")
        return

    await update.message.reply_text("📥 File mil gayi hai! Isko processing aur save kiya ja raha hai...")

    try:
        # Telegram server se file download karenge
        new_file = await context.bot.get_file(document.file_id)
        # Purani questions.csv ko is nayi file se replace kar denge
        await new_file.download_to_drive(CSV_FILE_PATH)
        
        await update.message.reply_text("✅ **Success! Nayi CSV file successfully update ho gayi hai.**\n\nAb aap Blue Menu se naya quiz shuru kar sakte hain!")
    except Exception as e:
        await update.message.reply_text(f"❌ File save karne me kuch dikkat aayi: {e}")

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("help", help_command))
    
    # Naya handler jo file upload detect karega
    app.add_handler(MessageHandler(filters.Document.FileExtension("csv"), handle_csv_upload))
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
