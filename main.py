import os
import threading
import time
from datetime import datetime

from flask import Flask
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

# ---------- ENV ----------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID", "")  # admin chat_id (setir görnüşinde)
WORK_HOURS = os.environ.get("WORK_HOURS", "09:00–23:00 (TM)")

# 1 manat = X USDT (kursy /setrate bilen üýtgedýärsiň)
CURRENT_RATE = float(os.environ.get("CURRENT_RATE", "0.0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")


# ---------- States ----------
ENTER_AMOUNT, CHOOSE_INPUT, CHOOSE_METHOD, ENTER_DETAILS = range(4)

# In-memory sessions for MVP
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
        [InlineKeyboardButton("🧾 Manat boýunça (X manat)", callback_data="in_manat")],
        [InlineKeyboardButton("🪙 USDT boýunça (X USDT)", callback_data="in_usdt")],
        [InlineKeyboardButton("⬅️ Yza", callback_data="back_menu")],
    ])

def method_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("BEP20 (BSC)", callback_data="m_BEP20")],
        [InlineKeyboardButton("Aptos", callback_data="m_APTOS")],
        [InlineKeyboardButton("Binance ID", callback_data="m_BINANCE_ID")],
        [InlineKeyboardButton("⬅️ Yza", callback_data="back_menu")],
    ])

def looks_like_bep20_address(s: str) -> bool:
    s = s.strip()
    return s.startswith("0x") and len(s) == 42

def looks_like_aptos_address(s: str) -> bool:
    s = s.strip().lower()
    if not s.startswith("0x"):
        return False
    if len(s) < 34 or len(s) > 66:
        return False
    try:
        int(s[2:], 16)
        return True
    except ValueError:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salam! Men USDT alyş-çalyş sargyt boty.\n"
        f"⏰ Iş wagty: {WORK_HOURS}\n\n"
        "Birini saýlaň:",
        reply_markup=main_menu()
    )

async def rate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if CURRENT_RATE <= 0:
        await update.message.reply_text(
            "📊 Kurs häzir goýulmady.\n"
            "Operator bilen habarlaşyň."
        )
        return

    await update.message.reply_text(
        "📊 Häzirki kurs:\n"
        f"1 manat = {fmt(CURRENT_RATE)} USDT\n"
        f"⏰ Iş wagty: {WORK_HOURS}"
    )

async def support_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Soragyňyzy ýazyň — operator size jogap berer.")

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Siziň chat_id: {update.effective_chat.id}")

async def set_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CURRENT_RATE

    # diňe admin
    if str(update.effective_chat.id) != str(ADMIN_CHAT_ID):
        return

    if not context.args:
        await update.message.reply_text("Ulanylyşy: /setrate 0.0285")
        return

    try:
        new_rate = float(context.args[0].replace(",", "."))
        if new_rate <= 0:
            raise ValueError
        CURRENT_RATE = new_rate
        await update.message.reply_text(
            "✅ Täze kurs goýuldy:\n"
            f"1 manat = {fmt(CURRENT_RATE)} USDT"
        )
    except Exception:
        await update.message.reply_text("Nädogry format. Mysal: /setrate 0.0285")

async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_menu":
        await query.edit_message_text("Birini saýlaň:", reply_markup=main_menu())
        return ConversationHandler.END

    if data == "rate":
        if CURRENT_RATE <= 0:
            await query.edit_message_text(
                "📊 Kurs häzir goýulmady.\n"
                "Operator bilen habarlaşyň.",
                reply_markup=main_menu()
            )
            return ConversationHandler.END

        await query.edit_message_text(
            "📊 Häzirki kurs:\n"
            f"1 manat = {fmt(CURRENT_RATE)} USDT\n"
            f"⏰ Iş wagty: {WORK_HOURS}",
            reply_markup=main_menu()
        )
        return ConversationHandler.END

    if data == "support":
        await query.edit_message_text("Soragyňyzy ýazyň — operator jogap berer.")
        return ConversationHandler.END

    if data in ("flow_buy", "flow_sell"):
        if CURRENT_RATE <= 0:
            await query.edit_message_text(
                "📊 Kurs häzir goýulmady.\n"
                "Operator bilen habarlaşyň.",
                reply_markup=main_menu()
            )
            return ConversationHandler.END

        flow = "BUY" if data == "flow_buy" else "SELL"
        user_sessions[query.from_user.id] = {"flow": flow}
        await query.edit_message_text("Mukdary näme boýunça girizjek?", reply_markup=input_menu())
        return CHOOSE_INPUT

    return ConversationHandler.END

async def choose_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_menu":
        await query.edit_message_text("Birini saýlaň:", reply_markup=main_menu())
        return ConversationHandler.END

    sess = user_sessions.get(query.from_user.id, {})
    if data == "in_manat":
        sess["input"] = "MANAT"
        user_sessions[query.from_user.id] = sess
        await query.edit_message_text("Mukdary MANAT bilen giriziň (diňe san). Mysal: 1000")
        return ENTER_AMOUNT
    elif data == "in_usdt":
        sess["input"] = "USDT"
        user_sessions[query.from_user.id] = sess
        await query.edit_message_text("Mukdary USDT bilen giriziň (diňe san). Mysal: 200")
        return ENTER_AMOUNT

    return CHOOSE_INPUT

async def enter_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if CURRENT_RATE <= 0:
        await update.message.reply_text("Kurs häzir goýulmady. Operator bilen habarlaşyň.")
        return ConversationHandler.END

    text = (update.message.text or "").replace(",", ".").strip()
    try:
        value = float(text)
        if value <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("0-dan uly san bolmaly. Mysal: 1000")
        return ENTER_AMOUNT

    sess = user_sessions.get(update.effective_user.id, {})
    input_mode = sess.get("input", "MANAT")

    # Hasaplama
    if input_mode == "MANAT":
        manat = value
        usdt = manat * CURRENT_RATE
    else:
        usdt = value
        manat = usdt / CURRENT_RATE

    sess["manat"] = manat
    sess["usdt"] = usdt
    user_sessions[update.effective_user.id] = sess

    await update.message.reply_text(
        "Hasaplama:\n"
        f"{fmt(manat)} manat ≈ {fmt(usdt)} USDT\n"
        f"(1 manat = {fmt(CURRENT_RATE)} USDT)\n\n"
        "USDT ibermek/almak usulyny saýlaň:",
        reply_markup=method_menu()
    )
    return CHOOSE_METHOD

async def choose_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "back_menu":
        await query.edit_message_text("Birini saýlaň:", reply_markup=main_menu())
        return ConversationHandler.END

    if data.startswith("m_"):
        method = data.split("_", 1)[1]
        sess = user_sessions.get(query.from_user.id, {})
        sess["method"] = method
        user_sessions[query.from_user.id] = sess

        if method == "BINANCE_ID":
            await query.edit_message_text("Binance ID giriziň (diňe san).")
        elif method == "BEP20":
            await query.edit_message_text("USDT üçin BEP20 (BSC) adresiňizi giriziň. Mysal: 0x...")
        else:  # APTOS
            await query.edit_message_text("USDT üçin Aptos adresiňizi giriziň. Mysal: 0x...")
        return ENTER_DETAILS

    return CHOOSE_METHOD

async def enter_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = (update.message.text or "").strip()
    sess = user_sessions.get(update.effective_user.id, {})
    method = sess.get("method", "")

    if method == "BINANCE_ID":
        if not details.isdigit() or len(details) < 5:
            await update.message.reply_text("Binance ID diňe san bolmaly. Mysal: 123456789")
            return ENTER_DETAILS
        detail_label = "Binance ID"
    elif method == "BEP20":
        if not looks_like_bep20_address(details):
            await update.message.reply_text("Adres nädogry ýaly. BEP20 adres 0x... görnüşinde (42 nyşan).")
            return ENTER_DETAILS
        detail_label = "BEP20 adres"
    elif method == "APTOS":
        if not looks_like_aptos_address(details):
            await update.message.reply_text("Adres nädogry ýaly. Aptos adres adatça 0x bilen başlaýar (hex).")
            return ENTER_DETAILS
        detail_label = "Aptos adres"
    else:
        await update.message.reply_text("Ýalňyşlyk. /start ýazyp täzeden synanyşyň.")
        return ConversationHandler.END

    flow = sess.get("flow", "—")
    manat = float(sess.get("manat", 0.0))
    usdt = float(sess.get("usdt", 0.0))

    order_id = new_order_id()
    direction = "USDT satyn almak" if flow == "BUY" else "USDT satmak"
    method_name = "Binance ID" if method == "BINANCE_ID" else ("BEP20 (BSC)" if method == "BEP20" else "Aptos")

    user_text = (
        f"✅ Sargyt kabul edildi: #{order_id}\n"
        f"Amal: {direction}\n"
        f"Mukdar: {fmt(manat)} manat ≈ {fmt(usdt)} USDT\n"
        f"Kurs: 1 manat = {fmt(CURRENT_RATE)} USDT\n"
        f"Usul: {method_name}\n"
        f"{detail_label}: {details}\n\n"
        "Operator tiz wagtda habarlaşar we maglumatlary tassyklar."
    )
    await update.message.reply_text(user_text, reply_markup=main_menu())

    if ADMIN_CHAT_ID:
        admin_text = (
            f"🆕 TÄZE SARGYT #{order_id}\n"
            f"User: @{update.effective_user.username} (id={update.effective_user.id})\n"
            f"Amal: {direction}\n"
            f"Mukdar: {fmt(manat)} manat ≈ {fmt(usdt)} USDT\n"
            f"Kurs: 1 manat = {fmt(CURRENT_RATE)} USDT\n"
            f"Usul: {method_name}\n"
            f"{detail_label}: {details}\n"
            f"Wagt (UTC): {datetime.utcnow().isoformat(timespec='seconds')}"
        )
        try:
            await context.bot.send_message(chat_id=int(ADMIN_CHAT_ID), text=admin_text)
        except Exception:
            pass

    user_sessions.pop(update.effective_user.id, None)
    return ConversationHandler.END

def run_bot():
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
        allow_reentry=True,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("rate", rate_cmd))
    application.add_handler(CommandHandler("support", support_cmd))
    application.add_handler(CommandHandler("myid", myid))
    application.add_handler(CommandHandler("setrate", set_rate))
    application.add_handler(conv)

    application.run_polling(close_loop=False)

threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    run_bot()
