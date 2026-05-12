from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
import math

TOKEN = "8289029011:AAH61qPr65GYbpkRoCy-P_oh8csdlc2TMew"

user_data = {}

def get_expr(uid):
    if uid not in user_data:
        user_data[uid] = {"expr": "0", "history": []}
    return user_data[uid]

def make_keyboard():
    buttons = [
        ["7", "8", "9", "/"],
        ["4", "5", "6", "*"],
        ["1", "2", "3", "-"],
        ["0", ".", "=", "+"],
        ["C", "del", "sqrt", "hist"],
    ]
    keyboard = []
    for row in buttons:
        keyboard.append([InlineKeyboardButton(b, callback_data=b) for b in row])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/calc - открыть калькулятор\n/help - помощь"
    )

async def calc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    get_expr(uid)["expr"] = "0"
    await update.message.reply_text("0", reply_markup=make_keyboard())

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/calc - калькулятор\nsqrt - квадратный корень\nhist - история\ndel - удалить символ\nC - очистить"
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    uid = query.from_user.id
    data = get_expr(uid)
    expr = data["expr"]
    btn = query.data

    if btn == "C":
        expr = "0"

    elif btn == "del":
        expr = expr[:-1] if len(expr) > 1 else "0"

    elif btn == "=":
        try:
            result = eval(expr)
            if result == int(result):
                result = int(result)
            data["history"].append(f"{expr} = {result}")
            expr = str(result)
        except ZeroDivisionError:
            expr = "на 0 делить нельзя"
        except:
            expr = "ошибка"

    elif btn == "sqrt":
        try:
            val = eval(expr)
            result = round(math.sqrt(val), 6)
            expr = str(result)
        except:
            expr = "ошибка"

    elif btn == "hist":
        history = data["history"]
        if not history:
            await query.edit_message_text("История пуста", reply_markup=make_keyboard())
            return
        text = "История:\n" + "\n".join(history[-5:])
        await query.edit_message_text(text, reply_markup=make_keyboard())
        return

    else:
        if expr == "0" and btn not in "+-*/.":
            expr = btn
        else:
            expr += btn

    data["expr"] = expr
    try:
        await query.edit_message_text(expr, reply_markup=make_keyboard())
    except:
        pass

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("calc", calc))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CallbackQueryHandler(button))

print("бот запущен")
app.run_polling()