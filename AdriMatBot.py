import os
import random
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext, MessageHandler, filters, JobQueue

# Setup logging to catch potential errors
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- Bot's Persona and Messages ---
# This dictionary now includes encouraging messages and uses 'Adri' for a personal touch.
MESSAGES = {
    "en": {
        "start": "Hello Adri! I'm your personal math coach. I'll send you fun math puzzles to solve. Let's get started!",
        "problem_intro": "Time for some math fun! Here are 10 new problems for you, Adri:",
        "question": "Problem {number}:",
        "answer_correct": "That's exactly right, Adri! Great job!",
        "answer_incorrect": "Not quite, Adri. The correct answer was {correct_answer}. You'll get it next time!",
        "congratulations": "Fantastic! You answered {correct_count} out of 10 questions correctly. I'll adjust the next batch of problems just for you!",
    },
    "ru": {
        "start": "Привет, Адри! Я твой личный тренер по математике. Буду присылать тебе весёлые математические задачки. Давай начнём!",
        "problem_intro": "Время для математики! Вот 10 новых задач для тебя, Адри:",
        "question": "Задача {number}:",
        "answer_correct": "Именно так, Адри! Отличная работа!",
        "answer_incorrect": "Не совсем. Правильный ответ был {correct_answer}. У тебя всё получится в следующий раз!",
        "congratulations": "Фантастика! Ты ответила правильно на {correct_count} из 10 вопросов. Я подготовлю следующий набор задач специально для тебя!",
    },
    "es": {
        "start": "¡Hola, Adri! Soy tu entrenador de matemáticas personal. Te enviaré divertidos acertijos matemáticos para resolver. ¡Empecemos!",
        "problem_intro": "¡Hora de divertirse con las matemáticas! Aquí tienes 10 problemas nuevos para ti, Adri:",
        "question": "Problema {number}:",
        "answer_correct": "¡Eso es, Adri! ¡Excelente trabajo!",
        "answer_incorrect": "Casi. La respuesta correcta era {correct_answer}. ¡Lo harás mejor la próxima vez!",
        "congratulations": "¡Fantástico! Respondiste correctamente a {correct_count} de 10 preguntas. ¡Ajustaré el próximo lote de problemas solo para ti!",
    },
    "ca": {
        "start": "Hola, Adri! Sóc el teu entrenador de matemàtiques personal. T'enviaré trencaclosques de matemàtiques divertits per resoldre. Comencem!",
        "problem_intro": "Temps per a la diversió amb les mates! Aquí tens 10 problemes nous per a tu, Adri:",
        "question": "Problema {number}:",
        "answer_correct": "Això és, Adri! Molt bona feina!",
        "answer_incorrect": "No del tot. La resposta correcta era {correct_answer}. La pròxima vegada ho faràs millor!",
        "congratulations": "Fantàstic! Has respost correctament a {correct_count} de 10 preguntes. Ajustaré el pròxim lot de problemes només per a tu!",
    },
}

# The languages we will use for the questions themselves
MATH_LANGUAGES = ["en", "ru", "es", "ca"]

# --- Core Logic for Math Problems ---
def generate_math_problem(difficulty="easy"):
    """
    Generates a math problem with varying difficulty and specific constraints.
    """
    # EASY problems: Simple addition and subtraction for an 8-year-old
    if difficulty == "easy":
        num1 = random.randint(5, 20)
        num2 = random.randint(1, 10)
        operation = random.choice(['+', '-'])
        if operation == '+':
            question = f"{num1} + {num2}"
            answer = num1 + num2
        else:  # '-'
            question = f"{num1} - {num2}"
            answer = num1 - num2
    
    # HARD problems: Include multiplication and division with the requested constraints
    else:  # difficulty == "hard"
        operation = random.choice(['+', '-', '*', '/'])
        if operation == '+':
            num1 = random.randint(10, 40)
            num2 = random.randint(10, 30)
            question = f"{num1} + {num2}"
            answer = num1 + num2
        elif operation == '-':
            num1 = random.randint(20, 50)
            num2 = random.randint(5, 20)
            question = f"{num1} - {num2}"
            answer = num1 - num2
        elif operation == '*':
            # Multiplication where result is at most 81
            answer = random.randint(1, 9)
            num2 = random.randint(1, 9)
            num1 = int(81 / num2)
            num1 = random.randint(1, num1)
            question = f"{num1} * {num2}"
            answer = num1 * num2
        else:  # '/'
            # Division that results in a whole number and the dividend is at most 81
            answer = random.randint(2, 9)
            num2 = random.randint(2, 9)
            num1 = answer * num2
            if num1 > 81: # Ensure dividend is not over 81
                num2 = int(81/answer)
                num2 = random.randint(2, num2)
                num1 = answer * num2
            question = f"{num1} / {num2}"
    
    return question, answer

# --- Command Handlers and Scheduled Jobs ---
async def start_command(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message and starts the problem-sending job."""
    user_lang = update.effective_user.language_code
    message_text = MESSAGES.get(user_lang, MESSAGES["en"])["start"]
    await update.message.reply_text(message_text)
    
    # Start the scheduled task immediately
    await start_problems_command(update, context)

async def start_problems_command(update: Update, context: CallbackContext) -> None:
    """Starts the job to send math problems every 6 hours."""
    chat_id = update.effective_chat.id
    
    # Check if a job for this chat already exists to prevent duplicates
    if 'job' in context.chat_data:
        job = context.chat_data['job']
        if not job.enabled:
            job.enabled = True
            await update.message.reply_text("I'll start sending math problems again!")
        else:
            await update.message.reply_text("I am already sending math problems to you!")
        return

    # Schedule a new job to send problems every 6 hours (21600 seconds)
    # The first run will happen 1 minute after this command is issued
    job = context.job_queue.run_repeating(send_problems, interval=21600, first=60, chat_id=chat_id, name="math_problems_job")
    context.chat_data['job'] = job
    
    await update.message.reply_text("I'll now send you a new batch of 10 math problems every 6 hours! Let's get started with your first set!")

async def send_problems(context: CallbackContext) -> None:
    """Sends a series of 10 math problems to the chat."""
    job = context.job
    language_code = random.choice(MATH_LANGUAGES)
    chat_id = job.chat_id

    # Check Adri's previous performance to determine difficulty
    # If the user has a high score (more than 70% correct), increase difficulty
    correct_answers = context.chat_data.get('correct_answers', 0)
    total_questions = context.chat_data.get('total_questions', 0)
    
    difficulty = "easy"
    if total_questions > 0 and (correct_answers / total_questions) >= 0.7:
        difficulty = "hard"
    
    # Reset the session's score trackers for the new batch of problems
    context.chat_data['correct_answers'] = 0
    context.chat_data['total_questions'] = 0
    context.chat_data['current_question_number'] = 0
    context.chat_data['current_answers'] = {}
    
    message_text = MESSAGES.get(language_code, MESSAGES["en"])["problem_intro"]
    await context.bot.send_message(chat_id=chat_id, text=message_text)

    for i in range(1, 11):
        question, answer = generate_math_problem(difficulty)
        
        question_text = MESSAGES.get(language_code, MESSAGES["en"])["question"].format(number=i)
        
        # Store the answer for the current set of problems
        context.chat_data['current_answers'][str(i)] = answer
        
        await context.bot.send_message(chat_id=chat_id, text=f"{question_text} {question} = ?")
    
    context.chat_data['total_questions'] = 10
    
async def handle_message(update: Update, context: CallbackContext) -> None:
    """Handles user answers, checks for correctness, and provides feedback."""
    user_answer = update.message.text
    chat_data = context.chat_data
    
    if 'current_answers' not in chat_data:
        return

    # Look for an unanswered question
    for i in range(1, 11):
        question_key = str(i)
        if question_key in chat_data['current_answers']:
            correct_answer = chat_data['current_answers'][question_key]
            
            try:
                user_answer_int = int(user_answer)
                is_correct = (user_answer_int == correct_answer)
            except ValueError:
                # The user didn't enter a number
                return

            user_lang = update.effective_user.language_code
            if is_correct:
                chat_data['correct_answers'] += 1
                message_text = MESSAGES.get(user_lang, MESSAGES["en"])["answer_correct"]
            else:
                message_text = MESSAGES.get(user_lang, MESSAGES["en"])["answer_incorrect"].format(correct_answer=correct_answer)
            
            await update.message.reply_text(message_text)
            
            # Remove the answered question from the list
            del chat_data['current_answers'][question_key]
            
            # Check if all questions are answered
            if not chat_data['current_answers']:
                correct_count = chat_data['correct_answers']
                message_text = MESSAGES.get(user_lang, MESSAGES["en"])["congratulations"].format(correct_count=correct_count)
                await update.message.reply_text(message_text)
            
            # Stop after processing the first valid answer
            break
            
def main() -> None:
    """Start the bot."""
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
    if not TELEGRAM_TOKEN:
        logging.error("Error: TELEGRAM_TOKEN environment variable is not set.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Handlers for commands
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("startproblems", start_problems_command))

    # Handler for user's answers (any text that isn't a command)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()