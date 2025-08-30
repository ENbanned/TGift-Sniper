import asyncio
from typing import List, Optional

from src.core.models import GiftData, GiftCriteria, PurchaseDecision
from src.core.constants import Limits
from src.services.buyer import GiftBuyer
from src.telegram.notification_bot import NotificationBot
from src.utils import logger


class PurchaseManager:
    
    def __init__(self, buyers: List[GiftBuyer], criteria: List[GiftCriteria], 
                 notification_bot: Optional[NotificationBot] = None,
                 purchase_non_limited: bool = False,
                 fallback_purchase: bool = False):
        self.buyers = buyers
        self.criteria = criteria
        self.notification_bot = notification_bot
        self.purchase_non_limited = purchase_non_limited
        self.fallback_purchase = fallback_purchase
        self._processed_gifts: set[int] = set()
    

    def evaluate_gift(self, gift_data: GiftData) -> PurchaseDecision:
        if gift_data.is_sold_out:
            return PurchaseDecision(should_buy=False, reason="Распродан")
        
        if not gift_data.is_limited and not self.purchase_non_limited:
            return PurchaseDecision(should_buy=False, reason="Не лимитированный")
        
        price = gift_data.price
        supply = gift_data.total_amount
        
        for criteria in self.criteria:
            if criteria.matches(supply, price):
                return PurchaseDecision(
                    should_buy=True,
                    quantity=criteria.quantity,
                    matched_criteria=criteria,
                    reason=f"Совпадение: supply={supply}, price={price}"
                )
        
        return PurchaseDecision(
            should_buy=False, 
            reason=f"Не подходит под критерии: supply={supply}, price={price}"
        )
    

    async def process_gifts(self, gifts: List[GiftData]) -> None:
        new_gifts = [g for g in gifts if g.id not in self._processed_gifts]
        if not new_gifts:
            return
            
        
        for gift in new_gifts:
            self._processed_gifts.add(gift.id)
            if self.notification_bot:
                await self.notification_bot.send_gift_found(gift)
        
        new_gifts.sort(key=lambda g: g.total_amount)
        
        for gift in new_gifts:
            decision = self.evaluate_gift(gift)
            if decision.should_buy:
                await self._buy_gift_with_all_buyers(gift, decision)
        
        if self.fallback_purchase:
            for gift in new_gifts:
                if gift.is_sold_out:
                    continue
                    
                decision = self.evaluate_gift(gift)
                if decision.should_buy:
                    continue
                
                total_balance = sum(buyer.balance for buyer in self.buyers)
                max_affordable_total = total_balance // gift.price if gift.price > 0 else 0
                
                if max_affordable_total > 0:
                    target_quantity = self.criteria[0].quantity if self.criteria else 9999
                    
                    fallback_decision = PurchaseDecision(
                        should_buy=True,
                        quantity=target_quantity,
                        reason=f"Fallback покупка: максимум {target_quantity} шт."
                    )
                    
                    success = await self._buy_gift_with_all_buyers(gift, fallback_decision)
                    if success:
                        logger.info(f"Fallback покупка успешна для подарка {gift.id}")
    

    async def _buy_gift_with_all_buyers(self, gift: GiftData, decision: PurchaseDecision) -> bool:        
        logger.info(
            f"Покупаем подарок {gift.id}: до {decision.quantity} шт. "
            f"по {gift.price} Stars с {len(self.buyers)} аккаунтов"
        )
        
        tasks = []
        for buyer in self.buyers:
            max_affordable = buyer.balance // gift.price if gift.price > 0 else 0
            if max_affordable > 0:
                quantity_to_buy = min(decision.quantity, max_affordable)
                task = self._buy_with_buyer(buyer, gift, quantity_to_buy)
                tasks.append(task)
        
        if not tasks:
            logger.error(f"Ни один покупатель не может позволить подарок {gift.id}")
            return False
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        total_bought = 0
        total_spent = 0
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(str(result))
            elif result[0]:
                try:
                    bought_count = int(result[1].split('/')[0].split()[1])
                except:
                    bought_count = 0
                total_bought += bought_count
                total_spent += bought_count * gift.price
        
        if total_bought > 0:
            logger.success(f"[DONE] Всего куплено {total_bought} шт. подарка {gift.id}")
            if self.notification_bot:
                await self.notification_bot.send_purchase_success(
                    gift.id, total_bought, total_spent
                )
            return True
        else:
            error_msg = "; ".join(set(errors)) if errors else "Неизвестная ошибка"
            logger.error(f"Не удалось купить подарок {gift.id}: {error_msg}")
            if self.notification_bot:
                await self.notification_bot.send_purchase_error(gift.id, error_msg)
            return False
    

    async def _buy_with_buyer(self, buyer: GiftBuyer, gift: GiftData, quantity: int) -> tuple:
        try:
            success, message = await buyer.buy_gift(gift.id, quantity)
            return (success, message)
        except Exception as e:
            logger.error(f"[Buyer-{buyer.buyer_id}] Ошибка покупки: {e}")
            return (False, str(e))
    

    def cleanup_old_gifts(self, keep_last: int = Limits.MAX_PROCESSED_GIFTS) -> None:
        if len(self._processed_gifts) > keep_last:
            recent_gifts = list(self._processed_gifts)[-keep_last:]
            self._processed_gifts = set(recent_gifts)
            logger.debug(f"Очищена память processed_gifts: {len(self._processed_gifts)}")
    

    @property
    def processed_count(self) -> int:
        return len(self._processed_gifts)
    