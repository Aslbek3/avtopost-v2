import asyncio
import logging
import traceback
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
import strings
from handlers.admin import admin_router
from handlers.settings import settings_router

logging.basicConfig(level=logging.INFO)

async def send_scheduled_posts(bot: Bot):
    # VAQT FORMATI (DD.MM HH:MM)
    hozirgi_vaqt = datetime.now(config.TIMEZONE).strftime("%d.%m %H:%M")
    
    all_pending = await db.get_all_pending_posts()
    
    for post in all_pending:
        if post['send_time'] == hozirgi_vaqt:
            uid = post['owner_id']
            user_channels = await db.get_channels(uid)
            target_ids = post['target_channels']
            
            # Post yuborilganini tekshirish uchun o'zgaruvchi
            muvaffaqiyatli = False 
            
            for ch_id in target_ids:
                kanal_info = next((c for c in user_channels if c['channel_id'] == ch_id), None)
                
                if kanal_info:
                    bot_link = kanal_info['bot_username']
                    msg_text = post['text'].replace("[bot nomi]", bot_link).replace("[BOT_NOMI]", bot_link)
                    
                    try:
                        if post.get('photo_id'):
                            await bot.send_photo(chat_id=ch_id, photo=post['photo_id'], caption=msg_text)
                        else:
                            await bot.send_message(chat_id=ch_id, text=msg_text)
                        
                        muvaffaqiyatli = True # Hech bo'lmasa 1 ta kanalga borsa, true bo'ladi
                        await asyncio.sleep(0.1) 
                    except Exception as e:
                        logging.error(f"Yuborishda xato ({ch_id}): {e}")

            # KANALLARGA YUBORIB BO'LGANDAN SO'NG, NAVBAT KANALIDAN O'CHIRISH
            if post.get('queue_msg_id'):
                try:
                    await bot.delete_message(chat_id=config.QUEUE_CHANNEL_ID, message_id=post['queue_msg_id'])
                except Exception as e:
                    logging.error(f"Navbat kanalidan o'chirishda xato: {e}")

            # Agar yuborish o'xshasa sent, o'xshamasa failed statusi beriladi
            if muvaffaqiyatli:
                await db.mark_post_sent(post['_id'])
            else:
                # Baza faylidagi statistika to'g'ri ishlashi uchun xatolikni yozamiz
                await db.db.posts.update_one({"_id": post['_id']}, {"$set": {"status": "failed"}})

async def setup_error_handler(dp: Dispatcher, bot: Bot):
    @dp.error()
    async def error_handler(event: ErrorEvent):
        logging.error(f"XATOLIK: {traceback.format_exc()}")
        chat_id = None
        if event.update.message: 
            chat_id = event.update.message.chat.id
        elif event.update.callback_query: 
            chat_id = event.update.callback_query.message.chat.id
            
        if chat_id:
            try:
                err_msg = f"{strings.USER_ERROR_MSG}\n\n⚠️ *Texnik xato:* `{str(event.exception)[:100]}`"
                await bot.send_message(chat_id, err_msg, parse_mode="Markdown")
            except: 
                pass

async def main():
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(admin_router)
    dp.include_router(settings_router) 
    
    await db.check_db_connection()
    await setup_error_handler(dp, bot)

    scheduler = AsyncIOScheduler(timezone=config.TIMEZONE)
    scheduler.add_job(send_scheduled_posts, "interval", minutes=1, args=[bot])
    scheduler.start()

    print("🚀 Bot ishga tushdi...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
