import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any

from pyrogram import Client

from src.utils import logger
from src.utils.credentials_manager import CredentialsManager


class ClientManager:
    
    def __init__(self, sessions_dir: Path):
        self.sessions_dir = sessions_dir
        self.credentials_manager = CredentialsManager(sessions_dir)
    

    def create_client(self, session_name: str) -> Optional[Client]:
        credentials = self.credentials_manager.load(session_name)
        if not credentials:
            logger.error(f"Не найдены credentials для {session_name}")
            return None
        
        return Client(
            name=str(self.sessions_dir / session_name),
            api_id=credentials['api_id'],
            api_hash=credentials['api_hash']
        )
    

    async def create_and_start_clients(self, buyer_session: str, 
                                     hunter_sessions: List[str]) -> Dict[str, Any]:
        result = {
            'buyer': None,
            'hunters': [],
            'success': False
        }
        
        buyer_client = self.create_client(buyer_session)
        if not buyer_client:
            return result
        
        try:
            await buyer_client.start()
            buyer_info = await buyer_client.get_me()
            logger.info(
                f"Покупатель: {buyer_info.first_name} "
                f"(@{buyer_info.username or 'no_username'})"
            )
            result['buyer'] = buyer_client
        except Exception as e:
            logger.error(f"Ошибка запуска покупателя: {e}")
            return result
        
        for idx, hunter_name in enumerate(hunter_sessions):
            await asyncio.sleep(1)

            hunter_client = self.create_client(hunter_name)
            if not hunter_client:
                continue
            
            try:
                await hunter_client.start()
                hunter_info = await hunter_client.get_me()
                logger.info(
                    f"Охотник #{idx+1}: {hunter_info.first_name} "
                    f"(@{hunter_info.username or 'no_username'})"
                )
                result['hunters'].append(hunter_client)
            except Exception as e:
                logger.error(f"Ошибка запуска охотника {hunter_name}: {e}")
        
        result['success'] = result['buyer'] is not None and len(result['hunters']) > 0
        return result
    

    async def stop_all(self, buyer: Optional[Client], hunters: List[Client]) -> None:
        if buyer:
            await buyer.stop()
        
        for client in hunters:
            await client.stop()
