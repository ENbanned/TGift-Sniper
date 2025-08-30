import asyncio
import time
import random
import gc
from typing import List, Optional

from pyrogram import Client
from pyrogram.errors import FloodWait

from src.core.models import GiftCriteria
from src.core.constants import TimeConstants
from src.services.buyer import GiftBuyer
from src.services.hunter import GiftHunter
from src.services.purchase_manager import PurchaseManager
from src.services.stats_manager import StatsManager
from src.telegram.notification_bot import NotificationBot
from src.utils import logger
import config


class GiftMonitor:
    
    def __init__(self, buyer_clients: List[Client], hunter_clients: List[Client], 
                 criteria: List[GiftCriteria], notification_bot: Optional[NotificationBot] = None):
        
        self.buyers = [GiftBuyer(client, config.TARGET_USERNAMES, idx) 
                      for idx, client in enumerate(buyer_clients)]
        
        self.hunters = [GiftHunter(client, idx) for idx, client in enumerate(hunter_clients)]
        
        self.purchase_manager = PurchaseManager(
            buyers=self.buyers,
            criteria=criteria,
            notification_bot=notification_bot,
            purchase_non_limited=config.PURCHASE_NON_LIMITED_GIFTS,
            fallback_purchase=config.FALLBACK_PURCHASE
        )
        self.stats_manager = StatsManager()
        
        self.notification_bot = notification_bot
        
        self._running = False
        self._buying_in_progress = False
        self._hunter_tasks: List[asyncio.Task] = []
    

    async def initialize(self) -> bool:
        for buyer in self.buyers:
            if not await buyer.initialize():
                logger.error(f"Не удалось инициализировать покупателя {buyer.buyer_id}")
        
        total_balance = sum(buyer.balance for buyer in self.buyers)
        if total_balance < config.MIN_STARS_BALANCE:
            logger.error(f"Недостаточный общий баланс: {total_balance} < {config.MIN_STARS_BALANCE}")
            if self.notification_bot:
                await self.notification_bot.send_low_balance_warning(
                    total_balance, config.MIN_STARS_BALANCE
                )
            return False
        
        unique_clients = set()
        for buyer in self.buyers:
            unique_clients.add(id(buyer.client))
        for hunter in self.hunters:
            unique_clients.add(id(hunter.client))
        
        self.unique_accounts_count = len(unique_clients)
        
        logger.info(
            f"Монитор инициализирован. Уникальных аккаунтов: {self.unique_accounts_count}, "
            f"Покупателей: {len(self.buyers)}, Охотников: {len(self.hunters)}, "
            f"Критериев: {len(self.purchase_manager.criteria)}"
        )
        return True
    

    async def _hunter_loop(self, hunter: GiftHunter) -> None:
        await asyncio.sleep(
            random.uniform(0, TimeConstants.HUNTER_INITIAL_DELAY_MAX * len(self.hunters))
        )
        
        consecutive_errors = 0
        check_interval = config.CHECK_INTERVAL
        
        while self._running:
            try:
                start_time = time.time()
                
                new_gifts = await hunter.check_gifts()
                
                if new_gifts:
                    asyncio.create_task(self.purchase_manager.process_gifts(new_gifts))
                
                self.stats_manager.increment_checks()
                consecutive_errors = 0
                
                check_duration = time.time() - start_time
                sleep_time = max(0.1, check_interval - check_duration)
                
                if config.RANDOM_DELAY_MAX > 0:
                    sleep_time += random.uniform(0, config.RANDOM_DELAY_MAX)
                    
            except FloodWait as e:
                logger.warning(f"[Hunter-{hunter.hunter_id}] FloodWait: {e.value}с")
                sleep_time = e.value
                
            except Exception as e:
                consecutive_errors += 1
                logger.error(f"[Hunter-{hunter.hunter_id}] Ошибка: {e}")
                
                if consecutive_errors > 3:
                    sleep_time = check_interval * 2
                else:
                    sleep_time = check_interval
            
            await asyncio.sleep(sleep_time)
    

    async def _memory_cleanup_loop(self) -> None:
        while self._running:
            await asyncio.sleep(60)
            
            self.stats_manager.log_performance(self.purchase_manager.processed_count)
            self.purchase_manager.cleanup_old_gifts()
            gc.collect()
    

    async def start(self) -> None:
        if self._running:
            logger.warning("Монитор уже запущен")
            return
        
        self._running = True
        logger.info("Запуск мониторинга подарков...")
        
        for hunter in self.hunters:
            task = asyncio.create_task(self._hunter_loop(hunter))
            self._hunter_tasks.append(task)
        
        asyncio.create_task(self._memory_cleanup_loop())
        
        if self.notification_bot:
            total_balance = sum(buyer.balance for buyer in self.buyers)
            await self.notification_bot.send_startup_message(
                accounts_count=self.unique_accounts_count,
                balance=total_balance
            )
        
        logger.info(f"[DONE] Мониторинг запущен с {len(self.hunters)} охотниками и {len(self.buyers)} покупателями")
    

    async def stop(self) -> None:
        if not self._running:
            return
        
        logger.info("Остановка мониторинга...")
        self._running = False
        
        for task in self._hunter_tasks:
            task.cancel()
        
        await asyncio.gather(*self._hunter_tasks, return_exceptions=True)
        self._hunter_tasks.clear()
        
        logger.info("[DONE] Мониторинг остановлен")
    

    def get_stats(self) -> dict:
        monitor_stats = self.stats_manager.collect_monitor_stats(
            is_running=self._running,
            buyers=self.buyers,
            hunters=self.hunters,
            processed_gifts=self.purchase_manager.processed_count
        )
        return monitor_stats.__dict__
    