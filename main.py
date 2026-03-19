import logging
import mysql.connector
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
    "arrow": "➡️",
    "perms": "🔑",
    "settings": "⚙️"
}

# Права для активного пользователя
ACTIVE_PERMISSIONS = {
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
            ORDER BY username
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

# Обновить статус пользователя (с правами для active)
def update_user_status(user_id, new_status):
    conn = get_db()
    if not conn:
        return False, "Нет подключения к БД"
    
    try:
        cursor = conn.cursor()
        
        if new_status == 'active':
            # Для active - сохраняем JSON со всеми правами
            status_value = json.dumps(ACTIVE_PERMISSIONS, ensure_ascii=False)
        else:
            # Для inactive - пустая строка
            status_value = ''
        
        cursor.execute(
            "UPDATE site_users SET status = %s WHERE id = %s",
            (status_value, user_id)
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

# Проверка статуса пользователя
def check_user_status(status_value):
    if not status_value:
        return False, EMOJI['inactive'], "Inactive"
    
    try:
        # Пробуем распарсить JSON
        if status_value.startswith('{'):
            perms = json.loads(status_value)
            # Проверяем что это наши права
            if isinstance(perms, dict) and any(perms.values()):
                return True, EMOJI['active'], "Active"
    except:
        pass
    
    # Проверяем на обычный active
    if status_value == 'active':
        return True, EMOJI['active'], "Active"
    
    return False, EMOJI['inactive'], "Inactive"

# Старт
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    text = f"""
{EMOJI['rocket']} <b>Admin Bot с правами</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} MySQL: {MYSQL_CONFIG['host']}
{EMOJI['users']} Таблица: site_users

{EMOJI['perms']} <b>Права для Active:</b>
• view_logs
• view_admin_logs
• view_forbes
• view_bonus_codes
• view_server_config
• edit_server_config
• view_numbers
• view_bans
• view_money_logs
• view_manage_users
• manage_users

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
    active = 0
    inactive = 0
    
    for user in users:
        is_active, _, _ = check_user_status(user['status'])
        if is_active:
            active += 1
        else:
            inactive += 1
    
    header = f"""
{EMOJI['users']} <b>Пользователи</b> ({len(users)})
{EMOJI['active']} Active: {active} | {EMOJI['inactive']} Inactive: {inactive}
━━━━━━━━━━━━━━━━━━━━━━
<b>Выбери пользователя:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        # Определяем статус для иконки
        is_active, status_emoji, _ = check_user_status(user['status'])
        
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
    is_active, status_emoji, status_text = check_user_status(user['status'])
    
    info = f"""
{EMOJI['info']} <b>Информация о пользователе</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
{status_emoji} <b>Текущий статус:</b> {status_text}

{EMOJI['perms']} <b>Права для Active:</b>
• Все 11 прав доступа
• Полный доступ к админке

{EMOJI['arrow']} <b>Выбери новый статус:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['active']} Active (с правами)", callback_data="set_active"),
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
        status_name = 'Active (с правами)'
    else:
        new_status = 'inactive'
        status_emoji = EMOJI['inactive']
        status_name = 'Inactive'
    
    # Сохраняем выбор
    await state.update_data(new_status=new_status)
    
    data = await state.get_data()
    
    # Текущий статус для отображения
    _, current_emoji, current_text = check_user_status(data['current_status'])
    
    confirm = f"""
{EMOJI['warning']} <b>Подтверждение изменения</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
📧 <b>Email:</b> {data['email']}
{current_emoji} <b>Было:</b> {current_text}
{status_emoji} <b>Станет:</b> {status_name}

<b>Точно изменить?</b>
    """
    
    # Добавляем инфу о правах если выбирают Active
    if new_status == 'active':
        confirm += f"\n\n{EMOJI['perms']} <b>Будут выданы права:</b>\n"
        for perm in ACTIVE_PERMISSIONS.keys():
            confirm += f"• {perm}\n"
    
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
        f"{EMOJI['refresh']} Обновляю статус в MySQL..."
    )
    
    # Меняем статус (для active автоматически подставляются права)
    success, msg = update_user_status(data['user_id'], data['new_status'])
    
    await processing.delete()
    
    if success:
        if data['new_status'] == 'active':
            result_emoji = EMOJI['active']
            result_text = "Active"
            rights_text = f"\n\n{EMOJI['perms']} <b>Выданы все права:</b>\n11 прав доступа"
        else:
            result_emoji = EMOJI['inactive']
            result_text = "Inactive"
            rights_text = ""
        
        final = f"""
{EMOJI['success']} <b>Статус обновлен!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
📧 <b>Email:</b> {data['email']}
{result_emoji} <b>Новый статус:</b> {result_text}{rights_text}

{EMOJI['db']} Изменения сохранены в MySQL
        """
    else:
        final = f"""
{EMOJI['error']} <b>Ошибка!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
<b>Ошибка:</b> {msg}

Попробуй еще раз или проверь подключение к БД
        """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['menu']} В меню", callback_data="menu"),
        InlineKeyboardButton(f"{EMOJI['db']} Проверить БД", callback_data="checkdb"),
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
        f"{EMOJI['cancel']} Изменение отменено"
    )

# Отмена везде
@dp.callback_query_handler(lambda c: c.data == 'cancel', state='*')
async def cancel_all(callback: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback.id)
    await state.finish()
    
    await bot.send_message(
        callback.from_user.id,
        f"{EMOJI['cancel']} Действие отменено"
    )

# Проверка БД
@dp.callback_query_handler(lambda c: c.data == 'checkdb')
async def check_db_callback(callback: types.CallbackQuery):
    await bot.answer_callback_query(callback.id)
    await check_db(callback.message)

@dp.message_handler(commands=['checkdb'])
async def check_db(message: types.Message):
    status_msg = await message.reply(f"{EMOJI['refresh']} Проверка подключения...")
    
    conn = get_db()
    if not conn:
        await status_msg.edit_text(
            f"{EMOJI['error']} Нет подключения к MySQL\nХост: {MYSQL_CONFIG['host']}"
        )
        return
    
    try:
        cursor = conn.cursor()
        
        # Версия MySQL
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        
        # Проверяем таблицу
        cursor.execute("SHOW TABLES LIKE 'site_users'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM site_users")
            total = cursor.fetchone()[0]
            
            # Считаем активных (у кого есть JSON с правами)
            cursor.execute("SELECT COUNT(*) FROM site_users WHERE status LIKE '{%}'")
            active_with_perms = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM site_users WHERE status = 'active'")
            active_old = cursor.fetchone()[0]
            
            active = active_with_perms + active_old
            
            text = f"""
{EMOJI['success']} <b>MySQL подключен</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} <b>Хост:</b> {MYSQL_CONFIG['host']}
{EMOJI['db']} <b>Версия:</b> {version[0]}
{EMOJI['users']} <b>Всего пользователей:</b> {total}
{EMOJI['active']} <b>Active (с правами):</b> {active}
{EMOJI['inactive']} <b>Inactive:</b> {total - active}
            """
        else:
            text = f"{EMOJI['error']} Таблица 'site_users' не найдена"
        
        conn.close()
        
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton(f"{EMOJI['menu']} Меню", callback_data="menu")
        )
        
        await status_msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
        
    except Error as e:
        await status_msg.edit_text(f"{EMOJI['error']} Ошибка: {e}")

# Закрыть
@dp.callback_query_handler(lambda c: c.data == 'close')
async def close_msg(callback: types.CallbackQuery):
    await bot.answer_callback_query(callback.id)
    await bot.delete_message(callback.from_user.id, callback.message.message_id)

# Помощь
@dp.message_handler(commands=['help'])
async def help_cmd(message: types.Message):
    text = f"""
{EMOJI['info']} <b>Команды бота</b>
━━━━━━━━━━━━━━━━━━━━━━
/menu - список пользователей
/checkdb - проверка MySQL
/help - это меню

{EMOJI['perms']} <b>Права для Active:</b>
{chr(10).join([f'• {perm}' for perm in ACTIVE_PERMISSIONS.keys()])}

{EMOJI['active']} <b>Active</b> - JSON со всеми правами
{EMOJI['inactive']} <b>Inactive</b> - пусто
    """
    
    await message.reply(text, parse_mode="HTML")

# Запуск
if __name__ == '__main__':
    print(f"""
{EMOJI['rocket']} ══════════════════════════════════════
{EMOJI['rocket']}  Бот с правами запущен
{EMOJI['rocket']} ══════════════════════════════════════
{EMOJI['mysql']}  Хост: {MYSQL_CONFIG['host']}
{EMOJI['users']}  Таблица: site_users
{EMOJI['perms']}  Права: 11 прав для Active
{EMOJI['active']}  Active → JSON с правами
{EMOJI['inactive']}  Inactive → пусто
{EMOJI['rocket']} ══════════════════════════════════════
    """)
    
    executor.start_polling(dp, skip_updates=True)
