import asyncio
from typing import List, Optional, Dict, Any

from src.core.models import GiftData, GiftCriteria, PurchaseDecision
from src.core.constants import Limits
from src.core.exceptions import InsufficientBalanceError
from src.services.buyer import GiftBuyer
from src.telegram.notification_bot import NotificationBot
from src.utils import logger


class PurchaseManager:
    
    def __init__(self, buyer: GiftBuyer, criteria: List[GiftCriteria], 
                 notification_bot: Optional[NotificationBot] = None,
                 purchase_non_limited: bool = False):
        self.buyer = buyer
        self.criteria = criteria
        self.notification_bot = notification_bot
        self.purchase_non_limited = purchase_non_limited
        self._processed_gifts: set[int] = set()
        self._purchase_lock = asyncio.Lock()
    

    def evaluate_gift(self, gift_data: GiftData) -> PurchaseDecision:
        if gift_data.is_sold_out:
            return PurchaseDecision(should_buy=False, reason="Распродан")
        
        if not gift_data.is_limited and not self.purchase_non_limited:
            return PurchaseDecision(should_buy=False, reason="Не лимитированный")
        
        price = gift_data.price
        supply = gift_data.total_amount
        
        for criteria in self.criteria:
            if criteria.matches(supply, price):
                current_balance = self.buyer.balance
                max_affordable = current_balance // price if price > 0 else 0
                
                if max_affordable == 0:
                    return PurchaseDecision(
                        should_buy=False, 
                        reason=f"Недостаточно Stars: баланс {current_balance}, цена {price}"
                    )
                
                actual_quantity = min(criteria.quantity, max_affordable)
                
                return PurchaseDecision(
                    should_buy=True,
                    quantity=actual_quantity,
                    matched_criteria=criteria,
                    reason=f"Совпадение: supply={supply}, price={price}, купим {actual_quantity} шт."
                )
        
        return PurchaseDecision(
            should_buy=False, 
            reason=f"Не подходит под критерии: supply={supply}, price={price}"
        )
    

    async def process_gift(self, gift_data: GiftData) -> None:
        gift_id = gift_data.id
        
        if gift_id in self._processed_gifts:
            return
        
        async with self._purchase_lock:
            if gift_id in self._processed_gifts:
                return
            
            self._processed_gifts.add(gift_id)
            
            if self.notification_bot:
                await self.notification_bot.send_gift_found(gift_data)
            
            decision = self.evaluate_gift(gift_data)
            
            if not decision.should_buy:
                logger.info(f"Подарок {gift_id} пропущен: {decision.reason}")
                return
            
            total_cost = gift_data.price * decision.quantity
            
            logger.info(
                f"Покупаем подарок {gift_id}: {decision.quantity} шт. "
                f"по {gift_data.price} Stars"
            )
            
            try:
                success, message = await self.buyer.buy_gift(gift_id, decision.quantity)
                
                if success:
                    logger.success(f"[DONE] Успешная покупка подарка {gift_id}: {message}")
                    if self.notification_bot:
                        await self.notification_bot.send_purchase_success(
                            gift_id, decision.quantity, total_cost
                        )
                    self.buyer._stars_balance -= total_cost
                else:
                    logger.error(f"Ошибка покупки подарка {gift_id}: {message}")
                    if self.notification_bot:
                        await self.notification_bot.send_purchase_error(gift_id, message)
                        
            except InsufficientBalanceError:
                if self.notification_bot:
                    current_balance = await self.buyer.get_balance()
                    await self.notification_bot.send_low_balance_warning(
                        current_balance, total_cost
                    )
    

    def cleanup_old_gifts(self, keep_last: int = Limits.MAX_PROCESSED_GIFTS) -> None:
        if len(self._processed_gifts) > keep_last:
            recent_gifts = list(self._processed_gifts)[-keep_last:]
            self._processed_gifts = set(recent_gifts)
            logger.debug(f"Очищена память processed_gifts: {len(self._processed_gifts)}")
    

    @property
    def processed_count(self) -> int:
        return len(self._processed_gifts)
    