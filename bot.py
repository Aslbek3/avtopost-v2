import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, MONGO_URL, TIMEZONE, ADMINS
from handlers import router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["avto_post_db"]

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# ==================== TAYMER VA ANTISPAM ====================
async def check_and_post():
    try:
        now = datetime.now(TIMEZONE).isoformat()
        
        # Vaqti kelgan postlarni olish
        cursor = db.posts.find({"status": "pending", "time": {"$lte": now}})
        posts = await cursor.to_list(length=100) 

        for p in posts:
            try:
                # Tugma o'chirilgan, faqat postni o'zi ketadi
                await bot.copy_message(
                    chat_id=p['target'],
                    from_chat_id=p['from_chat_id'],
                    message_id=p['message_id']
                )
                
                # Statistika uchun: Yuborilgan vaqtni yozib qo'yamiz
                await db.posts.update_one(
                    {"_id": p["_id"]}, 
                    {"$set": {
                        "status": "sent", 
                        "sent_at": datetime.now(TIMEZONE).isoformat() # Kelajakdagi statistika uchun
                    }}
                )
                
                # ANTISPAM: Har bir post o'rtasida pauza (Bot bloklanmasligi uchun eng muhim qator!)
                await asyncio.sleep(0.05) 
                
            except Exception as e:
                # Xato bo'lsa, Failed statusi beriladi va adminga bildiriladi
                await db.posts.update_one({"_id": p["_id"]}, {"$set": {"status": "failed", "error": str(e)}})
                
                error_msg = (
                    f"⚠️ **POST JONATISHDA XATO!**\n\n"
                    f"Kanal: `{p['target']}`\n"
                    f"Vaqt: `{p['time']}`\n"
                    f"Sabab: `{str(e)}`\n\n"
                    f"*Eslatma: Bot kanalda adminligini tekshiring.*"
                )
                
                for admin in ADMINS:
                    try:
                        await bot.send_message(chat_id=admin, text=error_msg)
                    except Exception:
                        pass # Admin botni bloklagan bo'lsa, qotib qolmaydi
                
    except Exception as main_e:
        logging.error(f"Taymer xatosi: {main_e}")

# ==================== ISHGA TUSHIRISH ====================
async def main():
    dp.include_router(router)
    
    scheduler.add_job(check_and_post, "interval", minutes=1)
    scheduler.start()
    
    logging.info("🟢 Basic Bot (Antispam bilan) ishga tushdi...")
    
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🔴 Bot to'xtatildi")
