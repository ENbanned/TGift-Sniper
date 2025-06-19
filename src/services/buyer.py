import asyncio
from typing import Tuple

from pyrogram import Client
from pyrogram.errors import RPCError, FloodWait

from src.utils import logger
from src.core.constants import TimeConstants, TelegramConstants
from src.core.exceptions import PurchaseError, InsufficientBalanceError


class GiftBuyer:
    
    def __init__(self, client: Client, target_username: str):
        self.client = client
        self.target_username = target_username.lstrip('@')
        self._stars_balance: int = 0
    
    
    async def initialize(self) -> bool:
        try:
            self._stars_balance = await self.client.get_stars_balance()
            logger.info(
                f"[Buyer] Инициализирован. Цель: {self.target_username}, "
                f"Баланс: {self._stars_balance} Stars"
            )
            return True
        except Exception as e:
            logger.error(f"[Buyer] Ошибка инициализации: {e}")
            return False
    

    async def get_balance(self) -> int:
        try:
            self._stars_balance = await self.client.get_stars_balance()
            return self._stars_balance
        except Exception as e:
            logger.error(f"[Buyer] Ошибка получения баланса: {e}")
            return 0
    

    async def buy_gift(self, gift_id: int, quantity: int = 1) -> Tuple[bool, str]:
        if not self.target_username:
            return False, "Цель не инициализирована"
        
        success_count = 0
        last_error = ""
        
        for i in range(quantity):
            try:
                await self.client.send_gift(
                    chat_id=self.target_username,
                    gift_id=gift_id,
                    hide_my_name=True
                )
                success_count += 1
                logger.success(
                    f"[Buyer] Подарок {gift_id} отправлен ({i+1}/{quantity})"
                )
                
                if i < quantity - 1:
                    await asyncio.sleep(TimeConstants.PURCHASE_DELAY)
                    
            except FloodWait as e:
                logger.warning(f"[Buyer] FloodWait: {e.value} сек")
                await asyncio.sleep(e.value)
                try:
                    await self.client.send_gift(
                        chat_id=self.target_username,
                        gift_id=gift_id,
                        hide_my_name=True
                    )
                    success_count += 1
                except Exception as retry_error:
                    last_error = str(retry_error)
                    logger.error(f"[Buyer] Повторная ошибка: {retry_error}")
                    
            except RPCError as e:
                last_error = str(e)
                logger.error(f"[Buyer] RPC ошибка при покупке: {e}")
                
                if TelegramConstants.ERROR_INSUFFICIENT_BALANCE in str(e):
                    logger.error("[Buyer] Недостаточно Stars!")
                    raise InsufficientBalanceError("Недостаточно Stars")
                elif TelegramConstants.ERROR_GIFT_SOLD_OUT in str(e):
                    logger.error("[Buyer] Подарок распродан!")
                    break
                    
            except Exception as e:
                last_error = str(e)
                logger.error(f"[Buyer] Неожиданная ошибка: {e}")
        
        await self.get_balance()
        
        if success_count > 0:
            return True, f"Куплено {success_count}/{quantity}"
        else:
            return False, last_error
    

    async def can_afford(self, price: int, quantity: int) -> bool:
        total_cost = price * quantity
        current_balance = await self.get_balance()
        return current_balance >= total_cost
    

    @property
    def balance(self) -> int:
        return self._stars_balance
    