import asyncio
import json
from pathlib import Path
from typing import Optional
from datetime import datetime

from pyrogram import Client
from pyrogram.errors import RPCError

from src.utils import logger
from src.core.constants import TimeConstants
from src.core.models import GiftData
from src.telegram.bot_commands import BotCommands


class NotificationBot:
    
    def __init__(self, bot_session: str, chat_id: int, sessions_dir: str = "sessions"):
        self.bot_session = bot_session
        self.chat_id = chat_id
        self.sessions_dir = Path(sessions_dir)
        self.bot: Optional[Client] = None
        self._initialized = False
        self._queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._get_monitor_stats = lambda: {}


    def _load_bot_credentials(self) -> Optional[dict]:
        credentials_file = self.sessions_dir / ".credentials.json"
        
        if not credentials_file.exists():
            return None
        
        try:
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)
                bot_creds = credentials.get(self.bot_session)
                
                if bot_creds and bot_creds.get('is_bot'):
                    return bot_creds
                return None
        except Exception:
            return None
    

    async def initialize(self) -> bool:
        if not self.bot_session or not self.chat_id:
            logger.warning("Бот для уведомлений не настроен")
            return False
        
        session_file = self.sessions_dir / f"{self.bot_session}.session"
        if not session_file.exists():
            logger.warning(f"Сессия бота '{self.bot_session}' не найдена")
            return False
        
        bot_creds = self._load_bot_credentials()
        if not bot_creds:
            logger.warning(f"Не найдены credentials для бота '{self.bot_session}'")
            return False
        
        try:
            self.bot = Client(
                name=str(session_file.with_suffix('')),
                api_id=bot_creds['api_id'],
                api_hash=bot_creds['api_hash'],
                bot_token=bot_creds['bot_token']
            )
            
            await self.bot.start()
            
            me = await self.bot.get_me()
            logger.info(f"Бот уведомлений активирован: {me.first_name} (@{me.username})")
            
            self._initialized = True

            if self._initialized:
                self.commands = BotCommands(self.bot, self._get_monitor_stats)
                self.commands.setup_handlers()
                self._commands = self.commands
            
            self._worker_task = asyncio.create_task(self._process_queue())
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации бота: {e}")
            return False
    

    async def _process_queue(self) -> None:
        while self._initialized:
            try:
                message = await self._queue.get()
                await self._send_message(message)
                await asyncio.sleep(TimeConstants.QUEUE_PROCESS_DELAY)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Ошибка в обработчике очереди: {e}")
    

    async def _send_message(self, text: str) -> None:
        if not self._initialized or not self.bot:
            return
        
        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text
            )
        except RPCError as e:
            logger.error(f"Ошибка отправки уведомления: {e}")
    

    async def send_notification(self, text: str, priority: bool = False) -> None:
        if not self._initialized:
            return
        
        if priority:
            asyncio.create_task(self._send_message(text))
        else:
            await self._queue.put(text)
    

    async def send_startup_message(self, accounts_count: int, balance: int) -> None:
        message = (
            "🚀 **Gift Sniper запущен**\n\n"
            f"📊 Аккаунтов: {accounts_count}\n"
            f"💰 Баланс Stars: {balance:,}\n"
            f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await self.send_notification(message, priority=True)
    

    async def send_gift_found(self, gift_data: GiftData) -> None:
        message = (
            "🎁 **Найден лимитированный подарок**\n\n"
            f"🏷 ID: `{gift_data.id}`\n"
            f"💎 Цена: {gift_data.price} Stars\n"
            f"📦 Количество: {gift_data.total_amount:,}\n"
            f"🔄 Улучшаемый: {'✅' if gift_data.can_upgrade else '❌'}"
        )
        await self.send_notification(message)
    

    async def send_purchase_success(self, gift_id: int, quantity: int, total_spent: int) -> None:
        message = (
            "✅ **Покупка успешна**\n\n"
            f"🎁 Подарок ID: `{gift_id}`\n"
            f"📦 Куплено: {quantity} шт.\n"
            f"💸 Потрачено: {total_spent:,} Stars"
        )
        await self.send_notification(message, priority=True)
    

    async def send_purchase_error(self, gift_id: int, error: str) -> None:
        message = (
            "❌ **Ошибка покупки**\n\n"
            f"🎁 Подарок ID: `{gift_id}`\n"
            f"⚠️ Ошибка: {error}"
        )
        await self.send_notification(message, priority=True)
    

    async def send_low_balance_warning(self, current: int, required: int) -> None:
        message = (
            "⚠️ **Низкий баланс Stars**\n\n"
            f"💰 Текущий: {current:,}\n"
            f"💸 Требуется: {required:,}\n"
            f"❗ Пополните баланс для продолжения работы"
        )
        await self.send_notification(message, priority=True)


    def set_monitor_stats_callback(self, callback):
        self._get_monitor_stats = callback

        if hasattr(self, '_commands'):
            self._commands.get_monitor_stats = callback
    

    async def cleanup(self) -> None:
        self._initialized = False
        
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        
        if self.bot:
            await self.bot.stop()
