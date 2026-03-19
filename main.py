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
    "refresh": "🔄",
    "active": "🟢",
    "inactive": "🔴",
    "key": "🔑",
    "check": "🔍"
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
            
            # Проверяем структуру таблицы
            cursor.execute("""
                SELECT COLUMN_NAME, DATA_TYPE 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'site_users' 
                AND TABLE_SCHEMA = %s
            """, (MYSQL_CONFIG['database'],))
            columns = cursor.fetchall()
            
            columns_info = ""
            if columns:
                columns_info = "\n".join([f"  • {col[0]} ({col[1]})" for col in columns[:5]])
                if len(columns) > 5:
                    columns_info += f"\n  • ... и еще {len(columns) - 5} полей"
            
            success_text = f"""
{EMOJIS['success']} <b>Подключение к MySQL успешно!</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJIS['mysql']} <b>Версия MySQL:</b> {version[0]}
{EMOJIS['database']} <b>База данных:</b> {db_name[0]}
{EMOJIS['lock']} <b>Хост:</b> {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}
{EMOJIS['users']} <b>Таблица site_users:</b> {'Найдена' if columns else 'НЕ НАЙДЕНА'}

{EMOJIS['check']} <b>Поля таблицы:</b>
{columns_info if columns else 'Таблица не существует'}
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
        # Получаем пользователей с информацией о статусе
        cursor.execute("""
            SELECT id, username, email, status 
            FROM site_users 
            ORDER BY 
                CASE 
                    WHEN status = 'active' THEN 1 
                    ELSE 2 
                END,
                username
        """)
        users = cursor.fetchall()
        conn.close()
        return users
    except Error as e:
        logger.error(f"Ошибка получения пользователей: {e}")
        return []

# Функция для активации пользователя (изменение status на 'active' с правами)
def activate_user(user_id):
    conn = get_db_connection()
    if not conn:
        return False, "Ошибка подключения к БД"
    
    try:
        cursor = conn.cursor()
        
        # Создаем JSON с правами для активного пользователя
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
        
        # Устанавливаем статус 'active' и сохраняем права в JSON
        permissions_json = json.dumps(permissions, ensure_ascii=False)
        
        # Обновляем статус пользователя на 'active' с правами
        cursor.execute("""
            UPDATE site_users 
            SET status = %s 
            WHERE id = %s
        """, (permissions_json, user_id))
        
        conn.commit()
        affected_rows = cursor.rowcount
        
        # Получаем обновленную информацию о пользователе
        cursor.execute("SELECT username, email FROM site_users WHERE id = %s", (user_id,))
        user_info = cursor.fetchone()
        
        conn.close()
        
        if affected_rows > 0:
            return True, user_info
        else:
            return False, "Пользователь не найден"
    except Error as e:
        logger.error(f"Ошибка активации пользователя: {e}")
        return False, str(e)

# Функция для проверки текущего статуса пользователя
def check_user_status(user_id):
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT username, email, status FROM site_users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Error as e:
        logger.error(f"Ошибка проверки статуса: {e}")
        return None

# Команда /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    welcome_text = f"""
{EMOJIS['rocket']} <b>Добро пожаловать в Admin Panel Bot (MySQL Edition)!</b>

Этот бот позволяет активировать пользователей и выдавать им все права в системе через удаленную MySQL базу данных.

{EMOJIS['mysql']} <b>Подключение к MySQL:</b> {MYSQL_CONFIG['host']}
{EMOJIS['active']} <b>Режим работы:</b> Активация аккаунтов (status = 'active' с правами)

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
    
    # Подсчитываем статистику
    active_count = sum(1 for user in users if user['status'] == 'active' or 
                      (user['status'] and user['status'].startswith('{')))
    inactive_count = len(users) - active_count
    
    # Создаем красивый заголовок
    header = f"""
{EMOJIS['users']} <b>Список пользователей</b> ({len(users)})
{EMOJIS['active']} Активных: {active_count} | {EMOJIS['inactive']} Неактивных: {inactive_count}
━━━━━━━━━━━━━━━━━━━━━━
{EMOJIS['mysql']} <b>MySQL:</b> {MYSQL_CONFIG['host']}
<i>Выберите пользователя для активации:</i>
    """
    
    # Создаем клавиатуру с пользователями
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        username = user['username'] if user['username'] else "Без имени"
        email = user['email'] if user['email'] else "Нет email"
        
        # Определяем статус пользователя
        is_active = False
        if user['status']:
            if user['status'] == 'active':
                is_active = True
            elif user['status'].startswith('{'):
                try:
                    status_data = json.loads(user['status'])
                    if isinstance(status_data, dict) and any(status_data.values()):
                        is_active = True
                except:
                    pass
        
        status_emoji = EMOJIS['active'] if is_active else EMOJIS['inactive']
        status_text = "Активен" if is_active else "Неактивен"
        
        # Обрезаем длинные имена
        display_name = username[:20] + "..." if len(username) > 20 else username
        display_email = email[:25] + "..." if len(email) > 25 else email
        
        button_text = f"{status_emoji} {display_name} | {display_email} [{status_text}]"
        
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
    user = check_user_status(user_id)
    
    if not user:
        await bot.send_message(
            callback_query.from_user.id,
            f"{EMOJIS['error']} Пользователь не найден или ошибка подключения к БД"
        )
        return
    
    # Сохраняем ID пользователя в состояние
    await state.update_data(selected_user_id=user_id, selected_user_name=user['username'])
    
    # Проверяем текущий статус
    is_active = False
    status_display = "Неактивен"
    
    if user['status']:
        if user['status'] == 'active':
            is_active = True
            status_display = "Активен (active)"
        elif user['status'].startswith('{'):
            try:
                status_data = json.loads(user['status'])
                if isinstance(status_data, dict):
                    active_permissions = sum(1 for v in status_data.values() if v)
                    status_display = f"Активен с правами ({active_permissions} прав)"
                    is_active = True
                else:
                    status_display = "Неактивен (неверный формат)"
            except:
                status_display = "Неактивен (ошибка парсинга)"
    
    # Если пользователь уже активен
    if is_active:
        already_active_text = f"""
{EMOJIS['warning']} <b>Пользователь уже активирован!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
{EMOJIS['active']} <b>Текущий статус:</b> {status_display}

Данный пользователь уже имеет активный статус в системе.
Повторная активация не требуется.
        """
        
        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            InlineKeyboardButton(f"{EMOJIS['menu']} Вернуться в меню", callback_data="menu"),
            InlineKeyboardButton(f"{EMOJIS['cancel']} Закрыть", callback_data="close")
        )
        
        await bot.send_message(
            callback_query.from_user.id,
            already_active_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        await state.finish()
        return
    
    # Показываем информацию о пользователе для активации
    user_info = f"""
{EMOJIS['info']} <b>Информация о пользователе:</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
{EMOJIS['inactive']} <b>Текущий статус:</b> {status_display}

{EMOJIS['key']} <b>Вы уверены, что хотите АКТИВИРОВАТЬ этого пользователя?</b>

<b>При активации будут выданы права:</b>
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
{EMOJIS['active']} <b>Новый статус:</b> active (с JSON правами)
    """
    
    # Создаем клавиатуру подтверждения
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"{EMOJIS['confirm']} Активировать", callback_data="confirm_yes"),
        InlineKeyboardButton(f"{EMOJIS['cancel']} Отмена", callback_data="cancel")
    )
    
    await bot.send_message(
        callback_query.from_user.id,
        user_info,
        parse_mode="HTML",
        reply_markup=keyboard
    )
    
    await UserStates.confirming.set()

# Обработчик подтверждения активации
@dp.callback_query_handler(lambda c: c.data == 'confirm_yes', state=UserStates.confirming)
async def process_confirmation(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    
    # Показываем статус обработки
    processing_msg = await bot.send_message(
        callback_query.from_user.id,
        f"{EMOJIS['refresh']} Активация пользователя в MySQL..."
    )
    
    # Получаем данные из состояния
    data = await state.get_data()
    user_id = data.get('selected_user_id')
    user_name = data.get('selected_user_name')
    
    # Активируем пользователя
    success, result = activate_user(user_id)
    
    if success:
        # result содержит информацию о пользователе
        user_info = result
        
        result_text = f"""
{EMOJIS['success']} <b>Пользователь успешно активирован!</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJIS['active']} <b>Пользователь:</b> {user_name}
{EMOJIS['mysql']} <b>Статус изменен на:</b> active (с полными правами)

<b>Выданные права:</b>
✓ Просмотр всех логов
✓ Управление конфигурацией
✓ Управление пользователями
✓ И другие привилегии

{EMOJIS['database']} <b>Изменения сохранены в MySQL</b>
{EMOJIS['rocket']} Пользователь может войти в систему с полными правами.
        """
    else:
        result_text = f"""
{EMOJIS['error']} <b>Ошибка активации!</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJIS['users']} <b>Пользователь:</b> {user_name}

<b>Причина ошибки:</b>
<code>{result}</code>

{EMOJIS['mysql']} <b>Хост:</b> {MYSQL_CONFIG['host']}
{EMOJIS['database']} <b>База:</b> {MYSQL_CONFIG['database']}

<b>Рекомендации:</b>
• Проверьте подключение к MySQL
• Убедитесь, что пользователь существует
• Проверьте права на запись в таблицу
• Используйте /checkdb для диагностики
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
{EMOJIS['info']} <b>Справка по боту (MySQL Edition - Активация)</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>📊 Информация о подключении:</b>
{EMOJIS['mysql']} <b>MySQL хост:</b> {MYSQL_CONFIG['host']}
{EMOJIS['database']} <b>База данных:</b> {MYSQL_CONFIG['database']}
{EMOJIS['users']} <b>Таблица:</b> site_users

<b>🎯 Функционал бота:</b>
• Активация пользователей (status = 'active' с JSON правами)
• Просмотр списка всех пользователей
• Проверка текущего статуса
• Диагностика подключения к MySQL

<b>🤖 Доступные команды:</b>
/start - Начало работы
/menu - Открыть меню пользователей
/checkdb - Проверить подключение к MySQL
/help - Показать эту справку

<b>📝 Процесс активации:</b>
1. Бот подключается к удаленной MySQL БД
2. Получает список пользователей из таблицы site_users
3. Вы выбираете пользователя из списка
4. Бот показывает текущий статус
5. При подтверждении - статус меняется на 'active' с JSON правами

<b>🔧 Настройки подключения:</b>
<code>host: {MYSQL_CONFIG['host']}
database: {MYSQL_CONFIG['database']}
user: {MYSQL_CONFIG['user']}</code>

{EMOJIS['warning']} <b>Важно:</b>
• Активация дает пользователю ПОЛНЫЙ доступ к административной панели
• Проверяйте правильность выбора пользователя перед активацией
• Бот не может деактивировать пользователей
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
{EMOJIS['rocket']}  Запуск MySQL Admin Bot - Активация
{EMOJIS['rocket']} ═══════════════════════════════════════
{EMOJIS['mysql']}  MySQL Host: {MYSQL_CONFIG['host']}
{EMOJIS['database']}  Database: {MYSQL_CONFIG['database']}
{EMOJIS['users']}  Table: site_users
{EMOJIS['active']}  Mode: Активация аккаунтов (status = 'active' + права)
{EMOJIS['rocket']} ═══════════════════════════════════════
    """)
    
    # Проверяем подключение при запуске
    test_conn = get_db_connection()
    if test_conn:
        print(f"{EMOJIS['success']} Подключение к MySQL успешно установлено")
        
        # Проверяем структуру таблицы
        try:
            cursor = test_conn.cursor()
            cursor.execute("SHOW COLUMNS FROM site_users")
            columns = cursor.fetchall()
            print(f"{EMOJIS['users']} Таблица site_users найдена, полей: {len(columns)}")
            
            # Проверяем наличие поля status
            status_field = any(col[0] == 'status' for col in columns)
            if status_field:
                print(f"{EMOJIS['success']} Поле 'status' найдено")
            else:
                print(f"{EMOJIS['warning']} Поле 'status' не найдено в таблице!")
        except Error as e:
            print(f"{EMOJIS['warning']} Не удалось проверить структуру таблицы: {e}")
        
        test_conn.close()
    else:
        print(f"{EMOJIS['warning']} Предупреждение: Не удалось подключиться к MySQL")
        print(f"{EMOJIS['info']} Проверьте настройки в MYSQL_CONFIG")
    
    executor.start_polling(dp, skip_updates=True)
