#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

from pyrogram import Client

sys.path.append(str(Path(__file__).parent))

from src.utils import logger, setup_logger
from src.utils.credentials_manager import CredentialsManager
from src.core.constants import FileConstants, TelegramConstants


class AccountAuthenticator:
    
    def __init__(self):
        self.sessions_dir = Path(FileConstants.SESSIONS_DIR)
        self.sessions_dir.mkdir(exist_ok=True)
        self.credentials_manager = CredentialsManager(self.sessions_dir)
    

    async def add_account(self, session_name: str) -> bool:
        """Добавляет новый аккаунт"""
        print(f"\n📱 Добавление аккаунта: {session_name}")
        print("-" * 40)
        
        print("\n📌 Получите API Key и API Hash на https://my.telegram.org/auth")
        print("   1. Войдите под своим аккаунтом")
        print("   2. Создайте приложение если нужно")
        print("   3. Скопируйте App api_id и App api_hash\n")
        
        try:
            api_id_str = input("API ID: ").strip()
            api_id = int(api_id_str)
            
            api_hash = input("API HASH: ").strip()
            
            if not api_hash or len(api_hash) != TelegramConstants.API_HASH_LENGTH:
                logger.error(f"API HASH должен быть {TelegramConstants.API_HASH_LENGTH} символа")
                return False
            
        except ValueError:
            logger.error("API ID должен быть числом")
            return False
        
        print("\nДополнительные настройки (Enter для пропуска):")
        
        app_version = input("App version (например: 'MyApp 1.0'): ").strip()
        device_model = input("Device model (например: 'Desktop'): ").strip()
        system_version = input("System version (например: 'Windows 10'): ").strip()
        lang_code = input("Language code (например: 'ru' или 'en'): ").strip()
        
        client_params = {
            "name": str(self.sessions_dir / session_name),
            "api_id": api_id,
            "api_hash": api_hash
        }
        
        if app_version:
            client_params["app_version"] = app_version
        if device_model:
            client_params["device_model"] = device_model
        if system_version:
            client_params["system_version"] = system_version
        if lang_code:
            client_params["lang_code"] = lang_code
        
        client = Client(**client_params)
        
        try:
            print("\n Запуск авторизации...")
            print("   Следуйте инструкциям Pyrogram для входа")
            print("   (введите номер телефона, код подтверждения и т.д.)\n")
            
            await client.start()
            
            me = await client.get_me()
            logger.success(f"\n Успешная авторизация: {me.first_name} (@{me.username})")
            
            self.credentials_manager.save(session_name, {
                "api_id": api_id,
                "api_hash": api_hash
            })
            
            await client.stop()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка авторизации: {e}")
            return False
    

    async def add_bot_account(self, session_name: str, bot_token: str) -> bool:
        print(f"\n Добавление бота: {session_name}")
        print("-" * 40)
        
        print("\n Для бота нужны API credentials (не токен!)")
        print("   Получите их на https://my.telegram.org как для обычного аккаунта")
        
        try:
            api_id_str = input("API ID: ").strip()
            api_id = int(api_id_str)
            
            api_hash = input("API HASH: ").strip()
            
            if not api_hash or len(api_hash) != TelegramConstants.API_HASH_LENGTH:
                logger.error(f"API HASH должен быть {TelegramConstants.API_HASH_LENGTH} символа")
                return False
            
        except ValueError:
            logger.error("API ID должен быть числом")
            return False
        
        client = Client(
            name=str(self.sessions_dir / session_name),
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token
        )
        
        try:
            print("\n Запуск авторизации бота...")
            
            await client.start()
            
            me = await client.get_me()
            logger.success(f"\n Бот успешно авторизован: {me.first_name} (@{me.username})")
            
            self.credentials_manager.save(session_name, {
                "api_id": api_id,
                "api_hash": api_hash,
                "bot_token": bot_token,
                "is_bot": True
            })
            
            await client.stop()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка авторизации бота: {e}")
            return False
    

    async def check_sessions(self) -> Dict[str, Dict[str, Any]]:
        valid_sessions = {}
        
        for session_file in self.sessions_dir.glob("*.session"):
            session_name = session_file.stem
            
            creds = self.credentials_manager.load(session_name)
            if not creds:
                logger.warning(f"{session_name}: Нет сохраненных credentials")
                continue
            
            client = Client(
                name=str(self.sessions_dir / session_name),
                api_id=creds['api_id'],
                api_hash=creds['api_hash']
            )
            
            try:
                await client.start()
                me = await client.get_me()
                
                valid_sessions[session_name] = {
                    'name': me.first_name,
                    'username': me.username,
                    'id': me.id,
                    'is_bot': me.is_bot,
                    'is_premium': getattr(me, 'is_premium', False)
                }
                
                stars_balance = 0
                if not me.is_bot:
                    try:
                        stars_balance = await client.get_stars_balance()
                    except:
                        pass
                
                valid_sessions[session_name]['stars_balance'] = stars_balance
                
                premium = "⭐" if getattr(me, 'is_premium', False) else ""
                stars = f"{stars_balance:,}" if stars_balance > 0 else ""
                logger.info(f"{session_name}: {me.first_name} (@{me.username}) {premium} {stars}")
                
                await client.stop()
                
            except Exception as e:
                logger.error(f"❌ {session_name}: Недействительна ({str(e)[:50]}...)")
        
        return valid_sessions
    

    async def delete_session(self, session_name: str) -> bool:
        session_file = self.sessions_dir / f"{session_name}.session"
        
        if not session_file.exists():
            logger.error(f"Сессия {session_name} не найдена")
            return False
        
        try:
            session_file.unlink()
            self.credentials_manager.delete(session_name)
            logger.success(f"Сессия {session_name} удалена")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка удаления: {e}")
            return False
    

    async def interactive_setup(self) -> None:
        print("\n" + "="*50)
        print("TELEGRAM GIFT SNIPER - УПРАВЛЕНИЕ АККАУНТАМИ")
        print("="*50 + "\n")
        
        while True:
            print("\n Выберите действие:")
            print("1. Добавить новый аккаунт")
            print("2. Добавить бота")
            print("3. Проверить существующие аккаунты")
            print("4. Удалить аккаунт")
            print("5. Выход")
            
            choice = input("\n Ваш выбор (1-5): ").strip()
            
            if choice == "1":
                session_name = input("\n Название сессии (например: buyer, hunter_1): ").strip()
                
                if not session_name:
                    print("Название не может быть пустым!")
                    continue
                
                if ' ' in session_name:
                    print("Название не должно содержать пробелы!")
                    continue
                
                if (self.sessions_dir / f"{session_name}.session").exists():
                    print(f"Сессия {session_name} уже существует!")
                    overwrite = input("Перезаписать? (y/n): ").strip().lower()
                    if overwrite != 'y':
                        continue
                
                success = await self.add_account(session_name)
                
                if success:
                    print(f"\n Аккаунт {session_name} успешно добавлен!")
                    
                    sessions = list(self.sessions_dir.glob("*.session"))
                    if len(sessions) == 1:
                        print("\n Рекомендация: Добавьте еще хотя бы один аккаунт")
                        print("   Первый будет покупателем, остальные - охотниками")
                else:
                    print(f"\n Не удалось добавить аккаунт {session_name}")

            elif choice == "2":
                session_name = input("\n Название сессии бота (например: notification_bot): ").strip()
                
                if not session_name:
                    print("Название не может быть пустым!")
                    continue
                
                if ' ' in session_name:
                    print("Название не должно содержать пробелы!")
                    continue
                
                bot_token = input("Токен бота от @BotFather: ").strip()
                
                if not bot_token or ':' not in bot_token:
                    print("Неверный формат токена!")
                    continue
                
                if (self.sessions_dir / f"{session_name}.session").exists():
                    print(f"Сессия {session_name} уже существует!")
                    overwrite = input("Перезаписать? (y/n): ").strip().lower()
                    if overwrite != 'y':
                        continue
                
                success = await self.add_bot_account(session_name, bot_token)
                
                if success:
                    print(f"\n Бот {session_name} успешно добавлен!")
                    print(f"\n Добавьте в config.py:")
                    print(f"BOT_SESSION = '{session_name}'")
                else:
                    print(f"\n Не удалось добавить бота {session_name}")

            elif choice == "3":
                print("\n Проверка существующих аккаунтов...")
                valid_sessions = await self.check_sessions()
                
                if valid_sessions:
                    print(f"\n Найдено {len(valid_sessions)} действительных аккаунтов")
                    
                    accounts = {k: v for k, v in valid_sessions.items() if not v['is_bot']}
                    bots = {k: v for k, v in valid_sessions.items() if v['is_bot']}
                    
                    if len(accounts) >= 2:
                        print("\n Рекомендуемая конфигурация для config.py:")
                        print("-" * 40)
                        
                        sessions_list = list(accounts.keys())
                        buyer = max(sessions_list, key=lambda s: accounts[s]['stars_balance'])
                        hunters = [s for s in sessions_list if s != buyer]
                        
                        print(f"BUYER_SESSION = '{buyer}'")
                        print(f"HUNTER_SESSIONS = {hunters}")
                        
                        if bots:
                            bot_name = list(bots.keys())[0]
                            print(f"BOT_SESSION = '{bot_name}'")
                    else:
                        print("\n Добавьте минимум 2 аккаунта для работы")
                else:
                    print("\n Действительных аккаунтов не найдено")
                
            elif choice == "4":
                session_name = input("\n Название сессии для удаления: ").strip()
                
                if session_name:
                    confirm = input(f" Удалить сессию {session_name}? (y/n): ").strip().lower()
                    if confirm == 'y':
                        await self.delete_session(session_name)
                
            elif choice == "5":
                print("\n Выход...")
                break
            
            else:
                print("\n Неверный выбор!")


async def main():
    setup_logger()
    authenticator = AccountAuthenticator()
    await authenticator.interactive_setup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n Прервано пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
