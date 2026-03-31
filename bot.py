import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Sozlamalarni chaqiramiz
from config import BOT_TOKEN, MONGO_URL, TIMEZONE, ADMIN_ID
from handlers import router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# MongoDB ulanishi
cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["avto_post_db"]

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# ==================== TAYMER VAZIFASI ====================
async def check_and_post():
    try:
        now = datetime.now(TIMEZONE).isoformat()
        cursor = db.posts.find({"status": "pending", "time": {"$lte": now}})
        posts = await cursor.to_list(length=100)

        for p in posts:
            try:
                markup = None
                if p.get('b_text') and p.get('b_url'):
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=p['b_text'], url=p['b_url'])]
                    ])
                
                await bot.copy_message(
                    chat_id=p['target'],
                    from_chat_id=p['from_chat_id'],
                    message_id=p['message_id'],
                    reply_markup=markup
                )
                
                await db.posts.update_one({"_id": p["_id"]}, {"$set": {"status": "sent"}})
                
                # FloodWait (Blok) ga tushmaslik uchun himoya tormozi
                await asyncio.sleep(0.05)
                
            except Exception as e:
                # Xato bo'lsa adminga yozish
                error_msg = f"⚠️ **POST JONATISHDA XATO!**\nKanal: `{p['target']}`\nVaqti: `{p['time']}`\nXato: `{str(e)}`"
                await bot.send_message(chat_id=ADMIN_ID, text=error_msg)
                await db.posts.update_one({"_id": p["_id"]}, {"$set": {"status": "failed"}})
                
    except Exception as e:
        logging.error(f"Taymer xatosi: {e}")

# ==================== ISHGA TUSHIRISH ====================
async def main():
    dp.include_router(router)
    scheduler.add_job(check_and_post, "interval", minutes=1)
    scheduler.start()
    
    logging.info("🟢 Bot ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🔴 Bot to'xtatildi")
