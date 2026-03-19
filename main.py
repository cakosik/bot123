import logging
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from mysql.connector import Error

# Настройки бота
BOT_TOKEN = "8635962132:AAHuhG1PhLMRNTGgBpTPNTBpBdmCg7LjxQ8"  # Замените на ваш токен

# Настройки подключения к MySQL
MYSQL_CONFIG = {
    'host': '46.174.50.9',           # Адрес сервера MySQL
    'port': 3306,                       # Порт MySQL (обычно 3306)
    'database': 'u42263_logsaytabaza',      # Имя базы данных
    'user': 'u42263_sayt',              # Имя пользователя MySQL
    'password': '8S7j1D9h1U',                # Пароль MySQL
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connect_timeout': 10,
    'autocommit': True
}

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Бот
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Состояния
class UserStates(StatesGroup):
    selecting_user = State()
    selecting_status = State()
    confirming = State()

# Эмодзи
EMOJI = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "users": "👥",
    "confirm": "✔️",
    "cancel": "❌",
    "menu": "📋",
    "db": "🗄️",
    "rocket": "🚀",
    "mysql": "🐬",
    "refresh": "🔄",
    "active": "🟢",
    "inactive": "🔴",
    "arrow": "➡️"
}

# Подключение к БД
def get_db():
    try:
        return mysql.connector.connect(**MYSQL_CONFIG)
    except Error as e:
        logger.error(f"Ошибка MySQL: {e}")
        return None

# Получить всех пользователей
def get_users():
    conn = get_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, email, status 
            FROM site_users 
            ORDER BY 
                CASE status 
                    WHEN 'active' THEN 1 
                    WHEN 'inactive' THEN 2 
                    ELSE 3 
                END,
                username
        """)
        users = cursor.fetchall()
        conn.close()
        return users
    except Error as e:
        logger.error(f"Ошибка получения пользователей: {e}")
        return []

# Получить одного пользователя
def get_user(user_id):
    conn = get_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, username, email, status FROM site_users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Error as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        return None

# Обновить статус
def update_status(user_id, new_status):
    conn = get_db()
    if not conn:
        return False, "Нет подключения к БД"
    
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE site_users SET status = %s WHERE id = %s",
            (new_status, user_id)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        
        if affected > 0:
            return True, f"Статус изменен на {new_status}"
        else:
            return False, "Пользователь не найден"
    except Error as e:
        logger.error(f"Ошибка обновления: {e}")
        return False, str(e)

# Старт
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    text = f"""
{EMOJI['rocket']} <b>Admin Bot</b>
━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} MySQL: {MYSQL_CONFIG['host']}
{EMOJI['users']} Таблица: site_users
{EMOJI['active']} active
{EMOJI['inactive']} inactive

/menu - список пользователей
/checkdb - проверить БД
    """
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton(f"{EMOJI['menu']} Меню", callback_data="menu")
    )
    
    await message.reply(text, parse_mode="HTML", reply_markup=kb)

# Меню
@dp.message_handler(commands=['menu'])
async def menu(message: types.Message):
    await show_users(message)

# Показать пользователей
async def show_users(message: types.Message):
    loading = await message.reply(f"{EMOJI['refresh']} Загрузка...")
    
    users = get_users()
    
    if not users:
        await loading.edit_text(f"{EMOJI['error']} Нет пользователей")
        return
    
    # Статистика
    active = sum(1 for u in users if u['status'] == 'active')
    inactive = sum(1 for u in users if u['status'] == 'inactive')
    
    header = f"""
{EMOJI['users']} <b>Пользователи</b> ({len(users)})
{EMOJI['active']} Active: {active} | {EMOJI['inactive']} Inactive: {inactive}
━━━━━━━━━━━━━━━━━━
<b>Выбери пользователя:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        # Статус
        if user['status'] == 'active':
            status_emoji = EMOJI['active']
        elif user['status'] == 'inactive':
            status_emoji = EMOJI['inactive']
        else:
            status_emoji = "⚪"
        
        # Имя и email
        name = (user['username'] or "Без имени")[:15]
        email = (user['email'] or "Нет email")[:20]
        
        if len(name) >= 15:
            name += "..."
        if len(email) >= 20:
            email += "..."
        
        kb.add(InlineKeyboardButton(
            f"{status_emoji} {name} | {email}",
            callback_data=f"user_{user['id']}"
        ))
    
    kb.add(InlineKeyboardButton(
        f"{EMOJI['cancel']} Закрыть",
        callback_data="close"
    ))
    
    await loading.delete()
    await message.reply(header, parse_mode="HTML", reply_markup=kb)

# Выбор пользователя
@dp.callback_query_handler(lambda c: c.data.startswith('user_'))
async def user_selected(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id)
    
    user_id = callback.data.split('_')[1]
    user = get_user(user_id)
    
    if not user:
        await bot.send_message(
            callback.from_user.id,
            f"{EMOJI['error']} Пользователь не найден"
        )
        return
    
    # Сохраняем данные
    await state.update_data(
        user_id=user['id'],
        username=user['username'],
        email=user['email'],
        current_status=user['status']
    )
    
    # Текущий статус
    if user['status'] == 'active':
        status_text = f"{EMOJI['active']} Active"
    elif user['status'] == 'inactive':
        status_text = f"{EMOJI['inactive']} Inactive"
    else:
        status_text = "⚪ Другой"
    
    info = f"""
{EMOJI['info']} <b>Информация</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
{EMOJI['arrow']} <b>Текущий статус:</b> {status_text}

<b>Выбери новый статус:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['active']} Active", callback_data="set_active"),
        InlineKeyboardButton(f"{EMOJI['inactive']} Inactive", callback_data="set_inactive"),
        InlineKeyboardButton(f"{EMOJI['cancel']} Отмена", callback_data="cancel")
    )
    
    await bot.send_message(
        callback.from_user.id,
        info,
        parse_mode="HTML",
        reply_markup=kb
    )
    
    await UserStates.selecting_status.set()

# Выбор статуса
@dp.callback_query_handler(lambda c: c.data in ['set_active', 'set_inactive'], state=UserStates.selecting_status)
async def status_selected(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id)
    
    # Какой статус выбрали
    if callback.data == 'set_active':
        new_status = 'active'
        status_emoji = EMOJI['active']
        status_name = 'Active'
    else:
        new_status = 'inactive'
        status_emoji = EMOJI['inactive']
        status_name = 'Inactive'
    
    # Сохраняем выбор
    await state.update_data(new_status=new_status)
    
    data = await state.get_data()
    
    confirm = f"""
{EMOJI['warning']} <b>Подтверждение</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
📧 <b>Email:</b> {data['email']}
{EMOJI['arrow']} <b>Текущий:</b> {data['current_status']}
{status_emoji} <b>Новый:</b> {status_name}

<b>Точно изменить?</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['confirm']} Да", callback_data="confirm_yes"),
        InlineKeyboardButton(f"{EMOJI['cancel']} Нет", callback_data="confirm_no")
    )
    
    await bot.send_message(
        callback.from_user.id,
        confirm,
        parse_mode="HTML",
        reply_markup=kb
    )
    
    await UserStates.confirming.set()

# Подтверждение
@dp.callback_query_handler(lambda c: c.data == 'confirm_yes', state=UserStates.confirming)
async def confirm_change(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id)
    
    data = await state.get_data()
    
    processing = await bot.send_message(
        callback.from_user.id,
        f"{EMOJI['refresh']} Обновляю..."
    )
    
    # Меняем статус
    success, msg = update_status(data['user_id'], data['new_status'])
    
    await processing.delete()
    
    if success:
        if data['new_status'] == 'active':
            result_emoji = EMOJI['active']
            result_text = "Active"
        else:
            result_emoji = EMOJI['inactive']
            result_text = "Inactive"
        
        final = f"""
{EMOJI['success']} <b>Готово!</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
{result_emoji} <b>Статус:</b> {result_text}

Статус обновлен в БД
        """
    else:
        final = f"""
{EMOJI['error']} <b>Ошибка!</b>
━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
<b>Ошибка:</b> {msg}

Попробуй еще раз
        """
    
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton(f"{EMOJI['menu']} В меню", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJI['cancel']} Закрыть", callback_data="close")
    )
    
    await bot.send_message(
        callback.from_user.id,
        final,
        parse_mode="HTML",
        reply_markup=kb
    )
    
    await state.finish()

# Отмена подтверждения
@dp.callback_query_handler(lambda c: c.data == 'confirm_no', state=UserStates.confirming)
async def cancel_confirm(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id)
    await state.finish()
    
    await bot.send_message(
        callback.from_user.id,
        f"{EMOJI['cancel']} Отменено"
    )

# Отмена везде
@dp.callback_query_handler(lambda c: c.data == 'cancel', state='*')
async def cancel_all(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id)
    await state.finish()
    
    await bot.send_message(
        callback.from_user.id,
        f"{EMOJI['cancel']} Отменено"
    )

# Закрыть
@dp.callback_query_handler(lambda c: c.data == 'close')
async def close_msg(callback: types.CallbackQuery):
    await bot.answer_callback_query(callback.id)
    await bot.delete_message(callback.from_user.id, callback.message.message_id)

# Проверка БД
@dp.message_handler(commands=['checkdb'])
async def check_db(message: types.Message):
    status = await message.reply(f"{EMOJI['refresh']} Проверка...")
    
    conn = get_db()
    if not conn:
        await status.edit_text(
            f"{EMOJI['error']} Нет подключения\nХост: {MYSQL_CONFIG['host']}"
        )
        return
    
    try:
        cursor = conn.cursor()
        
        # Версия
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        # Таблица
        cursor.execute("SHOW TABLES LIKE 'site_users'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM site_users")
            total = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM site_users WHERE status = 'active'")
            active = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM site_users WHERE status = 'inactive'")
            inactive = cursor.fetchone()[0]
            
            text = f"""
{EMOJI['success']} <b>MySQL OK</b>
━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} Хост: {MYSQL_CONFIG['host']}
{EMOJI['db']} Версия: {version[0]}
{EMOJI['users']} Всего: {total}
{EMOJI['active']} Active: {active}
{EMOJI['inactive']} Inactive: {inactive}
            """
        else:
            text = f"{EMOJI['error']} Нет таблицы site_users"
        
        conn.close()
        await status.edit_text(text, parse_mode="HTML")
        
    except Error as e:
        await status.edit_text(f"{EMOJI['error']} {e}")

# Помощь
@dp.message_handler(commands=['help'])
async def help_cmd(message: types.Message):
    text = f"""
{EMOJI['info']} <b>Команды</b>
━━━━━━━━━━━━━━━━━━
/menu - список пользователей
/checkdb - проверка MySQL
/help - это меню

<b>Статусы:</b>
{EMOJI['active']} active
{EMOJI['inactive']} inactive
    """
    
    await message.reply(text, parse_mode="HTML")

# Запуск
if __name__ == '__main__':
    print(f"""
{EMOJI['rocket']} ═══════════════════════
{EMOJI['rocket']}  Бот запущен
{EMOJI['rocket']} ═══════════════════════
{EMOJI['mysql']}  Хост: {MYSQL_CONFIG['host']}
{EMOJI['users']}  Таблица: site_users
{EMOJI['active']}  Статус: active
{EMOJI['inactive']}  Статус: inactive
{EMOJI['rocket']} ═══════════════════════
    """)
    
    executor.start_polling(dp, skip_updates=True)
