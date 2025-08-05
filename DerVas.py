import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import random
import os
from datetime import datetime, date
import pytz

# Включим логирование для отладки
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.environ.get('TOKEN')

# Глобальные константы для челленджа
TOTAL_DAYS = 100
TOTAL_PUSHUPS = 10000
# --- НОВОЕ: Устанавливаем часовой пояс для Барселоны ---
BARCELONA_TIMEZONE = pytz.timezone('Europe/Madrid')

# Словари для хранения данных пользователей и их состояния
user_data = {}
user_state = {}

# Состояния для многошагового диалога
# --- ИЗМЕНЕНО: Удалено состояние AWAITING_DAY ---
AWAITING_PUSHUPS_INITIAL = 1
AWAITING_ADD_PUSHUPS = 2

# Список советов по отжиманиям
pushup_tips = [
    "Техника важнее количества! Следите, чтобы спина была прямой, а локти не разводились в стороны.",
    "Не забывайте про разминку перед тренировкой, чтобы избежать травм.",
    "Отжимания можно делать с колен, если обычные пока слишком сложны. Главное — прогресс!",
    "Для увеличения нагрузки попробуйте отжиматься с узкой постановкой рук, это отлично прокачает трицепс.",
    "Старайтесь делать отжимания в одно и то же время, чтобы выработать привычку."
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Запускает начальную настройку пользователя."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # --- НОВОЕ: Упрощенная логика старта ---
    # Бот больше не спрашивает про день.
    if user_id not in user_data:
        user_data[user_id] = {
            'name': user_name, 
            'pushups': 0, 
            'day': 1, 
            'last_pushup_date': date.today().isoformat()
        }
    
    await update.message.reply_text(
        f"Привет! Это бот для челленджа DerVas на 100 дней и 10000 отжиманий.\n\n"
        f"Мы начинаем с 1-го дня. Сколько отжиманий вы уже сделали?"
    )
    user_state[user_id] = AWAITING_PUSHUPS_INITIAL

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик сообщений, который реагирует в зависимости от состояния пользователя."""
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id in user_state:
        try:
            value = int(text)
            if value >= 0:
                # --- ИЗМЕНЕНО: Объединена логика начального ввода и добавления отжиманий ---
                current_state = user_state[user_id]
                
                if current_state == AWAITING_PUSHUPS_INITIAL:
                    user_data[user_id]['pushups'] = value
                    del user_state[user_id]
                    await update.message.reply_text(
                        f"Понял! Ваши данные сохранены. Удачи в челлендже!\n"
                        f"Чтобы посмотреть меню, используйте команду /challenge."
                    )
                elif current_state == AWAITING_ADD_PUSHUPS:
                    # --- НОВОЕ: Логика автоматического обновления дня ---
                    now_barcelona = datetime.now(BARCELONA_TIMEZONE).date()
                    last_date_str = user_data[user_id].get('last_pushup_date')
                    last_date = datetime.fromisoformat(last_date_str).date() if last_date_str else now_barcelona

                    if now_barcelona > last_date:
                        user_data[user_id]['day'] += 1
                        user_data[user_id]['last_pushup_date'] = now_barcelona.isoformat()
                        await update.message.reply_text(f"🚀 Наступил новый день челленджа! Теперь вы на {user_data[user_id]['day']}-м дне.")

                    user_data[user_id]['pushups'] += value
                    del user_state[user_id]
                    await update.message.reply_text(f"Добавлено! Теперь у вас {user_data[user_id]['pushups']} отжиманий.")
                    await show_progress(update, context) # Показываем прогресс после добавления
            else:
                await update.message.reply_text("Количество отжиманий не может быть отрицательным. Пожалуйста, введите корректное число.")
        except ValueError:
            await update.message.reply_text("Пожалуйста, введите число.")
    else:
        return

async def challenge(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /challenge. Отображает основное меню."""
    user_id = update.effective_user.id
    if user_id not in user_data:
        await update.message.reply_text(
            "Кажется, вы не прошли начальную настройку. Пожалуйста, используйте команду /start."
        )
        return

    keyboard = [
        [InlineKeyboardButton("Добавить отжимания", callback_data="add_pushups")],
        [InlineKeyboardButton("Посмотреть мой прогресс", callback_data="view_progress")],
        [InlineKeyboardButton("Посмотреть общий прогресс", callback_data="view_all_progress")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("Что будем делать?", reply_markup=reply_markup)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки."""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    if query.data == "add_pushups":
        user_state[user_id] = AWAITING_ADD_PUSHUPS
        await query.edit_message_text("Сколько отжиманий вы сделали? Введите число.")
    elif query.data == "view_progress":
        await show_progress(update, context)
    elif query.data == "view_all_progress":
        await show_all_progress(update, context)

async def show_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Функция для отображения прогресса конкретного пользователя."""
    user_id = update.effective_user.id
    if update.callback_query:
        message = update.callback_query.message
    else:
        message = update.message
        
    if user_id not in user_data:
        await message.reply_text("Кажется, вы не прошли начальную настройку. Пожалуйста, используйте команду /start.")
        return

    data = user_data[user_id]
    # --- НОВОЕ: Автоматически получаем текущий день ---
    current_day = data['day']
    current_pushups = data['pushups']
    
    required_pushups_total = current_day * 100
    progress_percentage = (current_pushups / TOTAL_PUSHUPS) * 100
    
    bar_length = 20
    filled_blocks = int(progress_percentage / (100 / bar_length))
    empty_blocks = bar_length - filled_blocks
    progress_bar = f"[{'█' * filled_blocks}{'░' * empty_blocks}]"
    
    progress_text = f"Ваш прогресс на {current_day}-й день:\n\n"
    progress_text += f"Всего отжиманий: **{current_pushups}** / **{TOTAL_PUSHUPS}**\n"
    progress_text += f"Прогресс: `{progress_bar}` `{progress_percentage:.2f}%`\n\n"

    if current_pushups < required_pushups_total:
        behind_by = required_pushups_total - current_pushups
        daily_catch_up_1_day = (behind_by + 100)
        daily_catch_up_2_days = (behind_by / 2) + 100
        daily_catch_up_3_days = (behind_by / 3) + 100
        
        progress_text += f"⚠️ Вы отстаете от графика на **{behind_by}** отжиманий.\n"
        progress_text += f"Чтобы нагнать, вам нужно делать:\n"
        progress_text += f"- Сегодня: **{daily_catch_up_1_day:.0f}** отжиманий.\n"
        progress_text += f"- В течение 2 дней: **{daily_catch_up_2_days:.0f}** отжиманий в день.\n"
        progress_text += f"- В течение 3 дней: **{daily_catch_up_3_days:.0f}** отжиманий в день.\n\n"
        
    progress_text += f"💡 Совет: {random.choice(pushup_tips)}"
    
    if update.callback_query:
         await message.edit_text(progress_text, parse_mode='Markdown')
    elif update.message:
         await message.reply_text(progress_text, parse_mode='Markdown')

async def show_all_progress(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Функция для отображения общего прогресса всех участников."""
    message = update.callback_query.message

    if not user_data:
        await message.edit_text("Пока никто не начал челлендж. Будьте первым!")
        return

    sorted_users = sorted(user_data.items(), key=lambda item: item[1]['pushups'], reverse=True)
    
    all_progress_text = "📊 **Общий прогресс участников:**\n\n"
    
    for _, data in sorted_users:
        user_name = data['name']
        current_pushups = data['pushups']
        # --- НОВОЕ: Автоматически получаем текущий день ---
        current_day = data['day']
        
        progress_percentage = (current_pushups / TOTAL_PUSHUPS) * 100
        bar_length = 15
        filled_blocks = int(progress_percentage / (100 / bar_length))
        empty_blocks = bar_length - filled_blocks
        progress_bar = f"[{'█' * filled_blocks}{'░' * empty_blocks}]"
        
        required_pushups_total = current_day * 100
        status = "✅ Нагоняет график" if current_pushups >= required_pushups_total else "🔴 Отстает"
        
        all_progress_text += (
            f"**{user_name}**: ({current_pushups} / {TOTAL_PUSHUPS})\n"
            f"`{progress_bar}` `{progress_percentage:.2f}%`\n"
            f"Статус: {status}\n\n"
        )
    
    await message.edit_text(all_progress_text, parse_mode='Markdown')

def main() -> None:
    """Запускает бота."""
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("challenge", challenge))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback_query))

    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()