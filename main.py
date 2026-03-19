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

# Права которые будут выдаваться (для отдельной таблицы)
PERMISSIONS_JSON = {
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

# Получить всех пользователей (только из site_users)
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

# Обновить статус в site_users (только active/inactive)
def update_user_status(user_id, new_status):
    conn = get_db()
    if not conn:
        return False, "Нет подключения к БД"
    
    try:
        cursor = conn.cursor()
        # Меняем только status, никаких JSON тут нет
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

# Обновить permissions в site_user
def update_user_permissions(user_id):
    conn = get_db()
    if not conn:
        return False, "Нет подключения к БД"
    
    try:
        cursor = conn.cursor()
        
        # Проверяем есть ли уже запись в site_user
        cursor.execute("SELECT id FROM site_user WHERE user_id = %s", (user_id,))
        exists = cursor.fetchone()
        
        permissions_json = json.dumps(PERMISSIONS_JSON, ensure_ascii=False)
        
        if exists:
            # Обновляем существующую запись
            cursor.execute(
                "UPDATE site_user SET permissions = %s WHERE user_id = %s",
                (permissions_json, user_id)
            )
        else:
            # Создаем новую запись
            cursor.execute(
                "INSERT INTO site_user (user_id, permissions) VALUES (%s, %s)",
                (user_id, permissions_json)
            )
        
        conn.commit()
        conn.close()
        
        return True, "Права обновлены"
    except Error as e:
        logger.error(f"Ошибка обновления прав: {e}")
        return False, str(e)

# Старт
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    text = f"""
{EMOJI['rocket']} <b>Admin Bot</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} MySQL: {MYSQL_CONFIG['host']}

{EMOJI['users']} <b>Таблица site_users:</b>
• status: active / inactive

{EMOJI['perms']} <b>Таблица site_user:</b>
• permissions: JSON со всеми правами

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
━━━━━━━━━━━━━━━━━━━━━━
<b>Выбери пользователя:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        # Статус для иконки
        if user['status'] == 'active':
            status_emoji = EMOJI['active']
        else:
            status_emoji = EMOJI['inactive']
        
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
    else:
        status_text = f"{EMOJI['inactive']} Inactive"
    
    info = f"""
{EMOJI['info']} <b>Информация о пользователе</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
{EMOJI['arrow']} <b>Текущий статус:</b> {status_text}

{EMOJI['perms']} <b>При активации (Active) будут выданы права:</b>
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

<b>Куда:</b> в таблицу site_user (permissions)

{EMOJI['arrow']} <b>Выбери новый статус:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['active']} Active (выдать права)", callback_data="set_active"),
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
        rights_text = f"\n\n{EMOJI['perms']} <b>Будут выданы права</b> (в site_user)"
    else:
        new_status = 'inactive'
        status_emoji = EMOJI['inactive']
        status_name = 'Inactive'
        rights_text = ""
    
    # Сохраняем выбор
    await state.update_data(new_status=new_status)
    
    data = await state.get_data()
    
    # Текущий статус
    if data['current_status'] == 'active':
        current_text = f"{EMOJI['active']} Active"
    else:
        current_text = f"{EMOJI['inactive']} Inactive"
    
    confirm = f"""
{EMOJI['warning']} <b>Подтверждение</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
📧 <b>Email:</b> {data['email']}
{EMOJI['arrow']} <b>Было:</b> {current_text}
{status_emoji} <b>Станет:</b> {status_name}{rights_text}

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
        f"{EMOJI['refresh']} Обновляю данные..."
    )
    
    # 1. Сначала меняем статус в site_users
    status_success, status_msg = update_user_status(data['user_id'], data['new_status'])
    
    if not status_success:
        await processing.delete()
        await bot.send_message(
            callback.from_user.id,
            f"{EMOJI['error']} Ошибка обновления статуса: {status_msg}"
        )
        await state.finish()
        return
    
    # 2. Если выбрали Active - выдаем права в site_user
    perms_success = True
    perms_msg = ""
    
    if data['new_status'] == 'active':
        perms_success, perms_msg = update_user_permissions(data['user_id'])
    
    await processing.delete()
    
    # Формируем результат
    if data['new_status'] == 'active':
        if perms_success:
            final = f"""
{EMOJI['success']} <b>Готово!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
{EMOJI['active']} <b>Статус:</b> Active (изменен в site_users)
{EMOJI['perms']} <b>Права:</b> Выданы все 11 прав (в site_user)

✅ Статус обновлен
✅ Права выданы
            """
        else:
            final = f"""
{EMOJI['warning']} <b>Частично выполнено</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
{EMOJI['active']} <b>Статус:</b> Active (изменен)

{EMOJI['error']} <b>Ошибка выдачи прав:</b> {perms_msg}

Статус изменен, но права не выданы
            """
    else:
        final = f"""
{EMOJI['success']} <b>Готово!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
{EMOJI['inactive']} <b>Статус:</b> Inactive

Статус обновлен в site_users
        """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
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
        
        text = f"""
{EMOJI['success']} <b>MySQL подключен</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} <b>Хост:</b> {MYSQL_CONFIG['host']}
{EMOJI['db']} <b>Версия:</b> {version[0]}

<b>Таблицы:</b>
        """
        
        # Проверяем site_users
        cursor.execute("SHOW TABLES LIKE 'site_users'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM site_users")
            total_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM site_users WHERE status = 'active'")
            active_users = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM site_users WHERE status = 'inactive'")
            inactive_users = cursor.fetchone()[0]
            
            text += f"""
{EMOJI['users']} <b>site_users:</b>
   • Всего: {total_users}
   • Active: {active_users}
   • Inactive: {inactive_users}
            """
        else:
            text += f"\n{EMOJI['error']} site_users: НЕТ"
        
        # Проверяем site_user
        cursor.execute("SHOW TABLES LIKE 'site_user'")
        if cursor.fetchone():
            cursor.execute("SELECT COUNT(*) FROM site_user")
            total_perms = cursor.fetchone()[0]
            
            text += f"""
{EMOJI['perms']} <b>site_user:</b>
   • Всего записей: {total_perms}
            """
        else:
            text += f"\n{EMOJI['error']} site_user: НЕТ"
        
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

# Запуск
if __name__ == '__main__':
    print(f"""
{EMOJI['rocket']} ══════════════════════════════════════
{EMOJI['rocket']}  Бот запущен
{EMOJI['rocket']} ══════════════════════════════════════
{EMOJI['mysql']}  Хост: {MYSQL_CONFIG['host']}

{EMOJI['users']}  site_users:
   • status: active / inactive

{EMOJI['perms']}  site_user:
   • permissions: JSON с правами

{EMOJI['active']}  Active → status = active + права в site_user
{EMOJI['inactive']}  Inactive → status = inactive
{EMOJI['rocket']} ══════════════════════════════════════
    """)
    
    executor.start_polling(dp, skip_updates=True)
