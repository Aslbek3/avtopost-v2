from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import config

cluster = AsyncIOMotorClient(config.MONGO_URL)
db = cluster.autopost_bot

async def check_db_connection():
    try:
        await cluster.admin.command('ping')
        print("✅ MongoDB ulandi!")
    except Exception as e:
        print(f"❌ Baza xatosi: {e}")

# ==================== ADMINLAR ====================
async def is_admin(user_id: int) -> bool:
    if user_id in config.ADMINS: return True
    return bool(await db.admins.find_one({"user_id": user_id}))

# ==================== KANALLAR ====================
async def get_channels(user_id: int):
    return await db.channels.find({"owner_id": user_id}).to_list(length=100)

async def add_channel(user_id: int, channel_id: str, channel_name: str, bot_username: str):
    await db.channels.update_one(
        {"channel_id": channel_id, "owner_id": user_id},
        {"$set": {"channel_name": channel_name, "bot_username": bot_username}},
        upsert=True
    )

async def remove_channel(user_id: int, channel_id: str):
    await db.channels.delete_one({"channel_id": channel_id, "owner_id": user_id})

# ==================== POSTLAR VA NAVBAT KANALI ====================
async def add_post(user_id: int, text: str, photo_id: str, send_time: str, target_channels: list, queue_msg_id: int = None):
    await db.posts.insert_one({
        "owner_id": user_id, 
        "text": text,
        "photo_id": photo_id,
        "send_time": send_time,
        "target_channels": target_channels,
        "queue_msg_id": queue_msg_id, # Navbat kanalidagi xabar ID si
        "status": "pending"
    })

# Adminlar o'zlarining postini ko'rishi uchun (Reja menyusi)
async def get_pending_posts_for_user(user_id: int):
    return await db.posts.find({"status": "pending", "owner_id": user_id}).sort("send_time", 1).to_list(length=100)

# Botning orqa fondagi taymeri uchun (Barcha kutilayotgan postlar)
async def get_all_pending_posts():
    return await db.posts.find({"status": "pending"}).to_list(length=1000)

async def mark_post_sent(post_id):
    await db.posts.delete_one({"_id": post_id})

# ==================== AVTO-VAQT ====================
async def get_auto_times(user_id: int):
    times = await db.autotimes.find({"owner_id": user_id}).to_list(length=50)
    return [t['time'] for t in times] if times else ["10:00", "15:00", "20:00"]

async def add_auto_time(user_id: int, time_val: str):
    await db.autotimes.insert_one({"owner_id": user_id, "time": time_val})

async def delete_auto_time(user_id: int, time_val: str):
    await db.autotimes.delete_one({"owner_id": user_id, "time": time_val})

# ==================== STATISTIKA ====================
async def get_user_statistics(user_id: int):
    ch_count = await db.channels.count_documents({"owner_id": user_id})
    p_count = await db.posts.count_documents({"owner_id": user_id, "status": "pending"})
    return f"📊 **Sizning statistikangiz:**\n\n📢 Kanallar: {ch_count} ta\n⏳ Navbatda: {p_count} ta"
