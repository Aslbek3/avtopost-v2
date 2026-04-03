import time
from datetime import datetime
import motor.motor_asyncio
from bson import ObjectId
import config

# Bot ishga tushgan vaqt (Uptime uchun)
BOT_START_TIME = time.time()

# Baza bilan ulanish
client = motor.motor_asyncio.AsyncIOMotorClient(config.MONGO_URL)
db = client[config.DB_NAME]

async def check_db_connection():
    try:
        await client.admin.command('ping')
        print("✅ Baza ulangan!")
    except Exception as e:
        print(f"❌ Baza xatosi: {e}")

# ================= KANALLAR VA USERLAR =================

async def is_admin(user_id: int) -> bool:
    if user_id in config.ADMINS:
        return True
    admin = await db.admins.find_one({"user_id": user_id})
    return bool(admin)

async def get_channels(user_id: int):
    user = await db.users.find_one({"user_id": user_id})
    if user and "channels" in user:
        return user["channels"]
    return []

async def add_channel(user_id: int, channel_id: str, channel_name: str, bot_username: str):
    new_ch = {
        "channel_id": channel_id,
        "channel_name": channel_name,
        "bot_username": bot_username
    }
    await db.users.update_one(
        {"user_id": user_id},
        {"$push": {"channels": new_ch}},
        upsert=True
    )

async def remove_channel(user_id: int, channel_id: str):
    await db.users.update_one(
        {"user_id": user_id},
        {"$pull": {"channels": {"channel_id": channel_id}}}
    )

# ================= AVTO-VAQT =================

async def get_auto_times(user_id: int):
    user = await db.users.find_one({"user_id": user_id})
    if user and "auto_times" in user:
        return user["auto_times"]
    return []

async def add_auto_time(user_id: int, new_time: str):
    await db.users.update_one(
        {"user_id": user_id},
        {"$addToSet": {"auto_times": new_time}},
        upsert=True
    )

async def delete_auto_time(user_id: int, time_val: str):
    await db.users.update_one(
        {"user_id": user_id},
        {"$pull": {"auto_times": time_val}}
    )

# ================= POSTLAR =================

async def add_post(user_id: int, text: str, photo_id: str, send_time: str, target_channels: list, queue_msg_id: int):
    post = {
        "owner_id": user_id,
        "text": text,
        "photo_id": photo_id,
        "send_time": send_time,
        "target_channels": target_channels,
        "queue_msg_id": queue_msg_id,
        "status": "pending"
    }
    await db.posts.insert_one(post)

async def get_pending_posts_for_user(user_id: int):
    return await db.posts.find({"owner_id": user_id, "status": "pending"}).to_list(length=None)

async def get_all_pending_posts():
    return await db.posts.find({"status": "pending"}).to_list(length=None)

async def mark_post_sent(post_id: ObjectId):
    await db.posts.update_one({"_id": post_id}, {"$set": {"status": "sent"}})

# ================= STATISTIKA =================

async def get_user_statistics(uid: int) -> str:
    # Userlar va adminlar
    total_users = await db.users.count_documents({})
    total_admins = await db.admins.count_documents({})
    
    # Kutayotgan postlar
    total_pending = await db.posts.count_documents({"status": "pending"})
    
    # Kanal bo'yicha hisob-kitob
    pipeline = [
        {"$match": {"status": "pending"}},
        {"$unwind": "$target_channels"},
        {"$group": {"_id": "$target_channels", "count": {"$sum": 1}}}
    ]
    channel_stats = await db.posts.aggregate(pipeline).to_list(length=None)
    
    channel_text = ""
    if channel_stats:
        channel_text = "\n📢 **Kanal kesimida kutilayotganlar:**\n"
        for stat in channel_stats:
            channel_text += f"  ├ `{stat['_id']}`: {stat['count']} ta\n"
    
    total_failed = await db.posts.count_documents({"status": "failed"})
    

    # Server va ping (ixcham formatda)
    uptime_seconds = int(time.time() - BOT_START_TIME)
    uptime_str = f"{uptime_seconds // 3600}s {(uptime_seconds % 3600) // 60}d"
    
    start_db_ping = time.time()
    await client.admin.command("ping")
    end_db_ping = time.time()
    db_ping_ms = round((end_db_ping - start_db_ping) * 1000)
    
    # Natijani ixcham dizaynda yig'ish
    text = (
        "📈   Bot Holati:  \n"
        f"├ 👥 Userlar: {total_users}    | 👮‍♂️ Adminlar: {total_admins}\n"
        f"├ ⏳ Navbatda: {total_pending} | ⚠️ Xatolar: {total_failed}\n"
        f"└ 🖥 Uptime: {uptime_str}       | ⚡️ Ping: {db_ping_ms}ms"
    )
    
    return text
