from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime


@dataclass
class GiftCriteria:
    min_supply: int
    max_supply: int
    min_price: int
    max_price: int
    quantity: int

    def matches(self, supply: int, price: int) -> bool:
        return (self.min_supply <= supply <= self.max_supply and 
                self.min_price <= price <= self.max_price)


@dataclass
class PurchaseDecision:
    should_buy: bool
    quantity: int = 0
    matched_criteria: Optional[GiftCriteria] = None
    reason: str = ""


@dataclass
class GiftData:
    id: int
    price: int
    is_limited: bool
    is_sold_out: bool
    total_amount: int
    available_amount: int
    can_upgrade: bool
    
    @classmethod
    def from_telegram_gift(cls, gift: Any) -> 'GiftData':
        return cls(
            id=gift.id,
            price=gift.price,
            is_limited=gift.is_limited,
            is_sold_out=gift.is_sold_out,
            total_amount=gift.total_amount,
            available_amount=gift.available_amount,
            can_upgrade=gift.can_upgrade
        )


@dataclass
class HunterStats:
    hunter_id: int
    last_check: Optional[datetime]
    check_count: int
    known_gifts: int


@dataclass
class MonitorStats:
    running: bool
    processed_gifts: int
    buyer_balance: int
    total_checks: int
    hunters: list[HunterStats]
    