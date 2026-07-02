import os
import csv
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

# Environment variables load karein (.env file ya Render se)
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Python function: CSV file se questions read karne ke liye
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

# /start command - Menu Buttons aur Welcome Message
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Yeh aapke bot ke niche Menu Buttons bana dega
    keyboard = [["📝 Start Quiz"], ["ℹ️ Help & Info"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    welcome_text = (
        "👋 **Namaste! 'The Academic' Quiz Bot me aapka swagat hai.**\n\n"
        "Aap niche diye gaye Menu buttons ka use karke quiz shuru kar sakte hain.\n\n"
        "👉 **📝 Start Quiz** par click karein aur apna test shuru karein!"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

# Python function: Buttons ke clicks ko handle karne ke liye
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    if user_text == "📝 Start Quiz":
        questions = load_questions_from_csv()
        
        if not questions:
            await update.message.reply_text("⚠️ Sorry! Abhi database me koi sawal nahi mila. Kripya questions.csv file check karein.")
            return

        # Randomly ek sawal chunein
        quiz_item = random.choice(questions)
        
        # Telegram native Quiz poll send karne ka Python command
        await context.bot.send_poll(
            chat_id=update.effective_chat.id,
            question=quiz_item["question"],
            options=quiz_item["options"],
            type="quiz",
            correct_option_id=quiz_item["correct"],
            explanation=quiz_item["explanation"],
            open_period=30  # 30 Seconds ka timer
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

if __name__ == "__main__":
    if not TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN nahi mila!")
        exit(1)
        
    print("CSV Quiz Bot start ho raha hai...")
    app = Application.builder().token(TOKEN).build()

    # Handlers register karein
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    print("Bot live hai!")
    app.run_polling()
