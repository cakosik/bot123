import logging
import mysql.connector
import asyncio
import json
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

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Класс для состояний
class UserStates(StatesGroup):
    selecting_user = State()
    confirming = State()

# Красивые эмодзи
EMOJIS = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "users": "👥",
    "settings": "⚙️",
    "confirm": "✔️",
    "cancel": "❌",
    "menu": "📋",
    "database": "🗄️",
    "rocket": "🚀",
    "star": "⭐",
    "mysql": "🐬",
    "lock": "🔒",
    "refresh": "🔄"
}

# Функция для подключения к MySQL
def get_db_connection():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        logger.info(f"{EMOJIS['mysql']} Успешное подключение к MySQL")
        return conn
    except Error as e:
        logger.error(f"{EMOJIS['error']} Ошибка подключения к MySQL: {e}")
        return None

# Функция для проверки подключения к БД
@dp.message_handler(commands=['checkdb'])
async def check_database(message: types.Message):
    status_msg = await message.reply(f"{EMOJIS['refresh']} Проверка подключения к MySQL...")
    
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()
            
            success_text = f"""
{EMOJIS['success']} <b>Подключение к MySQL успешно!</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJIS['mysql']} <b>Версия MySQL:</b> {version[0]}
{EMOJIS['database']} <b>База данных:</b> {db_name[0]}
{EMOJIS['lock']} <b>Хост:</b> {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}
            """
            
            await status_msg.edit_text(success_text, parse_mode="HTML")
            conn.close()
        except Error as e:
            await status_msg.edit_text(
                f"{EMOJIS['error']} <b>Ошибка при запросе к БД:</b>\n<code>{e}</code>",
                parse_mode="HTML"
            )
    else:
        await status_msg.edit_text(
            f"{EMOJIS['error']} <b>Не удалось подключиться к MySQL</b>\n"
            f"Проверьте настройки подключения.",
            parse_mode="HTML"
        )

# Функция для получения списка пользователей
def get_users_list():
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Предполагаем, что таблица называется site_users
        # Измените запрос под вашу структуру БД
        cursor.execute("""
            SELECT id, username, email, status 
            FROM site_users 
            ORDER BY username
        """)
        users = cursor.fetchall()
        conn.close()
        return users
    except Error as e:
        logger.error(f"Ошибка получения пользователей: {e}")
        return []

# Функция для обновления статуса пользователя
def update_user_status(user_id):
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Создаем JSON с правами
        permissions = {
            "view_logs": True,
            "view_admin_logs": True,
            "view_forbes": True,
            "view_bonus_codes": True,
            "view_server_config": True,
            "edit_server_config": True,
            "view_numbers": True,
            "view_bans": True,
            "view_money_logs": True,
            "view_manage_users": True,
            "manage_users": True
        }
        
        permissions_json = json.dumps(permissions, ensure_ascii=False)
        
        # Обновляем статус пользователя
        cursor.execute("""
            UPDATE site_users 
            SET status = %s 
            WHERE id = %s
        """, (permissions_json, user_id))
        
        conn.commit()
        affected_rows = cursor.rowcount
        conn.close()
        
        return affected_rows > 0
    except Error as e:
        logger.error(f"Ошибка обновления статуса: {e}")
        return False

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    welcome_text = f"""
{EMOJIS['rocket']} <b>Добро пожаловать в Admin Panel Bot (MySQL Edition)!</b>

Этот бот позволяет управлять правами пользователей в системе через удаленную MySQL базу данных.

{EMOJIS['mysql']} <b>Подключение к MySQL:</b> {MYSQL_CONFIG['host']}

<b>Доступные команды:</b>
{EMOJIS['menu']} /menu - Просмотр списка пользователей
{EMOJIS['database']} /checkdb - Проверка подключения к MySQL
{EMOJIS['info']} /help - Справка

<i>Разработано с заботой о безопасности</i> {EMOJIS['star']}
    """
    
    # Создаем красивую клавиатуру
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"{EMOJIS['menu']} Меню", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJIS['database']} Проверить БД", callback_data="checkdb"),
        InlineKeyboardButton(f"{EMOJIS['info']} Помощь", callback_data="help")
    )
    
    await message.reply(welcome_text, parse_mode="HTML", reply_markup=keyboard)

# Команда /menu
@dp.message_handler(commands=['menu'])
async def cmd_menu(message: types.Message):
    await show_users_menu(message)

# Команда /help
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    await show_help(message)

# Обработчик callback для меню
@dp.callback_query_handler(lambda c: c.data == 'menu')
async def process_menu_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await show_users_menu(callback_query.message)

# Обработчик callback для проверки БД
@dp.callback_query_handler(lambda c: c.data == 'checkdb')
async def process_checkdb_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await check_database(callback_query.message)

# Функция отображения меню пользователей
async def show_users_menu(message: types.Message):
    # Показываем статус загрузки
    loading_msg = await message.reply(f"{EMOJIS['refresh']} Загрузка списка пользователей...")
    
    users = get_users_list()
    
    if not users:
        error_text = f"""
{EMOJIS['error']} <b>Ошибка загрузки пользователей</b>

Не удалось получить список пользователей из базы данных MySQL.

<b>Возможные причины:</b>
• Нет подключения к MySQL серверу
• Таблица 'site_users' не существует
• В таблице нет пользователей
• Неправильные учетные данные

{EMOJIS['mysql']} <b>Хост:</b> {MYSQL_CONFIG['host']}
{EMOJIS['database']} <b>База:</b> {MYSQL_CONFIG['database']}

Используйте /checkdb для диагностики подключения.
        """
        await loading_msg.edit_text(error_text, parse_mode="HTML")
        return
    
    # Удаляем сообщение о загрузке
    await loading_msg.delete()
    
    # Создаем красивый заголовок
    header = f"""
{EMOJIS['users']} <b>Список пользователей</b> ({len(users)})
━━━━━━━━━━━━━━━━━━━━━━
{EMOJIS['mysql']} <b>MySQL:</b> {MYSQL_CONFIG['host']}
<i>Выберите пользователя для редактирования прав:</i>
    """
    
    # Создаем клавиатуру с пользователями
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        username = user['username'] if user['username'] else "Без имени"
        email = user['email'] if user['email'] else "Нет email"
        
        # Проверяем текущий статус
        try:
            if user['status']:
                status_data = json.loads(user['status']) if isinstance(user['status'], str) else user['status']
                has_permissions = any(status_data.values()) if isinstance(status_data, dict) else False
            else:
                has_permissions = False
        except:
            has_permissions = False
        
        status_emoji = EMOJIS['success'] if has_permissions else EMOJIS['error']
        
        # Обрезаем длинные имена
        display_name = username[:20] + "..." if len(username) > 20 else username
        display_email = email[:25] + "..." if len(email) > 25 else email
        
        button_text = f"{status_emoji} {display_name} | {display_email}"
        
        keyboard.add(
            InlineKeyboardButton(
                button_text,
                callback_data=f"user_{user['id']}"
            )
        )
    
    # Добавляем кнопки управления
    keyboard.row(
        InlineKeyboardButton(f"{EMOJIS['refresh']} Обновить", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJIS['cancel']} Закрыть", callback_data="close")
    )
    
    await message.reply(header, parse_mode="HTML", reply_markup=keyboard)

# Обработчик выбора пользователя
@dp.callback_query_handler(lambda c: c.data.startswith('user_'))
async def process_user_selection(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    
    user_id = callback_query.data.split('_')[1]
    
    # Показываем статус загрузки
    await bot.send_message(
        callback_query.from_user.id,
        f"{EMOJIS['refresh']} Загрузка информации о пользователе..."
    )
    
    # Получаем информацию о пользователе
    conn = get_db_connection()
    if not conn:
        await bot.send_message(
            callback_query.from_user.id,
            f"{EMOJIS['error']} Ошибка подключения к базе данных MySQL"
        )
        return
    
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, email, status FROM site_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        await bot.send_message(
            callback_query.from_user.id,
            f"{EMOJIS['error']} Пользователь не найден"
        )
        return
    
    # Сохраняем ID пользователя в состояние
    await state.update_data(selected_user_id=user_id, selected_user_name=user['username'])
    
    # Проверяем текущие права
    current_status = "Нет прав"
    if user['status']:
        try:
            status_data = json.loads(user['status']) if isinstance(user['status'], str) else user['status']
            if isinstance(status_data, dict):
                active_permissions = [k for k, v in status_data.items() if v]
                if active_permissions:
                    current_status = f"Есть права ({len(active_permissions)} активных)"
        except:
            current_status = "Ошибка в формате прав"
    
    # Показываем информацию о пользователе
    user_info = f"""
{EMOJIS['info']} <b>Информация о пользователе:</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
📊 <b>Текущий статус:</b> {current_status}

{EMOJIS['warning']} <b>Вы уверены, что хотите выдать ВСЕ права этому пользователю?</b>

<b>Права которые будут выданы:</b>
• Просмотр логов (view_logs)
• Просмотр логов администратора (view_admin_logs)
• Просмотр Forbes (view_forbes)
• Просмотр бонус кодов (view_bonus_codes)
• Просмотр конфига сервера (view_server_config)
• Редактирование конфига сервера (edit_server_config)
• Просмотр номеров (view_numbers)
• Просмотр банов (view_bans)
• Просмотр логов денег (view_money_logs)
• Просмотр управления пользователями (view_manage_users)
• Управление пользователями (manage_users)

{EMOJIS['mysql']} <b>База данных:</b> {MYSQL_CONFIG['database']}
    """
    
    # Создаем клавиатуру подтверждения
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"{EMOJIS['confirm']} Подтвердить", callback_data="confirm_yes"),
        InlineKeyboardButton(f"{EMOJIS['cancel']} Отмена", callback_data="cancel")
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        user_info,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await UserStates.confirming.set()

# Обработчик подтверждения
@dp.callback_query_handler(lambda c: c.data == 'confirm_yes', state=UserStates.confirming)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    
    # Показываем статус обработки
    processing_msg = await bot.send_message(
        callback_query.from_user.id,
        f"{EMOJIS['refresh']} Обновление прав пользователя в MySQL..."
    )
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = data.get('selected_user_id')
    user_name = data.get('selected_user_name')
    
    # Обновляем статус пользователя
    success = update_user_status(user_id)
    
    if success:
        result_text = f"""
{EMOJIS['success']} <b>Успешно!</b>

Пользователю <b>{user_name}</b> выданы все права доступа.

{EMOJIS['mysql']} <b>Изменения сохранены в MySQL</b>
{EMOJIS['rocket']} Права активированы немедленно.

<i>Статус пользователя обновлен в базе данных.</i>
        """
    else:
        result_text = f"""
{EMOJIS['error']} <b>Ошибка!</b>

Не удалось обновить права пользователя <b>{user_name}</b> в MySQL.

<b>Возможные причины:</b>
• Потеря соединения с MySQL
• Недостаточно прав для обновления
• Пользователь с ID {user_id} не найден

{EMOJIS['mysql']} <b>Хост:</b> {MYSQL_CONFIG['host']}
{EMOJIS['database']} <b>База:</b> {MYSQL_CONFIG['database']}

Используйте /checkdb для диагностики подключения.
        """
    
    # Удаляем сообщение о обработке
    await processing_msg.delete()
    
    # Создаем клавиатуру для дальнейших действий
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"{EMOJIS['menu']} Вернуться в меню", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJIS['database']} Проверить БД", callback_data="checkdb"),
        InlineKeyboardButton(f"{EMOJIS['cancel']} Закрыть", callback_data="close")
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        result_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await state.finish()

# Обработчик отмены
@dp.callback_query_handler(lambda c: c.data == 'cancel', state='*')
async def process_cancel(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    
    await state.finish()
    
    cancel_text = f"""
{EMOJIS['cancel']} <b>Действие отменено</b>

Возвращайтесь когда будете готовы продолжить!
    """
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"{EMOJIS['menu']} Меню", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJIS['database']} Проверить БД", callback_data="checkdb")
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        cancel_text,
        parse_mode="HTML",
        reply_markup=keyboard
    )

# Обработчик закрытия
@dp.callback_query_handler(lambda c: c.data == 'close')
async def process_close(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.delete_message(
        callback_query.from_user.id,
        callback_query.message.message_id
    )

# Функция отображения справки
async def show_help(message: types.Message):
    help_text = f"""
{EMOJIS['info']} <b>Справка по боту (MySQL Edition)</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Информация о подключении:</b>
{EMOJIS['mysql']} <b>MySQL хост:</b> {MYSQL_CONFIG['host']}
{EMOJIS['database']} <b>База данных:</b> {MYSQL_CONFIG['database']}
{EMOJIS['users']} <b>Таблица:</b> site_users

<b>🤖 Доступные команды:</b>
/start - Начало работы
/menu - Открыть меню пользователей
/checkdb - Проверить подключение к MySQL
/help - Показать эту справку

<b>📝 Как это работает:</b>
1. Бот подключается к удаленной MySQL БД
2. Получает список пользователей из таблицы site_users
3. Вы выбираете пользователя из списка
4. Подтверждаете выдачу всех прав
5. Бот обновляет поле status в MySQL

<b>🔧 Настройки подключения:</b>
<code>host: {MYSQL_CONFIG['host']}
database: {MYSQL_CONFIG['database']}
user: {MYSQL_CONFIG['user']}</code>

{EMOJIS['warning']} <b>Внимание:</b>
Выдача прав дает пользователю ПОЛНЫЙ доступ к административной панели!
    """
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"{EMOJIS['menu']} Меню", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJIS['database']} Проверить БД", callback_data="checkdb"),
        InlineKeyboardButton(f"{EMOJIS['cancel']} Закрыть", callback_data="close")
    )
    
    await message.reply(help_text, parse_mode="HTML", reply_markup=keyboard)

# Обработчик callback для помощи
@dp.callback_query_handler(lambda c: c.data == 'help')
async def process_help_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await show_help(callback_query.message)

# Обработчик всех остальных сообщений
@dp.message_handler()
async def handle_all_messages(message: types.Message):
    if message.text.startswith('/'):
        # Если команда не распознана
        await message.reply(
            f"{EMOJIS['error']} Неизвестная команда. Используйте /menu для начала работы."
        )
    else:
        # Если просто текст
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton(f"{EMOJIS['menu']} Меню", callback_data="menu"),
            InlineKeyboardButton(f"{EMOJIS['database']} Проверить БД", callback_data="checkdb")
        )
        
        await message.reply(
            f"{EMOJIS['info']} Используйте команду /menu для управления пользователями",
            reply_markup=keyboard
        )

# Запуск бота
if __name__ == '__main__':
    print(f"""
{EMOJIS['rocket']} ═══════════════════════════════════════
{EMOJIS['rocket']}  Запуск MySQL Admin Bot
{EMOJIS['rocket']} ═══════════════════════════════════════
{EMOJIS['mysql']}  MySQL Host: {MYSQL_CONFIG['host']}
{EMOJIS['database']}  Database: {MYSQL_CONFIG['database']}
{EMOJIS['users']}  Table: site_users
{EMOJIS['rocket']} ═══════════════════════════════════════
    """)
    
    # Проверяем подключение при запуске
    test_conn = get_db_connection()
    if test_conn:
        print(f"{EMOJIS['success']} Подключение к MySQL успешно установлено")
        test_conn.close()
    else:
        print(f"{EMOJIS['warning']} Предупреждение: Не удалось подключиться к MySQL")
        print(f"{EMOJIS['info']} Проверьте настройки в MYSQL_CONFIG")
    
    executor.start_polling(dp, skip_updates=True)