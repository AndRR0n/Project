import asyncio
import sqlite3
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from database import init_db, get_all_points, get_points_by_user, upsert_point

# ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")
init_db()
# ────────────────────────────────────────────────

class PointForm(StatesGroup):
    choosing_action = State()
    # Добавление новой точки
    name    = State()
    address = State()
    phone   = State()
    status  = State()
    comment = State()
    # Редактирование существующей точки
    edit_choosing_field = State()
    edit_name       = State()
    edit_address    = State()
    edit_phone      = State()
    edit_status     = State()
    edit_comment    = State()
    edit_owner      = State()   # редактирование поля "Ответственный"


# ── Клавиатуры ──────────────────────────────────

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Новая точка",             callback_data="new")],
        [InlineKeyboardButton(text="✏️ Изменить существующую",   callback_data="edit")],
    ])

def status_keyboard(prefix: str = "status"):
    """prefix позволяет использовать одну функцию и для новой, и для редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ работает",       callback_data=f"{prefix}_работает")],
        [InlineKeyboardButton(text="🔧 в проработке",  callback_data=f"{prefix}_в проработке")],
        [InlineKeyboardButton(text="🔒 закрыта",       callback_data=f"{prefix}_закрыта")],
        [InlineKeyboardButton(text="❌ не работает",   callback_data=f"{prefix}_не работает")],
    ])

def skip_keyboard(cb_data: str = "skip_comment"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить →", callback_data=cb_data)]
    ])

def points_keyboard(user_id: int, username: str):
    """Показывает точки текущего пользователя — по owner_id или по updated_by."""
    points = get_points_by_user(user_id, username)
    if not points:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="У вас пока нет точек", callback_data="no_points")]
        ])
    kb = []
    for p in sorted(points, key=lambda x: x["id"]):
        name_short = (p.get("name") or "Без названия")[:28]
        btn_text = f"#{p['id']} {name_short}"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"edit_{p['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def edit_field_keyboard(point_id: int):
    """Меню выбора поля для редактирования."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Название",        callback_data=f"field_name_{point_id}")],
        [InlineKeyboardButton(text="📍 Адрес",           callback_data=f"field_address_{point_id}")],
        [InlineKeyboardButton(text="📞 Телефон",         callback_data=f"field_phone_{point_id}")],
        [InlineKeyboardButton(text="🔄 Статус",          callback_data=f"field_status_{point_id}")],
        [InlineKeyboardButton(text="💬 Комментарий",     callback_data=f"field_comment_{point_id}")],
        [InlineKeyboardButton(text="👤 Ответственный",   callback_data=f"field_owner_{point_id}")],
        [InlineKeyboardButton(text="✅ Сохранить всё",   callback_data=f"field_done_{point_id}")],
    ])


# ── Хелпер: найти точку по id ────────────────────

def find_point(point_id: int):
    points = get_all_points()
    return next((p for p in points if p["id"] == point_id), None)


# ── Хендлеры ────────────────────────────────────

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "Привет! Добавить новую точку или изменить старую?",
        reply_markup=main_keyboard()
    )
    await state.set_state(PointForm.choosing_action)


# ── НОВАЯ точка ──────────────────────────────────

@dp.callback_query(F.data == "new")
async def cb_new(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название точки:")
    await state.set_state(PointForm.name)
    await callback.answer()

@dp.message(PointForm.name)
async def process_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Адрес:")
    await state.set_state(PointForm.address)

@dp.message(PointForm.address)
async def process_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await message.answer("Телефон (или «-» чтобы пропустить):")
    await state.set_state(PointForm.phone)

@dp.message(PointForm.phone)
async def process_phone(message: Message, state: FSMContext):
    text = message.text.strip()
    if text != "-":
        await state.update_data(phone=text)
    await message.answer("Статус:", reply_markup=status_keyboard("status"))
    await state.set_state(PointForm.status)

@dp.callback_query(PointForm.status, F.data.startswith("status_"))
async def process_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split("_", 1)[1]
    await state.update_data(status=status)
    await callback.message.edit_text(
        "Комментарий (или нажмите «Пропустить»):",
        reply_markup=skip_keyboard("skip_comment")
    )
    await state.set_state(PointForm.comment)
    await callback.answer()

@dp.message(PointForm.comment)
async def process_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text.strip())
    await save_new_and_finish(state, message.from_user, message)

@dp.callback_query(PointForm.comment, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    await save_new_and_finish(state, callback.from_user, callback.message)
    await callback.answer("Сохранено!")

async def save_new_and_finish(state: FSMContext, user: types.User, msg):
    data     = await state.get_data()
    username = f"@{user.username}" if user.username else f"ID{user.id}"
    point = {
        "name":       data.get("name"),
        "address":    data.get("address"),
        "phone":      data.get("phone"),
        "status":     data.get("status"),
        "comment":    data.get("comment"),
        "updated_by": username,
        "owner_id":   user.id,          # сохраняем владельца
    }
    upsert_point(point)
    text = f"✅ Точка сохранена!\nСтатус: {data.get('status', '—')}"
    if isinstance(msg, Message):
        await msg.answer(text, reply_markup=main_keyboard())
    else:
        await msg.edit_text(text)
        await msg.answer("Ещё что-нибудь?", reply_markup=main_keyboard())
    await state.clear()


# ── РЕДАКТИРОВАНИЕ точки ─────────────────────────

@dp.callback_query(F.data == "edit")
async def cb_edit_choose(callback: CallbackQuery, state: FSMContext):
    user = callback.from_user
    username = f"@{user.username}" if user.username else f"ID{user.id}"
    kb = points_keyboard(user.id, username)
    await callback.message.edit_text("Выберите точку для редактирования:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(F.data == "no_points")
async def cb_no_points(callback: CallbackQuery):
    await callback.answer("У вас пока нет добавленных точек.", show_alert=True)

@dp.callback_query(F.data.startswith("edit_"))
async def cb_edit_select(callback: CallbackQuery, state: FSMContext):
    try:
        point_id = int(callback.data.split("_", 1)[1])
    except (ValueError, IndexError):
        await callback.message.edit_text("Ошибка выбора точки.")
        return

    point = find_point(point_id)
    if not point:
        await callback.message.edit_text("Точка не найдена.")
        return

    # Сохраняем актуальные данные точки в state как начальные значения
    await state.update_data(
        point_id   = point_id,
        name       = point.get("name"),
        address    = point.get("address"),
        phone      = point.get("phone"),
        status     = point.get("status"),
        comment    = point.get("comment"),
        updated_by = point.get("updated_by"),
    )

    info = (
        f"📌 Редактируем точку #{point_id}\n\n"
        f"Название:    {point.get('name', '—')}\n"
        f"Адрес:       {point.get('address', '—')}\n"
        f"Телефон:     {point.get('phone', '—')}\n"
        f"Статус:      {point.get('status', '—')}\n"
        f"Комментарий: {point.get('comment', '—')}\n"
        f"Ответственный: {point.get('updated_by', '—')}\n\n"
        "Что хотите изменить?"
    )
    await callback.message.edit_text(info, reply_markup=edit_field_keyboard(point_id))
    await state.set_state(PointForm.edit_choosing_field)
    await callback.answer()


# ── Выбор конкретного поля ───────────────────────

@dp.callback_query(PointForm.edit_choosing_field, F.data.startswith("field_"))
async def cb_field_select(callback: CallbackQuery, state: FSMContext):
    parts    = callback.data.split("_", 2)   # ["field", <field>, "<point_id>"]
    field    = parts[1]
    point_id = int(parts[2])
    data     = await state.get_data()

    if field == "done":
        await _save_edit_and_finish(state, callback.from_user, callback.message)
        await callback.answer("Сохранено!")
        return

    current = data.get(field, "—") or "—"

    if field == "name":
        await callback.message.edit_text(f"Текущее название: {current}\n\nВведите новое:")
        await state.set_state(PointForm.edit_name)

    elif field == "address":
        await callback.message.edit_text(f"Текущий адрес: {current}\n\nВведите новый:")
        await state.set_state(PointForm.edit_address)

    elif field == "phone":
        await callback.message.edit_text(f"Текущий телефон: {current}\n\nВведите новый:")
        await state.set_state(PointForm.edit_phone)

    elif field == "status":
        await callback.message.edit_text(
            f"Текущий статус: {current}\n\nВыберите новый:",
            reply_markup=status_keyboard("editstatus")
        )
        await state.set_state(PointForm.edit_status)

    elif field == "comment":
        await callback.message.edit_text(
            f"Текущий комментарий: {current}\n\nВведите новый (или «-» чтобы очистить):"
        )
        await state.set_state(PointForm.edit_comment)

    elif field == "owner":
        await callback.message.edit_text(
            f"Текущий ответственный: {current}\n\n"
            "Введите новый логин (например @username)\nили «-» чтобы очистить:"
        )
        await state.set_state(PointForm.edit_owner)

    await callback.answer()


# ── Обработка ввода для каждого поля ────────────

@dp.message(PointForm.edit_name)
async def edit_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await _back_to_field_menu(state, message)

@dp.message(PointForm.edit_address)
async def edit_address(message: Message, state: FSMContext):
    await state.update_data(address=message.text.strip())
    await _back_to_field_menu(state, message)

@dp.message(PointForm.edit_phone)
async def edit_phone(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(phone=None if text == "-" else text)
    await _back_to_field_menu(state, message)

@dp.callback_query(PointForm.edit_status, F.data.startswith("editstatus_"))
async def edit_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split("_", 1)[1]
    await state.update_data(status=status)
    await _back_to_field_menu(state, callback.message, is_callback=True)
    await callback.answer()

@dp.message(PointForm.edit_comment)
async def edit_comment(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(comment=None if text == "-" else text)
    await _back_to_field_menu(state, message)

@dp.message(PointForm.edit_owner)
async def edit_owner(message: Message, state: FSMContext):
    text = message.text.strip()
    await state.update_data(updated_by=None if text == "-" else text)
    await _back_to_field_menu(state, message)


async def _back_to_field_menu(state: FSMContext, msg, is_callback: bool = False):
    """Возвращает пользователя в меню выбора поля после редактирования одного поля."""
    data     = await state.get_data()
    point_id = data["point_id"]

    info = (
        f"📌 Редактируем точку #{point_id}\n\n"
        f"Название:      {data.get('name', '—') or '—'}\n"
        f"Адрес:         {data.get('address', '—') or '—'}\n"
        f"Телефон:       {data.get('phone', '—') or '—'}\n"
        f"Статус:        {data.get('status', '—') or '—'}\n"
        f"Комментарий:   {data.get('comment', '—') or '—'}\n"
        f"Ответственный: {data.get('updated_by', '—') or '—'}\n\n"
        "Что ещё изменить? Или нажмите «Сохранить всё»."
    )
    kb = edit_field_keyboard(point_id)

    if is_callback:
        await msg.edit_text(info, reply_markup=kb)
    else:
        await msg.answer(info, reply_markup=kb)

    await state.set_state(PointForm.edit_choosing_field)


async def _save_edit_and_finish(state: FSMContext, user: types.User, msg):
    data     = await state.get_data()
    # Берём ответственного из state (мог быть изменён вручную),
    # только если поле пустое — подставляем текущего пользователя
    updated_by = data.get("updated_by") or (
        f"@{user.username}" if user.username else f"ID{user.id}"
    )
    point = {
        "id":         data["point_id"],
        "name":       data.get("name"),
        "address":    data.get("address"),
        "phone":      data.get("phone"),
        "status":     data.get("status"),
        "comment":    data.get("comment"),
        "updated_by": updated_by,
        "owner_id":   user.id,
    }
    upsert_point(point)
    await msg.edit_text(
        f"✅ Точка #{data['point_id']} обновлена!\nСтатус: {data.get('status', '—')}"
    )
    await msg.answer("Ещё что-нибудь?", reply_markup=main_keyboard())
    await state.clear()


# ── Запуск ───────────────────────────────────────

async def main():
    print("Бот запущен")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
