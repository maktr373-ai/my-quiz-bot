import os
import csv
import random
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Environment variables load karein
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# CSV file se questions read karne ka function
def load_questions_from_csv():
    questions_list = []
    file_path = "questions.csv"
    
    if not os.path.exists(file_path):
        print(f"Error: {file_path} file nahi mili!")
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
        print(f"CSV read karne me error: {e}")
        
    return questions_list

# /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📝 Start Quiz"], ["ℹ️ Help & Info"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "Aap niche diye gaye Menu buttons ka use karke quiz shuru kar sakte hain.\n\n"
        "👉 **📝 Start Quiz** par click karein aur apna test shuru karein!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# Menu Handle karne ka function
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    if user_text == "📝 Start Quiz":
        questions = load_questions_from_csv()
        
        if not questions:
            await update.message.reply_text("⚠️ Sorry! Abhi database me koi sawal nahi mila.")
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
        
    elif user_text == "ℹ️ Help & Info":
        help_text = (
            "📌 **Bot Information:**\n"
            "Ye bot CSV file se automatic questions generate karta hai.\n\n"
            "Naya sawal paane ke liye baar-baar **📝 Start Quiz** button par click karein."
        )
        await update.message.reply_text(help_text, parse_mode="Markdown")
    else:
        await update.message.reply_text("Kripya niche diye gaye Menu buttons me se hi kisi ek ko chunein.")

# Main function jisme naya loop handler lagaya hai Python 3.14 ke liye
def main():
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN nahi mila!")
        return
        
    print("CSV Quiz Bot start ho raha hai...")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    print("Bot live hai!")
    
    # Python 3.14 and library v21 compatibility fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
