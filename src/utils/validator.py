from pathlib import Path
from typing import Any, List, Tuple

from src.core.models import GiftCriteria
from src.core.constants import FileConstants, Limits
from src.utils.credentials_manager import CredentialsManager
from src.utils.logger import logger


class ConfigValidator:
    
    @staticmethod
    def validate_all(config: Any) -> Tuple[bool, List[str]]:
        errors = []
        
        sessions_dir = Path(config.SESSIONS_DIR)
        if not sessions_dir.exists():
            try:
                sessions_dir.mkdir(parents=True)
                logger.info(f"Создана директория: {sessions_dir}")
            except Exception as e:
                errors.append(f"Не удалось создать директорию sessions: {e}")
        
        credentials_manager = CredentialsManager(sessions_dir)
        
        if not credentials_manager.exists():
            errors.append("Не найден файл .credentials.json - запустите auth_module.py")
        else:
            buyer_session = sessions_dir / f"{config.BUYER_SESSION}.session"
            if not buyer_session.exists():
                errors.append(f"Не найдена сессия покупателя: {config.BUYER_SESSION}")
            
            missing_hunters = []
            for hunter_name in config.HUNTER_SESSIONS:
                hunter_session = sessions_dir / f"{hunter_name}.session"
                if not hunter_session.exists():
                    missing_hunters.append(hunter_name)
            
            if missing_hunters:
                errors.append(f"Не найдены сессии охотников: {', '.join(missing_hunters)}")
            
            if len(config.HUNTER_SESSIONS) < config.MIN_HUNTERS_COUNT:
                errors.append(
                    f"Недостаточно охотников: {len(config.HUNTER_SESSIONS)} < "
                    f"{config.MIN_HUNTERS_COUNT}"
                )

        if config.BOT_SESSION:
            bot_session_file = sessions_dir / f"{config.BOT_SESSION}.session"
            if not bot_session_file.exists():
                errors.append(f"Не найдена сессия бота: {config.BOT_SESSION}")
            
            bot_creds = credentials_manager.load(config.BOT_SESSION)
            if bot_creds and not bot_creds.get('is_bot'):
                errors.append(f"Сессия {config.BOT_SESSION} не является ботом")

        if not config.TARGET_USERNAME:
            errors.append("TARGET_USERNAME должен быть указан")
        
        if not config.PURCHASE_CRITERIA:
            errors.append("PURCHASE_CRITERIA не может быть пустым")
        else:
            for idx, criteria in enumerate(config.PURCHASE_CRITERIA):
                if len(criteria) != 5:
                    errors.append(f"Критерий #{idx+1} должен содержать 5 значений")
                    continue
                
                min_supply, max_supply, min_price, max_price, quantity = criteria
                
                if min_supply < 0 or max_supply < min_supply:
                    errors.append(f"Критерий #{idx+1}: неверный диапазон supply")
                
                if min_price < 0 or max_price < min_price:
                    errors.append(f"Критерий #{idx+1}: неверный диапазон цены")
                
                if quantity <= 0:
                    errors.append(f"Критерий #{idx+1}: количество должно быть > 0")

        if config.MIN_STARS_BALANCE < 0:
            errors.append("MIN_STARS_BALANCE не может быть отрицательным")
        
        return len(errors) == 0, errors
    

    @staticmethod
    def parse_criteria(config: Any) -> List[GiftCriteria]:
        criteria_list = []
        
        for min_supply, max_supply, min_price, max_price, quantity in config.PURCHASE_CRITERIA:
            criteria = GiftCriteria(
                min_supply=min_supply,
                max_supply=max_supply,
                min_price=min_price,
                max_price=max_price,
                quantity=quantity
            )
            criteria_list.append(criteria)
        
        return criteria_list
    