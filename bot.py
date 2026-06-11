import io
import logging
import warnings
from datetime import datetime

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
from telegram.warnings import PTBUserWarning

from config import BOT_TOKEN
import storage

warnings.filterwarnings("ignore", category=PTBUserWarning)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("remindmate")


BDAY_NAME, BDAY_DATE = range(2)
BDAY_DELETE = 10
NOTE_TEXT, NOTE_REMIND, NOTE_REPEAT = 20, 21, 22
NOTE_DELETE, NOTE_DONE, NOTE_EDIT_PICK, NOTE_EDIT_TEXT = 30, 31, 32, 33
NOTE_SEARCH = 40


def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🎂 Дни рождения", callback_data="menu_birthday")],
        [InlineKeyboardButton("📝 Заметки", callback_data="menu_notes")],
        [InlineKeyboardButton("🔔 Напоминания", callback_data="menu_reminders")],
        [InlineKeyboardButton("🔎 Поиск", callback_data="menu_search")],
        [InlineKeyboardButton("📤 Экспорт заметок", callback_data="menu_export")],
    ]
    return InlineKeyboardMarkup(keyboard)


def back_button():
    return [InlineKeyboardButton("← Назад", callback_data="back_main")]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет. Выбирай что нужно:",
        reply_markup=main_menu_keyboard(),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu_birthday":
        await birthday_menu(query)
    elif query.data == "menu_notes":
        await notes_menu(query)
    elif query.data == "menu_reminders":
        await reminders_menu(query)
    elif query.data == "menu_export":
        await export_notes(query, context)
    elif query.data == "back_main":
        await query.edit_message_text("Выбирай:", reply_markup=main_menu_keyboard())


async def birthday_menu(query):
    user_id = query.from_user.id
    bdays = storage.get_birthdays(user_id)

    if bdays:
        lines = []
        for b in bdays:
            days = storage.days_until(b["date"])
            tail = "сегодня 🎉" if days == 0 else f"через {days} дн."
            lines.append(f"#{b['id']} {b['name']} — {b['date']} ({tail})")
        text = "\n".join(lines)
    else:
        text = "Список пуст."

    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data="bday_add")],
        [InlineKeyboardButton("🗑 Удалить", callback_data="bday_del")],
        back_button(),
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def bday_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Чьё это? Напиши имя (или 'мой'):")
    return BDAY_NAME


async def bday_add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bday_name"] = update.message.text.strip()
    await update.message.reply_text("Дата в формате ДД.ММ.ГГГГ:")
    return BDAY_DATE


async def bday_add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        await update.message.reply_text("Неверный формат. Пиши ДД.ММ.ГГГГ")
        return BDAY_DATE

    storage.add_birthday(
        update.effective_user.id, context.user_data["bday_name"], text
    )
    days = storage.days_until(text)
    await update.message.reply_text(
        f"Сохранил. До этого дня: {days} дн.",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def bday_del_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    bdays = storage.get_birthdays(query.from_user.id)
    if not bdays:
        await query.edit_message_text("Удалять нечего.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    await query.edit_message_text("Напиши номер записи для удаления:")
    return BDAY_DELETE


async def bday_del_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        bday_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Напиши число.")
        return BDAY_DELETE

    storage.delete_birthday(update.effective_user.id, bday_id)
    await update.message.reply_text("Удалено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def notes_menu(query):
    user_id = query.from_user.id
    notes = storage.get_notes(user_id)

    if notes:
        lines = []
        for n in notes:
            status = "✅" if n["done"] else "📌"
            remind = f" ⏰ {n['remind_at']}" if n["remind_at"] else ""
            repeat = f" 🔁{n['repeat']}" if n["repeat"] != "once" else ""
            lines.append(f"{status} #{n['id']} {n['text']}{remind}{repeat}")
        text = "\n".join(lines)
    else:
        text = "Заметок нет."

    keyboard = [
        [InlineKeyboardButton("➕ Добавить", callback_data="note_add")],
        [InlineKeyboardButton("✏️ Редактировать", callback_data="note_edit")],
        [InlineKeyboardButton("✅ Отметить выполненной", callback_data="note_done")],
        [InlineKeyboardButton("🗑 Удалить", callback_data="note_del")],
        back_button(),
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def note_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Текст заметки:")
    return NOTE_TEXT


async def note_add_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["note_text"] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("Без напоминания", callback_data="no_remind")]]
    await update.message.reply_text(
        "Когда напомнить? Дата и время (ДД.ММ.ГГГГ ЧЧ:ММ) или кнопка:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return NOTE_REMIND


async def note_add_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        datetime.strptime(text, "%d.%m.%Y %H:%M")
    except ValueError:
        await update.message.reply_text("Неверный формат. ДД.ММ.ГГГГ ЧЧ:ММ")
        return NOTE_REMIND

    context.user_data["note_remind_at"] = text
    keyboard = [
        [InlineKeyboardButton("Один раз", callback_data="rep_once")],
        [InlineKeyboardButton("Каждый день", callback_data="rep_daily")],
        [InlineKeyboardButton("Каждую неделю", callback_data="rep_weekly")],
    ]
    await update.message.reply_text(
        "Повторять?", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return NOTE_REPEAT


async def note_add_repeat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    repeat = query.data.replace("rep_", "")

    note = storage.add_note(
        query.from_user.id,
        context.user_data["note_text"],
        context.user_data["note_remind_at"],
        repeat,
    )
    await query.edit_message_text(
        f"Заметка #{note['id']} сохранена. Напомню {note['remind_at']} ({repeat}).",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


async def note_add_no_remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    note = storage.add_note(query.from_user.id, context.user_data["note_text"])
    await query.edit_message_text(
        f"Заметка #{note['id']} сохранена.", reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


async def note_del_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    notes = storage.get_notes(query.from_user.id)
    if not notes:
        await query.edit_message_text("Нечего удалять.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    await query.edit_message_text("Номер заметки для удаления:")
    return NOTE_DELETE


async def note_del_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        note_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Напиши число.")
        return NOTE_DELETE
    storage.delete_note(update.effective_user.id, note_id)
    await update.message.reply_text("Удалено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def note_done_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    notes = storage.get_notes(query.from_user.id, only_active=True)
    if not notes:
        await query.edit_message_text("Нет активных заметок.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    await query.edit_message_text("Номер заметки, которую закрыть:")
    return NOTE_DONE


async def note_done_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        note_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Напиши число.")
        return NOTE_DONE
    storage.mark_note_done(update.effective_user.id, note_id)
    await update.message.reply_text("Готово ✅", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def note_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    notes = storage.get_notes(query.from_user.id)
    if not notes:
        await query.edit_message_text("Нечего редактировать.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END
    await query.edit_message_text("Номер заметки для редактирования:")
    return NOTE_EDIT_PICK


async def note_edit_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        note_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("Напиши число.")
        return NOTE_EDIT_PICK
    context.user_data["edit_note_id"] = note_id
    await update.message.reply_text("Новый текст:")
    return NOTE_EDIT_TEXT


async def note_edit_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    storage.update_note_text(
        update.effective_user.id,
        context.user_data["edit_note_id"],
        update.message.text.strip(),
    )
    await update.message.reply_text("Обновил.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Что ищем? Напиши слово или фразу:")
    return NOTE_SEARCH


async def search_run(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    notes = storage.search_notes(update.effective_user.id, q)
    if not notes:
        await update.message.reply_text("Ничего не нашёл.", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    lines = []
    for n in notes:
        status = "✅" if n["done"] else "📌"
        remind = f" ⏰ {n['remind_at']}" if n["remind_at"] else ""
        lines.append(f"{status} #{n['id']} {n['text']}{remind}")
    await update.message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())
    return ConversationHandler.END


async def reminders_menu(query):
    user_id = query.from_user.id
    notes = storage.get_notes(user_id, only_active=True)
    reminders = [n for n in notes if n["remind_at"]]

    if reminders:
        lines = []
        for n in reminders:
            repeat = f" 🔁{n['repeat']}" if n["repeat"] != "once" else ""
            lines.append(f"⏰ #{n['id']} {n['text']} — {n['remind_at']}{repeat}")
        text = "Активные напоминания:\n" + "\n".join(lines)
    else:
        text = "Нет активных напоминаний."

    await query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup([back_button()])
    )


async def export_notes(query, context):
    notes_text = storage.export_notes_text(query.from_user.id)
    if not notes_text:
        await query.edit_message_text(
            "Нечего экспортировать.", reply_markup=main_menu_keyboard()
        )
        return

    buf = io.BytesIO(notes_text.encode("utf-8"))
    buf.name = "notes.txt"
    await context.bot.send_document(
        chat_id=query.from_user.id,
        document=buf,
        filename="notes.txt",
        caption="Твои заметки",
    )
    await query.edit_message_text("Готово.", reply_markup=main_menu_keyboard())


async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    for user_id, note in storage.get_pending_reminders():
        repeat = note.get("repeat", "once")
        suffix = f" (повтор: {repeat})" if repeat != "once" else ""
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🔔 Напоминание: {note['text']}{suffix}",
        )


async def on_error(update, context):
    logger.exception("handler error", exc_info=context.error)


def build_app():
    storage.init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    bday_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bday_add_start, pattern="^bday_add$")],
        states={
            BDAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bday_add_name)],
            BDAY_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bday_add_date)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    bday_del_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(bday_del_start, pattern="^bday_del$")],
        states={
            BDAY_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bday_del_done)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    note_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note_add_start, pattern="^note_add$")],
        states={
            NOTE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_add_text)],
            NOTE_REMIND: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, note_add_remind),
                CallbackQueryHandler(note_add_no_remind, pattern="^no_remind$"),
            ],
            NOTE_REPEAT: [CallbackQueryHandler(note_add_repeat, pattern="^rep_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    note_del_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note_del_start, pattern="^note_del$")],
        states={
            NOTE_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_del_done)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    note_done_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note_done_start, pattern="^note_done$")],
        states={
            NOTE_DONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_done_finish)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    note_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(note_edit_start, pattern="^note_edit$")],
        states={
            NOTE_EDIT_PICK: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_edit_pick)],
            NOTE_EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, note_edit_text)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    search_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(search_start, pattern="^menu_search$")],
        states={
            NOTE_SEARCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_run)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(bday_add_conv)
    app.add_handler(bday_del_conv)
    app.add_handler(note_add_conv)
    app.add_handler(note_del_conv)
    app.add_handler(note_done_conv)
    app.add_handler(note_edit_conv)
    app.add_handler(search_conv)
    app.add_handler(CallbackQueryHandler(menu_handler))

    app.add_error_handler(on_error)

    app.job_queue.run_repeating(check_reminders, interval=60, first=10)
    return app


def main():
    app = build_app()
    print("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
