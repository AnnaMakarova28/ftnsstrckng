import asyncio
import requests, json

from aiogram import Bot, Dispatcher
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from config import API_TOKEN, WEATHER_API_KEY
from utils import get_food_info

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

users: dict[int, dict] = {}


@dp.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот для трекинга воды/калорий/тренировок.\n\n"
        "Команды:\n"
        "/set_profile — настроить профиль\n"
        "/log_water  — добавить воду (мл)\n"
        "/log_food — добавить еду\n"
        "/log_workout бег — добавить тренировку\n"
        "/check_progress — прогресс за день\n"
        "/help — помощь"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await cmd_start(message)


class ProfileStates(StatesGroup):
    weight = State()
    height = State()
    age = State()
    activity = State()
    city = State()
    calorie_goal = State()


class FoodStates(StatesGroup):
    grams = State()


@dp.message(Command("set_profile"))
async def cmd_set_profile(message: Message, state: FSMContext) -> None:
    await state.set_state(ProfileStates.weight)
    await message.answer("Введите ваш вес (в кг):")


@dp.message(ProfileStates.weight)
async def set_weight(message: Message, state: FSMContext) -> None:
    try:
        weight = float(message.text.replace(",", "."))
    except (TypeError, ValueError):
        await message.answer("Введите число, например: 80")
        return
    await state.update_data(weight=weight)
    await state.set_state(ProfileStates.height)
    await message.answer("Введите ваш рост (в см):")


@dp.message(ProfileStates.height)
async def set_height(message: Message, state: FSMContext) -> None:
    try:
        height = float(message.text.replace(",", "."))
    except (TypeError, ValueError):
        await message.answer("Введите число, например: 180")
        return
    await state.update_data(height=height)
    await state.set_state(ProfileStates.age)
    await message.answer("Введите ваш возраст:")


@dp.message(ProfileStates.age)
async def set_age(message: Message, state: FSMContext) -> None:
    try:
        age = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите целое число, например: 25")
        return
    await state.update_data(age=age)
    await state.set_state(ProfileStates.activity)
    await message.answer("Сколько минут активности у вас в день?")


@dp.message(ProfileStates.activity)
async def set_activity(message: Message, state: FSMContext) -> None:
    try:
        activity = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите целое число, например: 45")
        return
    await state.update_data(activity=activity)
    await state.set_state(ProfileStates.city)
    await message.answer("В каком городе вы находитесь?")


@dp.message(ProfileStates.city)
async def set_city(message: Message, state: FSMContext) -> None:
    city = (message.text or "").strip()
    if not city:
        await message.answer("Введите название города, например: Moscow")
        return
    await state.update_data(city=city)
    await state.set_state(ProfileStates.calorie_goal)
    await message.answer("Цель по калориям (введите число или 0 для авто):")


@dp.message(ProfileStates.calorie_goal)
async def set_calorie_goal(message: Message, state: FSMContext) -> None:
    try:
        calorie_goal = int(message.text)
    except (TypeError, ValueError):
        await message.answer("Введите целое число, например: 2500, или 0")
        return
    data = await state.get_data()
    weight = float(data["weight"])
    height = float(data["height"])
    city = data["city"]
    age = int(data["age"])

    #### calories ####
    if calorie_goal == 0:
        calorie_goal = int(10 * weight + 6.25 * height - 5 * age)

    activity = int(data["activity"])

    #### water ####
    water_goal = int(weight * 30 + (activity // 30) * 500)

    if WEATHER_API_KEY is not None and city is not None:
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        temp = int(response.json()["main"]["temp"])
    if temp > 30:
        water_goal += 1000
    elif temp > 25:
        water_goal += 500

    # save data
    users[message.from_user.id] = {
        "weight": weight,
        "height": height,
        "age": age,
        "activity": activity,
        "city": data["city"],
        "water_goal": water_goal,
        "calorie_goal": calorie_goal,
        "logged_water": 0,
        "logged_calories": 0,
        "burned_calories": 0,
    }
    await state.clear()
    await message.answer(
        "Профиль сохранен.\n"
        f"Норма воды: {water_goal} мл.\n"
        f"Цель калорий: {calorie_goal} ккал."
    )


@dp.message(Command("log_water"))
async def cmd_log_water(message: Message) -> None:
    user = users.get(message.from_user.id)
    if not user:
        await message.answer("Сначала настройте профиль: /set_profile")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Введите количество воды в мл, например: /log_water 250")
        return
    try:
        amount = int(parts[1])
    except ValueError:
        await message.answer("Введите число, например: /log_water 250")
        return
    if amount <= 0:
        await message.answer("Количество должно быть больше 0")
        return
    user["logged_water"] += amount
    remaining = max(user["water_goal"] - user["logged_water"], 0)
    await message.answer(
        f"Записано: {amount} мл.\n"
        f"Выпито: {user['logged_water']} мл из {user['water_goal']} мл.\n"
        f"Осталось: {remaining} мл."
    )


@dp.message(Command("log_food"))
async def cmd_log_food(message: Message, state: FSMContext) -> None:
    user = users.get(message.from_user.id)
    if not user:
        await message.answer("Сначала настройте профиль: /set_profile")
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Введите название продукта, например: /log_food банан")
        return
    query = parts[1].strip()
    info = get_food_info(query)
    if not info:
        await message.answer("Не удалось найти продукт. Попробуйте другое название.")
        return
    product, calories = info.values()
    await state.update_data(product=product, calories=calories)
    await state.set_state(FoodStates.grams)
    await message.answer(
        f"🍽 {product} — {calories} ккал на 100 г. Сколько грамм вы съели?"
    )


@dp.message(FoodStates.grams)
async def set_food_grams(message: Message, state: FSMContext) -> None:
    try:
        grams = float(message.text.replace(",", "."))
    except (TypeError, ValueError):
        await message.answer("Введите число, например: 150")
        return
    if grams <= 0:
        await message.answer("Количество должно быть больше 0")
        return
    data = await state.get_data()
    calories = float(data["calories"])
    kcal = calories * grams / 100
    users[message.from_user.id]["logged_calories"] += kcal
    await state.clear()
    await message.answer(f"Записано: {kcal:.1f} ккал.")


@dp.message(Command("log_workout"))
async def cmd_log_workout(message: Message) -> None:
    user = users.get(message.from_user.id)
    if not user:
        await message.answer("Сначала настройте профиль: /set_profile")
        return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Введите тип и время, например: /log_workout бег 30")
        return
    workout = parts[1].lower()
    try:
        minutes = int(parts[2])
    except ValueError:
        await message.answer("Введите время в минутах, например: 30")
        return
    if minutes <= 0:
        await message.answer("Время должно быть больше 0")
        return
    kcal_per_min = {
        "бег": 10,
        "ходьба": 4,
        "велосипед": 8,
        "плавание": 9,
        "силовая": 7,
    }.get(workout, 6)
    burned = kcal_per_min * minutes
    user["burned_calories"] += burned
    water_extra = (minutes // 30) * 200
    msg = f"🏃‍♂️ {workout} {minutes} минут — {burned} ккал."
    if water_extra > 0:
        msg += f" Дополнительно: выпейте {water_extra} мл воды."
    await message.answer(msg)


@dp.message(Command("check_progress"))
async def cmd_check_progress(message: Message) -> None:
    user = users.get(message.from_user.id)
    if not user:
        await message.answer("Сначала настройте профиль: /set_profile")
        return
    water_goal = user["water_goal"]
    water_logged = user["logged_water"]
    water_left = max(water_goal - water_logged, 0)
    cal_goal = user["calorie_goal"]
    cal_logged = user["logged_calories"]
    cal_burned = user["burned_calories"]
    cal_balance = cal_logged - cal_burned
    await message.answer(
        "📊 Прогресс:\n"
        "Вода:\n"
        f"- Выпито: {water_logged} мл из {water_goal} мл.\n"
        f"- Осталось: {water_left} мл.\n\n"
        "Калории:\n"
        f"- Потреблено: {cal_logged:.1f} ккал из {cal_goal} ккал.\n"
        f"- Сожжено: {cal_burned:.1f} ккал.\n"
        f"- Баланс: {cal_balance:.1f} ккал."
    )


# ----------------------------------------


async def main():
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
