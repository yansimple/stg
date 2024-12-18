import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
from config import BOT_TOKEN, ADMIN_ID, BTC_WALLET
from db.mongodb_setup import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Коллекции MongoDB
users_collection = db["users"]
orders_collection = db["orders"]
keys_collection = db["keys"]

# Команда /start
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    users_collection.update_one(
        {"user_id": user.id},
        {"$setOnInsert": {"username": user.username, "first_name": user.first_name}},
        upsert=True,
    )
    update.message.reply_text(
        "Добро пожаловать в магазин игровых ключей! Используйте /shop для покупки."
    )

# Команда /shop
def shop(update: Update, context: CallbackContext) -> None:
    keys = list(keys_collection.find({"sold": False}))
    if not keys:
        update.message.reply_text("Ключей пока нет в наличии. Загляните позже!")
        return

    keyboard = [
        [InlineKeyboardButton(key["game"], callback_data=f"buy:{key['_id']}")]
        for key in keys
    ]
    update.message.reply_text(
        "Выберите игру для покупки:", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Покупка ключа
def handle_buy(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    query.answer()

    key_id = query.data.split(":")[1]
    key = keys_collection.find_one({"_id": key_id, "sold": False})

    if not key:
        query.edit_message_text("Ключ уже продан или недоступен.")
        return

    btc_amount = key["price_btc"]
    btc_address = BTC_WALLET

    orders_collection.insert_one(
        {
            "user_id": query.from_user.id,
            "key_id": key_id,
            "btc_amount": btc_amount,
            "status": "pending",
        }
    )

    query.edit_message_text(
        f"Для завершения покупки отправьте {btc_amount} BTC на адрес:\n{btc_address}"
    )

# Панель администратора
def admin_panel(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("У вас нет доступа к панели администратора.")
        return

    keyboard = [
        [InlineKeyboardButton("Добавить ключ", callback_data="add_key")],
        [InlineKeyboardButton("Просмотр заказов", callback_data="view_orders")],
    ]
    update.message.reply_text(
        "Панель администратора", reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Добавление ключей
def add_key(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        update.message.reply_text("У вас нет доступа.")
        return

    update.message.reply_text(
        "Отправьте информацию о ключе в формате:\nИгра|Ключ|Цена (BTC)"
    )

def handle_add_key(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        return

    try:
        game, key, price = update.message.text.split("|")
        keys_collection.insert_one(
            {"game": game.strip(), "key": key.strip(), "price_btc": float(price.strip()), "sold": False}
        )
        update.message.reply_text(f"Ключ для {game.strip()} добавлен успешно!")
    except Exception as e:
        update.message.reply_text("Ошибка! Проверьте формат ввода.")

# Просмотр заказов
def view_orders(update: Update, context: CallbackContext) -> None:
    if update.effective_user.id != ADMIN_ID:
        return

    orders = list(orders_collection.find())
    if not orders:
        update.message.reply_text("Заказов пока нет.")
        return

    for order in orders:
        update.message.reply_text(
            f"ID: {order['_id']}\nПользователь: {order['user_id']}\nСумма BTC: {order['btc_amount']}\nСтатус: {order['status']}"
        )

# Основная функция
def main():
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("shop", shop))
    dispatcher.add_handler(CommandHandler("admin", admin_panel))
    dispatcher.add_handler(MessageHandler(Filters.text & Filters.user(ADMIN_ID), handle_add_key))

    dispatcher.add_handler(CallbackQueryHandler(handle_buy, pattern="^buy:"))
    dispatcher.add_handler(CallbackQueryHandler(add_key, pattern="^add_key$"))
    dispatcher.add_handler(CallbackQueryHandler(view_orders, pattern="^view_orders$"))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()