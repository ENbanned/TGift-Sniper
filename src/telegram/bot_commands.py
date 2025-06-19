from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message

from src.utils import logger


class BotCommands:
    def __init__(self, bot: Client, monitor_stats_callback: callable):
        self.bot = bot
        self.get_monitor_stats = monitor_stats_callback
        

    def setup_handlers(self):
        
        @self.bot.on_message(filters.command("ping") & filters.private)
        async def ping_command(client: Client, message: Message):
            try:
                stats = self.get_monitor_stats()
                
                uptime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                response = (
                    "🟢 **Gift Sniper активен**\n\n"
                    f"⏰ Время: {uptime}\n"
                    f"🔄 Статус: {'Работает' if stats.get('running', False) else 'Остановлен'}\n"
                    f"💰 Баланс: {stats.get('buyer_balance', 0):,} Stars\n"
                    f"📊 Проверок: {stats.get('total_checks', 0)}\n"
                    f"🎁 Обработано: {stats.get('processed_gifts', 0)}\n"
                    f"🔍 Охотников: {len(stats.get('hunters', []))}"
                )
                
                await message.reply(response)
                logger.info(f"Ping от пользователя {message.from_user.id}")
                
            except Exception as e:
                await message.reply("❌ Ошибка получения статистики")
                logger.error(f"Ошибка ping команды: {e}")
        