import os
import csv
import random
import asyncio
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def load_questions_from_csv():
    questions_list = []
    file_path = "questions.csv"
    if not os.path.exists(file_path):
        return questions_list
    try:
        with open(file_path, mode='r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                questions_list.append({
                    "question": row["question"],
                    "options": [row["option1"], row["option2"], row["option3"], row["option4"]],
                    "correct": int(row["correct"]),
                    "explanation": row["explanation"]
                })
    except Exception as e:
        print(f"Error: {e}")
    return questions_list

# Yeh function un niche wale bade buttons ko hamesha ke liye mita dega
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "Neeche ke bade buttons hata diye gaye hain. Naya sawal paane ke liye ab left side wale **Blue Menu Button** par click karein!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())

async def quiz_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    questions = load_questions_from_csv()
    if not questions:
        await update.message.reply_text("⚠️ Sorry! Questions nahi mile.")
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
        "Ye bot aapki CSV file se automatic questions generate karta hai.\n\n"
        "Naya sawal paane ke liye Blue Menu button me se **📝 Start Quiz** par click karein."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

def main():
    if not TOKEN:
        return
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("quiz", quiz_command))
    app.add_handler(CommandHandler("help", help_command))
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
