from pymongo import MongoClient

def get_database():
    # Подключение к MongoDB
    client = MongoClient("mongodb://localhost:27017/")
    return client["game_key_store"]

db = get_database()