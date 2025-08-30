import time
from typing import List, Dict, Any

from src.core.models import MonitorStats
from src.services.hunter import GiftHunter
from src.services.buyer import GiftBuyer
from src.utils import logger


class StatsManager:
    
    def __init__(self):
        self._total_checks = 0
        self._last_check_count = 0
        self._last_check_time = time.time()
    

    def increment_checks(self) -> None:
        self._total_checks += 1
    

    def get_performance_stats(self) -> Dict[str, float]:
        current_time = time.time()
        checks_in_period = self._total_checks - self._last_check_count
        time_elapsed = current_time - self._last_check_time
        
        if time_elapsed > 0:
            checks_per_minute = (checks_in_period / time_elapsed) * 60
        else:
            checks_per_minute = 0
        
        self._last_check_count = self._total_checks
        self._last_check_time = current_time
        
        return {
            'checks_per_minute': checks_per_minute,
            'total_checks': self._total_checks,
            'period_checks': checks_in_period
        }
    

    def log_performance(self, processed_gifts: int) -> None:
        stats = self.get_performance_stats()
        logger.info(
            f"Производительность: {stats['checks_per_minute']:.1f} проверок/мин, "
            f"Обработано подарков: {processed_gifts}"
        )
    

    def collect_monitor_stats(self, is_running: bool, buyers: List[GiftBuyer], 
                            hunters: List[GiftHunter], processed_gifts: int) -> MonitorStats:
        hunter_stats = [hunter.get_stats() for hunter in hunters]
        total_balance = sum(buyer.balance for buyer in buyers)
        
        return MonitorStats(
            running=is_running,
            processed_gifts=processed_gifts,
            buyer_balance=total_balance,
            total_checks=self._total_checks,
            hunters=hunter_stats
        )