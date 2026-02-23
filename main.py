import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")
WORK_HOURS = os.environ.get("WORK_HOURS", "09:00–23:00 (TM)")
CURRENT_RATE = float(os.environ.get("CURRENT_RATE", "0.0"))

ENTER_AMOUNT, CHOOSE_INPUT, CHOOSE_METHOD, ENTER_DETAILS = range(4)
user_sessions = {}

def fmt(n: float) -> str:
    s = f"{n:.6f}".rstrip("0").rstrip(".")
    return s if s else "0"

def new_order_id() -> str:
    return datetime.utcnow().strftime("%y%m%d%H%M%S")

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💵 USDT satyn almak", callback_data="flow_buy"),
         InlineKeyboardButton("💸 USDT satmak", callback_data="flow_sell")],
        [InlineKeyboardButton("📊 Kurs", callback_data="rate"),
         InlineKeyboardButton("💬 Goldaw", callback_data="support")],
    ])

def input_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧾 Manat boýunça", callback_data="in_manat")],
        [InlineKeyboardButton("🪙 USDT boýunça", callback_data="in_usdt")],
    ])

def method_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BEP20 (BSC)", callback_data="m_BEP20")],
        [InlineKeyboardButton("Aptos", callback_data="m_APTOS")],
        [InlineKeyboardButton("Binance ID", callback_data="m_BINANCE_ID")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salam! USDT alyş-çalyş boty.\n"
        f"Iş wagty: {WORK_HOURS}",
        reply_markup=main_menu()
    )

async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"1 manat = {fmt(CURRENT_RATE)} USDT"
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(str(update.effective_chat.id))

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_RATE
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return
    try:
        CURRENT_RATE = float(context.args[0])
        await update.message.reply_text(f"Täze kurs: 1 manat = {fmt(CURRENT_RATE)} USDT")
    except:
        await update.message.reply_text("Ulanylyşy: /setrate 0.0285")

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in ("flow_buy", "flow_sell"):
        flow = "BUY" if data == "flow_buy" else "SELL"
        user_sessions[query.from_user.id] = {"flow": flow}
        await query.edit_message_text("Manat ýa USDT?", reply_markup=input_menu())
        return CHOOSE_INPUT

    if data == "rate":
        await query.edit_message_text(
            f"1 manat = {fmt(CURRENT_RATE)} USDT",
            reply_markup=main_menu()
        )
        return ConversationHandler.END

    return ConversationHandler.END

async def choose_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    sess = user_sessions.get(query.from_user.id, {})
    sess["input"] = "MANAT" if data == "in_manat" else "USDT"
    user_sessions[query.from_user.id] = sess

    await query.edit_message_text("Mukdary giriziň:")
    return ENTER_AMOUNT

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    value = float(update.message.text.replace(",", "."))
    sess = user_sessions.get(update.effective_user.id, {})
    mode = sess.get("input")

    if mode == "MANAT":
        manat = value
        usdt = manat * CURRENT_RATE
    else:
        usdt = value
        manat = usdt / CURRENT_RATE

    sess["manat"] = manat
    sess["usdt"] = usdt
    user_sessions[update.effective_user.id] = sess

    await update.message.reply_text(
        f"{fmt(manat)} manat ≈ {fmt(usdt)} USDT\n"
        "Usuly saýlaň:",
        reply_markup=method_menu()
    )
    return CHOOSE_METHOD

async def choose_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    method = query.data.split("_")[1]

    sess = user_sessions.get(query.from_user.id, {})
    sess["method"] = method
    user_sessions[query.from_user.id] = sess

    await query.edit_message_text("Adres ýa Binance ID giriziň:")
    return ENTER_DETAILS

async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text
    sess = user_sessions.get(update.effective_user.id, {})
    order_id = new_order_id()

    text = (
        f"🆕 SARGYT #{order_id}\n"
        f"{fmt(sess['manat'])} manat ≈ {fmt(sess['usdt'])} USDT\n"
        f"Usul: {sess['method']}\n"
        f"Maglumat: {details}"
    )

    if ADMIN_CHAT_ID:
        await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=text)

    await update.message.reply_text("Sargyt kabul edildi.", reply_markup=main_menu())
    return ConversationHandler.END

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(on_button)],
        states={
            CHOOSE_INPUT: [CallbackQueryHandler(choose_input)],
            ENTER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_amount)],
            CHOOSE_METHOD: [CallbackQueryHandler(choose_method)],
            ENTER_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_details)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("rate", rate_cmd))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("setrate", set_rate))
    application.add_handler(conv)

    application.run_polling()

if __name__ == "__main__":
    main()
