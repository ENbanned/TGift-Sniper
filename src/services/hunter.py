import asyncio
import gc
from typing import List, Optional
from datetime import datetime

from pyrogram import Client
from pyrogram.errors import FloodWait, NetworkMigrate

from src.utils import logger
from src.core.constants import TimeConstants, Limits
from src.core.models import GiftData, HunterStats


class GiftHunter:
    
    def __init__(self, client: Client, hunter_id: int):
        self.client = client
        self.hunter_id = hunter_id
        self._last_check: Optional[datetime] = None
        self._known_gifts: set[int] = set()
        self._check_count: int = 0
    

    async def check_gifts(self) -> List[GiftData]:
        try:
            self._last_check = datetime.now()
            self._check_count += 1

            if self._check_count % Limits.GC_COLLECTION_INTERVAL == 0:
                gc.collect(0)
                
            logger.debug(f"[Hunter-{self.hunter_id}] Проверка #{self._check_count}")
            
            gifts = None
            for attempt in range(2):
                try:
                    gifts = await asyncio.wait_for(
                        self.client.get_available_gifts(),
                        timeout=TimeConstants.GIFT_CHECK_TIMEOUT
                    )
                    break
                except (ConnectionError, OSError, TimeoutError) as e:
                    if attempt == 0:
                        logger.warning(f"[Hunter-{self.hunter_id}] Сетевая ошибка, повторяем...")
                        await asyncio.sleep(1)
                    else:
                        raise
                except NetworkMigrate:
                    logger.info(f"[Hunter-{self.hunter_id}] Network migrate, ждем 5 сек...")
                    await asyncio.sleep(5)
                    if attempt == 0:
                        continue
                    else:
                        raise
            
            if not gifts:
                return []
            
            new_limited_gifts = []
            current_limited_ids = set()
            
            for gift in gifts:
                if not gift.is_limited:
                    continue
                    
                current_limited_ids.add(gift.id)
                
                if gift.id not in self._known_gifts and not gift.is_sold_out:
                    gift_data = GiftData.from_telegram_gift(gift)
                    new_limited_gifts.append(gift_data)
                    self._known_gifts.add(gift.id)
                    
                    logger.info(
                        f"[Hunter-{self.hunter_id}] Новый лимитированный подарок: "
                        f"ID={gift.id}, Цена={gift.price}, Количество={gift.total_amount}"
                    )
            
            self._known_gifts = self._known_gifts.intersection(current_limited_ids)
            
            del gifts
            
            return new_limited_gifts
            
        except FloodWait as e:
            logger.warning(f"[Hunter-{self.hunter_id}] FloodWait: {e.value} сек")
            await asyncio.sleep(e.value)
            return []
        
        except asyncio.TimeoutError:
            logger.warning(f"[Hunter-{self.hunter_id}] Таймаут при получении подарков")
            return []
            
        except Exception as e:
            logger.error(f"[Hunter-{self.hunter_id}] Ошибка проверки подарков: {e}")
            return []
    

    def get_stats(self) -> HunterStats:
        return HunterStats(
            hunter_id=self.hunter_id,
            last_check=self._last_check,
            check_count=self._check_count,
            known_gifts=len(self._known_gifts)
        )
    