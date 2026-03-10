import asyncio
import sqlite3
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database import init_db, get_all_points, upsert_point

# ────────────────────────────────────────────────
BOT_TOKEN = os.environ.get("BOT_TOKEN")

init_db()

# ────────────────────────────────────────────────
class PointForm(StatesGroup):
    choosing_action = State()
    name = State()
    address = State()
    phone = State()
    status = State()
    comment = State()
    point_id = State()


def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, новая точка", callback_data="new")],
        [InlineKeyboardButton(text="Нет, изменить существующую", callback_data="edit")]
    ])


def status_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="работает",        callback_data="status_работает")],
        [InlineKeyboardButton(text="в проработке",    callback_data="status_в проработке")],
        [InlineKeyboardButton(text="закрыта",         callback_data="status_закрыта")],
        [InlineKeyboardButton(text="не работает",     callback_data="status_не работает")],
    ])


def skip_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить →", callback_data="skip_comment")]
    ])


def points_keyboard():
    points = get_all_points()
    if not points:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Пока нет точек", callback_data="no_points")]
        ])

    kb = []
    for p in sorted(points, key=lambda x: x["id"]):
        name_short = (p.get("name") or "Без названия")[:28]
        btn_text = f"#{p['id']} {name_short}…"
        kb.append([InlineKeyboardButton(text=btn_text, callback_data=f"edit_{p['id']}")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await message.answer(
        "Привет! Добавить новую точку или изменить старую?",
        reply_markup=main_keyboard()
    )
    await state.set_state(PointForm.choosing_action)


@dp.callback_query(F.data == "new")
async def cb_new(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Название точки:")
    await state.set_state(PointForm.name)
    await callback.answer()


@dp.callback_query(F.data == "edit")
async def cb_edit_choose(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Выбери точку:", reply_markup=points_keyboard())
    await callback.answer()


@dp.callback_query(F.data.startswith("edit_"))
async def cb_edit_select(callback: CallbackQuery, state: FSMContext):
    try:
        point_id = int(callback.data.split("_")[1])
    except:
        await callback.message.edit_text("Ошибка выбора точки")
        await state.clear()
        return

    points = get_all_points()
    point = next((p for p in points if p["id"] == point_id), None)
    if not point:
        await callback.message.edit_text("Точка не найдена")
        await state.clear()
        return

    await state.update_data(point_id=point_id)
    name = point.get("name", "—")
    await callback.message.edit_text(
        f"Редактируем #{point_id}\n\nТекущее название: {name}\n\nНовое (или «-»):"
    )
    await state.set_state(PointForm.name)
    await callback.answer()


@dp.message(PointForm.name)
async def process_name(message: Message, state: FSMContext):
    text = message.text.strip()
    if text != "-":
        await state.update_data(name=text)
    await message.answer("Адрес (или «-»):")
    await state.set_state(PointForm.address)


@dp.message(PointForm.address)
async def process_address(message: Message, state: FSMContext):
    text = message.text.strip()
    if text != "-":
        await state.update_data(address=text)
    await message.answer("Телефон (или «-»):")
    await state.set_state(PointForm.phone)


@dp.message(PointForm.phone)
async def process_phone(message: Message, state: FSMContext):
    text = message.text.strip()
    if text != "-":
        await state.update_data(phone=text)
    await message.answer("Статус:", reply_markup=status_keyboard())
    await state.set_state(PointForm.status)


@dp.callback_query(PointForm.status, F.data.startswith("status_"))
async def process_status(callback: CallbackQuery, state: FSMContext):
    status = callback.data.split("_", 1)[1]
    await state.update_data(status=status)
    await callback.message.edit_text(
        "Комментарий (или «Пропустить»):",
        reply_markup=skip_keyboard()
    )
    await state.set_state(PointForm.comment)
    await callback.answer()


@dp.message(PointForm.comment)
async def process_comment(message: Message, state: FSMContext):
    await state.update_data(comment=message.text.strip())
    await save_and_finish(state, message.from_user, message)


@dp.callback_query(PointForm.comment, F.data == "skip_comment")
async def skip_comment(callback: CallbackQuery, state: FSMContext):
    await save_and_finish(state, callback.from_user, callback.message)
    await callback.answer("Сохранено!")


async def save_and_finish(state: FSMContext, user: types.User, msg):
    data = await state.get_data()
    username = f"@{user.username}" if user.username else f"ID{user.id}"

    point = {
        "name": data.get("name"),
        "address": data.get("address"),
        "phone": data.get("phone"),
        "status": data.get("status"),
        "comment": data.get("comment"),
        "updated_by": username
    }

    if "point_id" in data:
        point["id"] = data["point_id"]

    upsert_point(point)

    text = f"✅ Готово!\nСтатус: {data.get('status', '—')}"
    if isinstance(msg, Message):
        await msg.answer(text, reply_markup=main_keyboard())
    else:
        await msg.edit_text(text)
        await msg.answer("Ещё?", reply_markup=main_keyboard())

    await state.clear()


async def main():
    print("Бот запущен")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())