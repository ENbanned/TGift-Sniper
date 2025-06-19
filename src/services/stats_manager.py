import time
from typing import List, Dict, Any

from src.core.models import MonitorStats
from src.core.constants import TimeConstants
from src.services.hunter import GiftHunter
from src.services.buyer import GiftBuyer
from src.utils import logger


class StatsManager:
    
    def __init__(self):
        self._total_checks = 0
        self._last_check_count = 0
        self._last_check_time = time.time()
        self._degradation_check_time = time.time()
        self._degradation_check_count = 0
    

    def increment_checks(self) -> None:
        self._total_checks += 1
        self._degradation_check_count += 1
    

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
    

    def check_degradation(self, min_checks: int = 100) -> bool:
        current_time = time.time()
        time_elapsed = current_time - self._degradation_check_time
        
        if time_elapsed < TimeConstants.DEGRADATION_CHECK_INTERVAL:
            return False
        
        if time_elapsed > 0:
            checks_per_minute = (self._degradation_check_count / time_elapsed) * 60
        else:
            checks_per_minute = 0
        
        has_degradation = checks_per_minute < 10 and self._total_checks > 100
        
        self._degradation_check_time = current_time
        self._degradation_check_count = 0
        
        return has_degradation
    

    def collect_monitor_stats(self, is_running: bool, buyer: GiftBuyer, 
                            hunters: List[GiftHunter], processed_gifts: int) -> MonitorStats:
        hunter_stats = [hunter.get_stats() for hunter in hunters]
        
        return MonitorStats(
            running=is_running,
            processed_gifts=processed_gifts,
            buyer_balance=buyer.balance,
            total_checks=self._total_checks,
            hunters=hunter_stats
        )
    