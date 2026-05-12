import logging
import math
import random
import time
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN = "8289029011:AAH61qPr65GYbpkRoCy-P_oh8csdlc2TMew"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Состояние калькулятора ────────────────────────────────────────────────────
# user_id -> {"expr": str, "memory": float, "history": list}
calc_state: dict[int, dict] = {}

def get_state(user_id: int) -> dict:
    if user_id not in calc_state:
        calc_state[user_id] = {"expr": "0", "memory": 0.0, "history": []}
    return calc_state[user_id]

# ─── Клавиатура калькулятора ──────────────────────────────────────────────────
def build_keyboard(expr: str, memory: float) -> InlineKeyboardMarkup:
    mem_label = f"MR({memory:g})" if memory != 0 else "MR"
    rows = [
        [
            InlineKeyboardButton("AC", callback_data="ac"),
            InlineKeyboardButton("+/-", callback_data="neg"),
            InlineKeyboardButton("%",  callback_data="pct"),
            InlineKeyboardButton("÷",  callback_data="op_/"),
        ],
        [
            InlineKeyboardButton("7", callback_data="d_7"),
            InlineKeyboardButton("8", callback_data="d_8"),
            InlineKeyboardButton("9", callback_data="d_9"),
            InlineKeyboardButton("×", callback_data="op_*"),
        ],
        [
            InlineKeyboardButton("4", callback_data="d_4"),
            InlineKeyboardButton("5", callback_data="d_5"),
            InlineKeyboardButton("6", callback_data="d_6"),
            InlineKeyboardButton("-", callback_data="op_-"),
        ],
        [
            InlineKeyboardButton("1", callback_data="d_1"),
            InlineKeyboardButton("2", callback_data="d_2"),
            InlineKeyboardButton("3", callback_data="d_3"),
            InlineKeyboardButton("+", callback_data="op_+"),
        ],
        [
            InlineKeyboardButton("0",   callback_data="d_0"),
            InlineKeyboardButton(".",   callback_data="dot"),
            InlineKeyboardButton("⌫",   callback_data="bs"),
            InlineKeyboardButton("=",   callback_data="eq"),
        ],
        [
            InlineKeyboardButton("MS",    callback_data="ms"),
            InlineKeyboardButton(mem_label, callback_data="mr"),
            InlineKeyboardButton("MC",    callback_data="mc"),
            InlineKeyboardButton("√",     callback_data="sqrt"),
        ],
    ]
    return InlineKeyboardMarkup(rows)

def render_display(expr: str) -> str:
    # красиво отображаем выражение
    display = expr.replace("*", "×").replace("/", "÷")
    return f"```\n{'─'*22}\n  {display:>20}\n{'─'*22}\n```"

def safe_eval(expr: str) -> str:
    """Безопасное вычисление математического выражения."""
    allowed = set("0123456789+-*/.() ")
    if not all(c in allowed for c in expr):
        return "Ошибка"
    try:
        result = eval(expr, {"__builtins__": {}}, {})  # noqa: S307
        if isinstance(result, float):
            if result == int(result) and abs(result) < 1e15:
                return str(int(result))
            return f"{result:.10g}"
        return str(result)
    except ZeroDivisionError:
        return "Деление на 0"
    except Exception:
        return "Ошибка"

# ─── Команда /start ────────────────────────────────────────────────────────────
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    name = update.effective_user.first_name
    text = (
        f"👋 Привет, *{name}*!\n\n"
        "Я — продвинутый калькулятор-бот.\n\n"
        "🔢 /calc — открыть калькулятор\n"
        "📊 /history — история вычислений\n"
        "🎲 /random — случайное число\n"
        "📐 /math — математические константы\n"
        "💱 /convert — конвертер единиц\n"
        "❓ /help — полная справка\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ─── Команда /calc ─────────────────────────────────────────────────────────────
async def cmd_calc(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    state = get_state(user_id)
    state["expr"] = "0"

    msg = await update.message.reply_text(
        render_display("0"),
        parse_mode="Markdown",
        reply_markup=build_keyboard("0", state["memory"]),
    )
    # сохраняем message_id чтобы редактировать
    state["msg_id"] = msg.message_id
    state["chat_id"] = update.effective_chat.id

# ─── Обработка кнопок калькулятора ────────────────────────────────────────────
async def on_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    state = get_state(user_id)
    data = query.data
    expr = state["expr"]

    # --- очистка ---
    if data == "ac":
        expr = "0"

    # --- удаление символа ---
    elif data == "bs":
        expr = expr[:-1] if len(expr) > 1 else "0"

    # --- цифры ---
    elif data.startswith("d_"):
        digit = data[2:]
        expr = digit if expr == "0" else expr + digit

    # --- точка ---
    elif data == "dot":
        # не добавлять вторую точку в текущее число
        parts = expr.replace("+", " ").replace("-", " ").replace("*", " ").replace("/", " ").split()
        last = parts[-1] if parts else ""
        if "." not in last:
            expr = expr + "."

    # --- операторы ---
    elif data.startswith("op_"):
        op = data[3:]
        if expr[-1] in "+-*/":
            expr = expr[:-1] + op
        else:
            expr = expr + op

    # --- знак +/- ---
    elif data == "neg":
        try:
            val = safe_eval(expr)
            if val not in ("Ошибка", "Деление на 0"):
                expr = str(-float(val)) if "." in val or float(val) != int(float(val)) else str(-int(float(val)))
        except Exception:
            pass

    # --- процент ---
    elif data == "pct":
        try:
            val = safe_eval(expr)
            if val not in ("Ошибка", "Деление на 0"):
                v = float(val) / 100
                expr = str(int(v)) if v == int(v) else f"{v:.10g}"
        except Exception:
            pass

    # --- квадратный корень ---
    elif data == "sqrt":
        try:
            val = safe_eval(expr)
            if val not in ("Ошибка", "Деление на 0"):
                v = math.sqrt(float(val))
                expr = str(int(v)) if v == int(v) else f"{v:.10g}"
        except Exception:
            expr = "Ошибка"

    # --- равно ---
    elif data == "eq":
        original = expr
        result = safe_eval(expr)
        state["history"].append(f"{original} = {result}")
        if len(state["history"]) > 20:
            state["history"] = state["history"][-20:]
        expr = result

    # --- память: сохранить ---
    elif data == "ms":
        try:
            val = safe_eval(expr)
            if val not in ("Ошибка", "Деление на 0"):
                state["memory"] = float(val)
        except Exception:
            pass

    # --- память: вспомнить ---
    elif data == "mr":
        mem = state["memory"]
        expr = str(int(mem)) if mem == int(mem) else f"{mem:.10g}"

    # --- память: очистить ---
    elif data == "mc":
        state["memory"] = 0.0

    state["expr"] = expr

    try:
        await query.edit_message_text(
            render_display(expr),
            parse_mode="Markdown",
            reply_markup=build_keyboard(expr, state["memory"]),
        )
    except Exception:
        pass  # текст не изменился — Telegram выбросит исключение, игнорируем

# ─── Команда /history ─────────────────────────────────────────────────────────
async def cmd_history(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    state = get_state(user_id)
    history = state.get("history", [])

    if not history:
        await update.message.reply_text("📋 История пуста. Посчитай что-нибудь через /calc!")
        return

    lines = "\n".join(f"`{i+1}.` {h}" for i, h in enumerate(history[-10:]))
    await update.message.reply_text(
        f"📊 *Последние вычисления:*\n\n{lines}",
        parse_mode="Markdown",
    )

# ─── Команда /random ──────────────────────────────────────────────────────────
async def cmd_random(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    try:
        if len(args) == 2:
            a, b = int(args[0]), int(args[1])
        elif len(args) == 1:
            a, b = 1, int(args[0])
        else:
            a, b = 1, 100
    except ValueError:
        await update.message.reply_text("⚠️ Использование: /random [мин] [макс]")
        return

    if a > b:
        a, b = b, a

    n = random.randint(a, b)
    bar_len = 20
    pos = int((n - a) / max(b - a, 1) * bar_len)
    bar = "░" * pos + "█" + "░" * (bar_len - pos - 1)

    await update.message.reply_text(
        f"🎲 *Случайное число* от {a} до {b}\n\n"
        f"`[{bar}]`\n\n"
        f"Результат: *{n}*",
        parse_mode="Markdown",
    )

# ─── Команда /math ────────────────────────────────────────────────────────────
async def cmd_math(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    constants = {
        "π (Пи)": math.pi,
        "e (Эйлер)": math.e,
        "φ (Золотое сечение)": (1 + math.sqrt(5)) / 2,
        "√2 (корень из 2)": math.sqrt(2),
        "√3 (корень из 3)": math.sqrt(3),
        "ln(2)": math.log(2),
        "ln(10)": math.log(10),
    }
    lines = "\n".join(f"• *{k}* = `{v:.10f}`" for k, v in constants.items())
    await update.message.reply_text(
        f"📐 *Математические константы:*\n\n{lines}",
        parse_mode="Markdown",
    )

# ─── Команда /convert ─────────────────────────────────────────────────────────
CONVERSIONS = {
    # длина
    ("км", "м"): 1000, ("м", "км"): 0.001,
    ("м", "см"): 100, ("см", "м"): 0.01,
    ("км", "миль"): 0.621371, ("миль", "км"): 1.60934,
    ("м", "фут"): 3.28084, ("фут", "м"): 0.3048,
    # масса
    ("кг", "г"): 1000, ("г", "кг"): 0.001,
    ("кг", "фунт"): 2.20462, ("фунт", "кг"): 0.453592,
    ("кг", "унц"): 35.274, ("унц", "кг"): 0.0283495,
    # температура (handled separately)
    # скорость
    ("км/ч", "м/с"): 0.277778, ("м/с", "км/ч"): 3.6,
    ("км/ч", "миль/ч"): 0.621371, ("миль/ч", "км/ч"): 1.60934,
    # площадь
    ("м²", "см²"): 10000, ("см²", "м²"): 0.0001,
    ("га", "м²"): 10000, ("м²", "га"): 0.0001,
    # байты
    ("байт", "кб"): 1/1024, ("кб", "байт"): 1024,
    ("кб", "мб"): 1/1024, ("мб", "кб"): 1024,
    ("мб", "гб"): 1/1024, ("гб", "мб"): 1024,
}

async def cmd_convert(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    args = ctx.args
    if len(args) != 3:
        units = ", ".join(set(k for pair in CONVERSIONS for k in pair))
        await update.message.reply_text(
            "💱 *Конвертер единиц*\n\n"
            "Использование: `/convert [число] [из] [в]`\n\n"
            f"Доступные единицы:\n`{units}`\n\n"
            "Примеры:\n"
            "`/convert 5 км м`\n"
            "`/convert 100 кг фунт`\n"
            "`/convert 1024 кб мб`",
            parse_mode="Markdown",
        )
        return

    try:
        value = float(args[0])
        from_unit = args[1].lower()
        to_unit = args[2].lower()
    except ValueError:
        await update.message.reply_text("⚠️ Первый аргумент должен быть числом.")
        return

    key = (from_unit, to_unit)
    if key in CONVERSIONS:
        result = value * CONVERSIONS[key]
        await update.message.reply_text(
            f"💱 *Конвертация:*\n\n"
            f"`{value:g} {from_unit}` → *{result:g} {to_unit}*",
            parse_mode="Markdown",
        )
    elif from_unit in ("°c", "цельс") and to_unit in ("°f", "фар"):
        result = value * 9/5 + 32
        await update.message.reply_text(f"🌡 `{value}°C` = *{result:.2f}°F*", parse_mode="Markdown")
    elif from_unit in ("°f", "фар") and to_unit in ("°c", "цельс"):
        result = (value - 32) * 5/9
        await update.message.reply_text(f"🌡 `{value}°F` = *{result:.2f}°C*", parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"❌ Не знаю как конвертировать `{from_unit}` → `{to_unit}`.\n"
            "Напиши /convert без аргументов чтобы увидеть список.",
            parse_mode="Markdown",
        )

# ─── Команда /help ────────────────────────────────────────────────────────────
async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "📖 *Полная справка*\n\n"
        "*/calc* — открыть интерактивный калькулятор\n"
        "   • Поддерживает: `+ - × ÷ % √`\n"
        "   • Память: MS (сохранить), MR (вспомнить), MC (очистить)\n"
        "   • Кнопка ⌫ — стереть последний символ\n\n"
        "*/history* — последние 10 вычислений\n\n"
        "*/random [мин] [макс]* — случайное число\n"
        "   Пример: `/random 1 6` (бросить кубик)\n\n"
        "*/math* — математические константы (π, e, φ...)\n\n"
        "*/convert [число] [из] [в]* — конвертер единиц\n"
        "   Пример: `/convert 100 км миль`\n\n"
        "*/help* — эта справка",
        parse_mode="Markdown",
    )

# ─── Неизвестные сообщения ─────────────────────────────────────────────────────
async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    tips = [
        "Попробуй /calc чтобы открыть калькулятор!",
        "Хочешь случайное число? Напиши /random",
        "Посмотри константы через /math 📐",
        "Конвертируй единицы через /convert 💱",
    ]
    await update.message.reply_text(
        f"🤖 {random.choice(tips)}\n\nПолная справка: /help",
    )

# ─── Запуск ───────────────────────────────────────────────────────────────────
def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("calc",    cmd_calc))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("random",  cmd_random))
    app.add_handler(CommandHandler("math",    cmd_math))
    app.add_handler(CommandHandler("convert", cmd_convert))
    app.add_handler(CommandHandler("help",    cmd_help))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    print("🤖 Бот запущен! Нажми Ctrl+C для остановки.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()