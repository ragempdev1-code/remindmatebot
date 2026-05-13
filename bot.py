from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import BOT_TOKEN
import storage

BIRTHDAY_INPUT = 0
NOTE_TEXT = 1
NOTE_REMIND = 2
NOTE_DELETE = 3


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎂 День рождения", callback_data="menu_birthday")],
        [InlineKeyboardButton("📝 Заметки", callback_data="menu_notes")],
        [InlineKeyboardButton("🔔 Напоминания", callback_data="menu_reminders")],
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Выбирай что нужно:",
        reply_markup=main_menu_keyboard()
    )


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_birthday":
        await birthday_menu(query, context)
    elif query.data == "menu_notes":
        await notes_menu(query, context)
    elif query.data == "menu_reminders":
        await reminders_menu(query, context)
    elif query.data == "back_main":
        await query.edit_message_text("Выбирай:", reply_markup=main_menu_keyboard())


async def birthday_menu(query, context):
    user_id = query.from_user.id
    days = storage.days_until_birthday(user_id)

    if days is not None:
        if days == 0:
            text = "🎉 Сегодня твой день рождения!"
        else:
            text = f"До дня рождения: {days} дн."
    else:
        text = "Дата не установлена."

    keyboard = [
        [InlineKeyboardButton("Установить дату", callback_data="set_birthday")],
        [InlineKeyboardButton("← Назад", callback_data="back_main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def set_birthday_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Напиши дату рождения в формате ДД.ММ.ГГГГ")
    return BIRTHDAY_INPUT


async def set_birthday_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    try:
        from datetime import datetime
        datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пиши ДД.ММ.ГГГГ")
        return BIRTHDAY_INPUT

    storage.set_birthday(update.effective_user.id, text)
    days = storage.days_until_birthday(update.effective_user.id)

    await update.message.reply_text(
        f"Сохранил. До дня рождения: {days} дн.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def notes_menu(query, context):
    user_id = query.from_user.id
    notes = storage.get_notes(user_id)

    if notes:
        lines = []
        for n in notes:
            status = "✅" if n["done"] else "📌"
            remind = f" (⏰ {n['remind_at']})" if n.get("remind_at") else ""
            lines.append(f"{status} {n['id']}. {n['text']}{remind}")
        text = "\n".join(lines)
    else:
        text = "Заметок нет."

    keyboard = [
        [InlineKeyboardButton("Добавить заметку", callback_data="add_note")],
        [InlineKeyboardButton("Удалить заметку", callback_data="del_note")],
        [InlineKeyboardButton("← Назад", callback_data="back_main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def add_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Напиши текст заметки:")
    return NOTE_TEXT


async def add_note_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["note_text"] = update.message.text.strip()

    keyboard = [
        [InlineKeyboardButton("Без напоминания", callback_data="no_remind")],
    ]
    await update.message.reply_text(
        "Когда напомнить? Напиши дату и время (ДД.ММ.ГГГГ ЧЧ:ММ) или нажми кнопку:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return NOTE_REMIND


async def add_note_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    try:
        from datetime import datetime
        datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пиши ДД.ММ.ГГГГ ЧЧ:ММ")
        return NOTE_REMIND

    note = storage.add_note(update.effective_user.id, context.user_data["note_text"], text)
    await update.message.reply_text(
        f"Заметка #{note['id']} сохранена. Напомню {text}",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def add_note_no_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    note = storage.add_note(query.from_user.id, context.user_data["note_text"])
    await query.edit_message_text(
        f"Заметка #{note['id']} сохранена.",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def del_note_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    notes = storage.get_notes(query.from_user.id)
    if not notes:
        await query.edit_message_text("Нечего удалять.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    await query.edit_message_text("Напиши номер заметки для удаления:")
    return NOTE_DELETE


async def del_note_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        note_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Напиши число.")
        return NOTE_DELETE

    storage.delete_note(update.effective_user.id, note_id)
    await update.message.reply_text("Удалено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def reminders_menu(query, context):
    user_id = query.from_user.id
    notes = storage.get_notes(user_id)
    reminders = [n for n in notes if n.get("remind_at") and not n.get("done")]

    if reminders:
        lines = [f"⏰ {n['id']}. {n['text']} — {n['remind_at']}" for n in reminders]
        text = "Активные напоминания:\n" + "\n".join(lines)
    else:
        text = "Нет активных напоминаний."

    keyboard = [
        [InlineKeyboardButton("← Назад", callback_data="back_main")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    reminders = storage.get_pending_reminders()
    for user_id, note in reminders:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🔔 Напоминание: {note['text']}"
        )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    birthday_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_birthday_start, pattern="^set_birthday$")],
        states={
            BIRTHDAY_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_birthday_done)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    add_note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_note_start, pattern="^add_note$")],
        states={
            NOTE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_text)],
            NOTE_REMIND: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_note_remind),
                CallbackQueryHandler(add_note_no_remind, pattern="^no_remind$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    del_note_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(del_note_start, pattern="^del_note$")],
        states={
            NOTE_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, del_note_done)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(birthday_conv)
    app.add_handler(add_note_conv)
    app.add_handler(del_note_conv)
    app.add_handler(CallbackQueryHandler(menu_handler))

    app.job_queue.run_repeating(check_reminders, interval=60, first=10)

    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
