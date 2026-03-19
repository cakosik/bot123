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

# Права которые будут выдаваться
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

# Получить всех пользователей
def get_users():
    conn = get_db()
    if not conn:
        return []
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, username, email, status, permissions 
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
        cursor.execute("SELECT id, username, email, status, permissions FROM site_users WHERE id = %s", (user_id,))
        user = cursor.fetchone()
        conn.close()
        return user
    except Error as e:
        logger.error(f"Ошибка получения пользователя: {e}")
        return None

# Обновить статус и permissions пользователя
def update_user_full(user_id, new_status):
    conn = get_db()
    if not conn:
        return False, "Нет подключения к БД"
    
    try:
        cursor = conn.cursor()
        
        if new_status == 'active':
            # Для active - ставим статус active и JSON с правами
            permissions_json = json.dumps(PERMISSIONS_JSON, ensure_ascii=False)
            cursor.execute(
                "UPDATE site_users SET status = %s, permissions = %s WHERE id = %s",
                ('active', permissions_json, user_id)
            )
        else:
            # Для inactive - ставим статус inactive и пустые права (или NULL)
            cursor.execute(
                "UPDATE site_users SET status = %s, permissions = NULL WHERE id = %s",
                ('inactive', user_id)
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

# Проверка есть ли права у пользователя
def has_permissions(perms_value):
    if not perms_value:
        return False
    try:
        if isinstance(perms_value, str):
            perms = json.loads(perms_value)
            return isinstance(perms, dict) and any(perms.values())
    except:
        pass
    return False

# Старт
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    text = f"""
{EMOJI['rocket']} <b>Admin Bot</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} MySQL: {MYSQL_CONFIG['host']}
{EMOJI['users']} Таблица: site_users

<b>Поля:</b>
• status - active/inactive
• permissions - JSON с правами

{EMOJI['perms']} <b>Права:</b>
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
        if user['status'] == 'active' and has_permissions(user['permissions']):
            active += 1
        else:
            inactive += 1
    
    header = f"""
{EMOJI['users']} <b>Пользователи</b> ({len(users)})
{EMOJI['active']} Active (с правами): {active} | {EMOJI['inactive']} Inactive: {inactive}
━━━━━━━━━━━━━━━━━━━━━━
<b>Выбери пользователя:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=1)
    
    for user in users:
        # Определяем иконку статуса
        if user['status'] == 'active' and has_permissions(user['permissions']):
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
        current_status=user['status'],
        current_permissions=user['permissions']
    )
    
    # Текущий статус
    if user['status'] == 'active' and has_permissions(user['permissions']):
        status_text = f"{EMOJI['active']} Active (с правами)"
    else:
        status_text = f"{EMOJI['inactive']} Inactive"
    
    info = f"""
{EMOJI['info']} <b>Информация о пользователе</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Имя:</b> {user['username']}
📧 <b>Email:</b> {user['email']}
{EMOJI['arrow']} <b>Текущий статус:</b> {status_text}

{EMOJI['perms']} <b>Права которые будут выданы при активации:</b>
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

<b>Куда:</b> в поле permissions таблицы site_users

{EMOJI['arrow']} <b>Выбери действие:</b>
    """
    
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton(f"{EMOJI['active']} Сделать Active", callback_data="set_active"),
        InlineKeyboardButton(f"{EMOJI['inactive']} Сделать Inactive", callback_data="set_inactive"),
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
        action_text = f"\n\n{EMOJI['perms']} <b>Будут выданы все права</b> (в поле permissions)"
    else:
        new_status = 'inactive'
        status_emoji = EMOJI['inactive']
        status_name = 'Inactive'
        action_text = f"\n\n{EMOJI['warning']} <b>Права будут удалены</b> (permissions = NULL)"
    
    # Сохраняем выбор
    await state.update_data(new_status=new_status)
    
    data = await state.get_data()
    
    # Текущий статус для отображения
    if data['current_status'] == 'active' and has_permissions(data['current_permissions']):
        current_text = f"{EMOJI['active']} Active"
    else:
        current_text = f"{EMOJI['inactive']} Inactive"
    
    confirm = f"""
{EMOJI['warning']} <b>Подтверждение</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
📧 <b>Email:</b> {data['email']}
{EMOJI['arrow']} <b>Было:</b> {current_text}
{status_emoji} <b>Станет:</b> {status_name}{action_text}

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
        f"{EMOJI['refresh']} Обновляю данные в site_users..."
    )
    
    # Обновляем и статус и permissions в одной таблице
    success, msg = update_user_full(data['user_id'], data['new_status'])
    
    await processing.delete()
    
    if success:
        if data['new_status'] == 'active':
            final = f"""
{EMOJI['success']} <b>Готово!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
{EMOJI['active']} <b>Статус:</b> Active
{EMOJI['perms']} <b>Права:</b> Выданы все 11 прав

✅ status = 'active'
✅ permissions = JSON со всеми правами
            """
        else:
            final = f"""
{EMOJI['success']} <b>Готово!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
{EMOJI['inactive']} <b>Статус:</b> Inactive
{EMOJI['perms']} <b>Права:</b> Удалены

✅ status = 'inactive'
✅ permissions = NULL
            """
    else:
        final = f"""
{EMOJI['error']} <b>Ошибка!</b>
━━━━━━━━━━━━━━━━━━━━━━
👤 <b>Пользователь:</b> {data['username']}
<b>Ошибка:</b> {msg}

Попробуй еще раз
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
        
        # Проверяем структуру таблицы
        cursor.execute("DESCRIBE site_users")
        columns = cursor.fetchall()
        
        has_status = False
        has_permissions = False
        
        for col in columns:
            if col[0] == 'status':
                has_status = True
            if col[0] == 'permissions':
                has_permissions = True
        
        # Считаем пользователей
        cursor.execute("SELECT COUNT(*) FROM site_users")
        total = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM site_users WHERE status = 'active'")
        active_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM site_users WHERE permissions IS NOT NULL AND permissions != ''")
        perms_count = cursor.fetchone()[0]
        
        text = f"""
{EMOJI['success']} <b>MySQL подключен</b>
━━━━━━━━━━━━━━━━━━━━━━
{EMOJI['mysql']} <b>Хост:</b> {MYSQL_CONFIG['host']}
{EMOJI['db']} <b>Версия:</b> {version[0]}

{EMOJI['users']} <b>Таблица site_users:</b>
• Всего: {total}
• Active: {active_count}
• С правами: {perms_count}

<b>Поля таблицы:</b>
• status: {'✅' if has_status else '❌'}
• permissions: {'✅' if has_permissions else '❌'}
        """
        
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
{EMOJI['users']}  Таблица: site_users

{EMOJI['active']}  Active:
   • status = 'active'
   • permissions = JSON со всеми правами

{EMOJI['inactive']}  Inactive:
   • status = 'inactive'
   • permissions = NULL

{EMOJI['perms']}  Права которые выдаются:
   • view_logs
   • view_admin_logs
   • view_forbes
   • и еще 8 прав
{EMOJI['rocket']} ══════════════════════════════════════
    """)
    
    executor.start_polling(dp, skip_updates=True)
