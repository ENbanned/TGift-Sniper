import asyncio
import time
import random
import gc
from typing import List, Optional

from pyrogram import Client
from pyrogram.errors import FloodWait

from src.core.models import GiftCriteria
from src.core.constants import TimeConstants, Limits
from src.services.buyer import GiftBuyer
from src.services.hunter import GiftHunter
from src.services.purchase_manager import PurchaseManager
from src.services.stats_manager import StatsManager
from src.telegram.notification_bot import NotificationBot
from src.utils import logger
import config


class GiftMonitor:
    
    def __init__(self, buyer_client: Client, hunter_clients: List[Client], 
                 criteria: List[GiftCriteria], notification_bot: Optional[NotificationBot] = None):
        self.buyer = GiftBuyer(buyer_client, config.TARGET_USERNAME)
        self.hunters = [GiftHunter(client, idx) for idx, client in enumerate(hunter_clients)]
        
        self.purchase_manager = PurchaseManager(
            buyer=self.buyer,
            criteria=criteria,
            notification_bot=notification_bot,
            purchase_non_limited=config.PURCHASE_NON_LIMITED_GIFTS
        )
        self.stats_manager = StatsManager()
        
        self.notification_bot = notification_bot
        
        self._running = False
        self._hunter_tasks: List[asyncio.Task] = []
    

    async def initialize(self) -> bool:
        if not await self.buyer.initialize():
            logger.error("Не удалось инициализировать покупателя")
            return False
        
        balance = await self.buyer.get_balance()
        if balance < config.MIN_STARS_BALANCE:
            logger.error(f"Недостаточный баланс: {balance} < {config.MIN_STARS_BALANCE}")
            if self.notification_bot:
                await self.notification_bot.send_low_balance_warning(
                    balance, config.MIN_STARS_BALANCE
                )
            return False
        
        logger.info(
            f"Монитор инициализирован. Охотников: {len(self.hunters)}, "
            f"Критериев: {len(self.purchase_manager.criteria)}"
        )
        return True
    

    async def _hunter_loop(self, hunter: GiftHunter) -> None:
        await asyncio.sleep(
            random.uniform(0, TimeConstants.HUNTER_INITIAL_DELAY_MAX * len(self.hunters))
        )
        
        consecutive_errors = 0
        consecutive_successes = 0
        base_interval = config.BASE_CHECK_INTERVAL
        current_interval = base_interval
        
        while self._running:
            try:
                start_time = time.time()
                
                new_gifts = await hunter.check_gifts()
                
                if new_gifts:
                    tasks = [
                        self.purchase_manager.process_gift(gift_data) 
                        for gift_data in new_gifts
                    ]
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                self.stats_manager.increment_checks()
                consecutive_errors = 0
                consecutive_successes += 1
                
                if (consecutive_successes > Limits.CONSECUTIVE_SUCCESS_THRESHOLD and 
                    current_interval > base_interval):
                    current_interval = max(
                        base_interval, 
                        current_interval * TimeConstants.INTERVAL_RECOVERY_FACTOR
                    )
                    logger.debug(
                        f"[Hunter-{hunter.hunter_id}] Восстановление интервала: "
                        f"{current_interval:.1f}с"
                    )
                
                if config.ADAPTIVE_INTERVALS:
                    check_duration = time.time() - start_time
                    if check_duration < TimeConstants.CHECK_DURATION_FAST:
                        current_interval = max(
                            config.MIN_CHECK_INTERVAL, 
                            current_interval * TimeConstants.INTERVAL_DECREASE_FACTOR
                        )
                    elif check_duration > TimeConstants.CHECK_DURATION_SLOW:
                        current_interval = min(
                            config.MAX_CHECK_INTERVAL, 
                            current_interval * TimeConstants.INTERVAL_INCREASE_FACTOR
                        )
                else:
                    current_interval = base_interval
                
                sleep_time = max(Limits.MIN_INTERVAL_DELAY, current_interval - check_duration)
                
                if config.RANDOM_DELAY_MAX > 0:
                    sleep_time += random.uniform(0, config.RANDOM_DELAY_MAX)
                
            except FloodWait as e:
                logger.warning(f"[Hunter-{hunter.hunter_id}] FloodWait: {e.value}с")
                sleep_time = e.value
                current_interval = min(
                    config.MAX_CHECK_INTERVAL, 
                    current_interval * TimeConstants.FLOOD_WAIT_FACTOR
                )
                consecutive_successes = 0
                
            except Exception as e:
                consecutive_errors += 1
                consecutive_successes = 0
                logger.error(f"[Hunter-{hunter.hunter_id}] Ошибка: {e}")
                
                if consecutive_errors > Limits.CONSECUTIVE_ERROR_THRESHOLD:
                    current_interval = min(
                        config.MAX_CHECK_INTERVAL, 
                        current_interval * TimeConstants.ERROR_INTERVAL_FACTOR
                    )
                
                sleep_time = current_interval
            
            await asyncio.sleep(sleep_time)
    

    async def _memory_cleanup_loop(self) -> None:
        while self._running:
            await asyncio.sleep(TimeConstants.MEMORY_CLEANUP_INTERVAL)
            
            self.stats_manager.log_performance(self.purchase_manager.processed_count)
            
            self.purchase_manager.cleanup_old_gifts()
            
            gc.collect()
    

    async def _check_degradation(self) -> None:
        while self._running:
            await asyncio.sleep(60)
            
            if self.stats_manager.check_degradation(TimeConstants.DEGRADATION_MIN_CHECKS):
                logger.warning("Обнаружена деградация производительности")
                
                for task in self._hunter_tasks:
                    task.cancel()
                
                await asyncio.gather(*self._hunter_tasks, return_exceptions=True)
                self._hunter_tasks.clear()
                
                await asyncio.sleep(TimeConstants.POST_ERROR_DELAY)
                
                for hunter in self.hunters:
                    task = asyncio.create_task(self._hunter_loop(hunter))
                    self._hunter_tasks.append(task)
                
                logger.info("Охотники перезапущены")
    

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
        asyncio.create_task(self._check_degradation())
        
        if self.notification_bot:
            balance = await self.buyer.get_balance()
            await self.notification_bot.send_startup_message(
                accounts_count=len(self.hunters) + 1,
                balance=balance
            )
        
        logger.info(f"[DONE] Мониторинг запущен с {len(self.hunters)} охотниками")
    

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
            buyer=self.buyer,
            hunters=self.hunters,
            processed_gifts=self.purchase_manager.processed_count
        )
        return monitor_stats.__dict__
    