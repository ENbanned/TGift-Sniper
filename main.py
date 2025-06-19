import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).parent))

import config
from src.core.constants import AppInfo, FileConstants
from src.services import GiftMonitor
from src.telegram import ClientManager, NotificationBot
from src.utils import logger, setup_logger, ConfigValidator


class GiftSniperApp:
    
    def __init__(self):
        self.monitor: Optional[GiftMonitor] = None
        self.notification_bot: Optional[NotificationBot] = None
        self.client_manager = ClientManager(Path(FileConstants.SESSIONS_DIR))
        self._running = False
        self._clients = {'buyer': None, 'hunters': []}
    

    async def validate_config(self) -> bool:
        is_valid, errors = ConfigValidator.validate_all(config)
        
        if not is_valid:
            logger.error("* Ошибки в конфигурации:")
            for error in errors:
                logger.error(f"   - {error}")
            return False
        
        logger.info("+ Конфигурация валидна")
        return True
    

    async def initialize_bot(self) -> None:
        if config.BOT_SESSION and config.LOG_CHAT_ID:
            self.notification_bot = NotificationBot(
                bot_session=config.BOT_SESSION, 
                chat_id=config.LOG_CHAT_ID,
                sessions_dir=FileConstants.SESSIONS_DIR
            )
            await self.notification_bot.initialize()
        else:
            logger.info("# Бот уведомлений не настроен")
    

    async def start_clients(self) -> bool:
        result = await self.client_manager.create_and_start_clients(
            buyer_session=config.BUYER_SESSION,
            hunter_sessions=config.HUNTER_SESSIONS
        )
        
        if not result['success']:
            logger.error("* Не удалось запустить клиенты")
            return False
        
        self._clients = result
        return True
    

    async def run(self) -> None:
        logger.info(f"^ Запуск {AppInfo.NAME} v{AppInfo.VERSION}...")
        
        if not await self.validate_config():
            return
        
        await self.initialize_bot()
        
        if not await self.start_clients():
            return
        
        criteria = ConfigValidator.parse_criteria(config)
        
        self.monitor = GiftMonitor(
            buyer_client=self._clients['buyer'],
            hunter_clients=self._clients['hunters'],
            criteria=criteria,
            notification_bot=self.notification_bot
        )

        if self.notification_bot:
            self.notification_bot.set_monitor_stats_callback(self.monitor.get_stats)
        
        if not await self.monitor.initialize():
            logger.error("* Не удалось инициализировать монитор")
            await self.cleanup()
            return
        
        self._running = True
        await self.monitor.start()
        
        try:
            while self._running:
                await asyncio.sleep(10)
                
                if config.DEBUG_MODE:
                    stats = self.monitor.get_stats()
                    logger.debug(f":: Статистика: {stats}")
                
        except asyncio.CancelledError:
            logger.info("** Получен сигнал остановки")
        
        finally:
            await self.cleanup()
    

    async def cleanup(self) -> None:
        logger.info("<> Очистка ресурсов...")
        
        if self.monitor:
            await self.monitor.stop()
        
        if self.notification_bot:
            await self.notification_bot.cleanup()
        
        await self.client_manager.stop_all(
            self._clients['buyer'], 
            self._clients['hunters']
        )
        
        logger.info("✓ Завершение работы")
    

    def handle_signal(self, signum, frame) -> None:
        logger.info(f"** Получен сигнал {signum}")
        self._running = False


async def main():
    setup_logger(debug=config.DEBUG_MODE)
    
    app = GiftSniperApp()
    
    signal.signal(signal.SIGINT, app.handle_signal)
    signal.signal(signal.SIGTERM, app.handle_signal)
    
    try:
        await app.run()
    except Exception as e:
        logger.error(f"() Критическая ошибка: {e}")
        if config.DEBUG_MODE:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        print("* Требуется Python 3.10 или выше!")
        sys.exit(1)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n[] Остановлено пользователем")
    except Exception as e:
        print(f"\n*** Фатальная ошибка: {e}")
        sys.exit(1)
