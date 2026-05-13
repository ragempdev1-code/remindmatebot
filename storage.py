import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
NOTES_FILE = os.path.join(DATA_DIR, "notes.json")


def _load(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_birthday(user_id, date_str):
    data = _load(USERS_FILE)
    data[str(user_id)] = {"birthday": date_str}
    _save(USERS_FILE, data)


def get_birthday(user_id):
    data = _load(USERS_FILE)
    entry = data.get(str(user_id))
    if not entry:
        return None
    return entry.get("birthday")


def days_until_birthday(user_id):
    bday_str = get_birthday(user_id)
    if not bday_str:
        return None

    bday = datetime.strptime(bday_str, "%d.%m.%Y")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    next_bday = bday.replace(year=today.year)

    if next_bday < today:
        next_bday = next_bday.replace(year=today.year + 1)

    return (next_bday - today).days


def add_note(user_id, text, remind_at=None):
    data = _load(NOTES_FILE)
    user_notes = data.get(str(user_id), [])

    note = {
        "id": len(user_notes) + 1,
        "text": text,
        "remind_at": remind_at,
        "created_at": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "done": False
    }

    user_notes.append(note)
    data[str(user_id)] = user_notes
    _save(NOTES_FILE, data)
    return note


def get_notes(user_id):
    data = _load(NOTES_FILE)
    return data.get(str(user_id), [])


def delete_note(user_id, note_id):
    data = _load(NOTES_FILE)
    user_notes = data.get(str(user_id), [])
    user_notes = [n for n in user_notes if n["id"] != note_id]

    for i, note in enumerate(user_notes):
        note["id"] = i + 1

    data[str(user_id)] = user_notes
    _save(NOTES_FILE, data)


def get_pending_reminders():
    data = _load(NOTES_FILE)
    now = datetime.now()
    results = []

    for user_id, notes in data.items():
        for note in notes:
            if note.get("remind_at") and not note.get("done"):
                remind_time = datetime.strptime(note["remind_at"], "%d.%m.%Y %H:%M")
                if remind_time <= now:
                    note["done"] = True
                    results.append((int(user_id), note))

    _save(NOTES_FILE, data)
    return results
