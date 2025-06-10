from database import Database

db = Database()
try:
    users = db.get_users()
    print("Users found:", users)
except Exception as e:
    print("Error:", e)