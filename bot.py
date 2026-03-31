import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from motor.motor_asyncio import AsyncIOMotorClient
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Sozlamalarni chaqiramiz (ADMINS ro'yxat bo'lishi kerak)
from config import BOT_TOKEN, MONGO_URL, TIMEZONE, ADMINS
from handlers import router

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# MongoDB ulanishi
cluster = AsyncIOMotorClient(MONGO_URL)
db = cluster["avto_post_db"]

scheduler = AsyncIOScheduler(timezone=TIMEZONE)

# ==================== TAYMER VAZIFASI (SPAMGA QARSHI) ====================
async def check_and_post():
    try:
        now = datetime.now(TIMEZONE).isoformat()
        
        # Faqat vaqti kelgan va statusi "pending" bo'lganlarni olamiz
        cursor = db.posts.find({"status": "pending", "time": {"$lte": now}})
        posts = await cursor.to_list(length=100) # Bir urinishda 100 ta oladi

        for p in posts:
            try:
                markup = None
                if p.get('b_text') and p.get('b_url'):
                    markup = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text=p['b_text'], url=p['b_url'])]
                    ])
                
                # 1. Postni kanalga yuborish
                await bot.copy_message(
                    chat_id=p['target'],
                    from_chat_id=p['from_chat_id'],
                    message_id=p['message_id'],
                    reply_markup=markup
                )
                
                # 2. Muvaffaqiyatli bo'lsa, statusni 'sent' qilamiz
                await db.posts.update_one({"_id": p["_id"]}, {"$set": {"status": "sent"}})
                
                # 3. SPAMGA QARSHI TORMOZ: Har bir postdan keyin 0.05 soniya kutish
                await asyncio.sleep(0.05) 
                
            except Exception as e:
                # XATOLIK YUZ BERDI (Kanal o'chgan, bot bloklangan va hokazo)
                
                # Zudlik bilan statusni 'failed' qilamizki, qayta urinmasin
                await db.posts.update_one({"_id": p["_id"]}, {"$set": {"status": "failed"}})
                
                error_msg = (
                    f"⚠️ **POST JONATISHDA XATO!**\n\n"
                    f"Kanal: `{p['target']}`\n"
                    f"Vaqt: `{p['time']}`\n"
                    f"Sabab: `{str(e)}`"
                )
                
                # Xabarni barcha adminlarga tarqatish
                for admin in ADMINS:
                    try:
                        await bot.send_message(chat_id=admin, text=error_msg)
                    except Exception as admin_err:
                        # Agar admin botni bloklagan bo'lsa, jimgina o'tib ketadi
                        logging.warning(f"Admin {admin} ga xabar yetib bormadi: {admin_err}")
                
    except Exception as main_e:
        logging.error(f"Taymer umumiy xatosi: {main_e}")

# ==================== ISHGA TUSHIRISH ====================
async def main():
    dp.include_router(router)
    
    # Taymerni har 1 daqiqada ishlashga sozlaymiz
    scheduler.add_job(check_and_post, "interval", minutes=1)
    scheduler.start()
    
    logging.info("🟢 O'q o'tmas bot ishga tushdi...")
    
    # Drop pending updates - bot o'chib qolganda kelgan xabarlarni miyasidan chiqarib tashlaydi
    await bot.delete_webhook(drop_pending_updates=True) 
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("🔴 Bot to'xtatildi")
