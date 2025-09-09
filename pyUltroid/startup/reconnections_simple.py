# Ultroid - UserBot
# Copyright (C) 2021-2023 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import asyncio
import logging
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    AuthKeyUnregisteredError,
    AuthKeyInvalidError,
    AuthKeyDuplicatedError,
    UnauthorizedError,
    ConnectionError,
)


class SimpleReconnectionClient(TelegramClient):
    """Cliente simplificado con reconexión básica sin complejidades"""
    
    def __init__(self, *args, **kwargs):
        # Configuración básica de telethon para reconexión
        kwargs.setdefault("auto_reconnect", False)
        kwargs.setdefault("connection_retries", 0)
        kwargs.setdefault("retry_delay", 0)
        
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("SimpleReconnection")
        self._reconnecting = False
        self._connection_failures = 0

    async def simple_reconnect(self, max_attempts=3):
        """Reconexión básica sin complejidades"""
        if self._reconnecting:
            return False
            
        self._reconnecting = True
        self.logger.info("Iniciando reconexión simple...")
        
        try:
            for attempt in range(max_attempts):
                try:
                    # Desconectar limpiamente si está conectado
                    if self.is_connected():
                        await self.disconnect()
                    
                    # Espera exponencial simple
                    if attempt > 0:
                        wait_time = 2 ** attempt
                        self.logger.info(f"Esperando {wait_time}s antes del intento {attempt + 1}")
                        await asyncio.sleep(wait_time)
                    
                    # Intentar reconectar
                    self.logger.info(f"Reconexión simple - intento {attempt + 1}/{max_attempts}")
                    await super().connect()
                    
                    if self.is_connected():
                        # Verificar que funciona
                        await self.get_me()
                        self.logger.info("✅ Reconexión simple exitosa")
                        self._connection_failures = 0
                        return True
                        
                except FloodWaitError as e:
                    self.logger.warning(f"Flood wait: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    
                except (AuthKeyUnregisteredError, AuthKeyInvalidError, AuthKeyDuplicatedError) as e:
                    self.logger.critical(f"Error de autenticación: {e}")
                    raise e
                    
                except Exception as e:
                    self.logger.warning(f"Intento {attempt + 1} falló: {e}")
                    
            self.logger.error(f"❌ Reconexión simple falló después de {max_attempts} intentos")
            return False
            
        finally:
            self._reconnecting = False

    async def _aggressive_reconnect(self):
        """Reconexión agresiva para casos difíciles"""
        self.logger.info("🚨 Iniciando reconexión agresiva...")
        
        try:
            # Desconexión completa forzada
            try:
                await asyncio.wait_for(self.disconnect(), timeout=5.0)
            except:
                pass
            
            # Esperar más tiempo
            await asyncio.sleep(10)
            
            # 3 intentos con más tiempo entre ellos
            for attempt in range(3):
                try:
                    self.logger.info(f"Reconexión agresiva - intento {attempt + 1}/3")
                    await super().connect()
                    
                    if self.is_connected():
                        await asyncio.wait_for(self.get_me(), timeout=15.0)
                        self.logger.info("✅ Reconexión agresiva exitosa")
                        return True
                        
                except Exception as e:
                    self.logger.warning(f"Reconexión agresiva intento {attempt + 1} falló: {e}")
                    if attempt < 2:
                        await asyncio.sleep(10)
                        
            return False
            
        except Exception as e:
            self.logger.error(f"Error en reconexión agresiva: {e}")
            return False

    async def auto_reconnect_on_error(self):
        """Manejo automático de errores de conexión"""
        self._connection_failures += 1
        
        # Si hay muchos fallos, usar reconexión agresiva
        if self._connection_failures >= 5:
            success = await self._aggressive_reconnect()
        else:
            success = await self.simple_reconnect()
            
        if success:
            self._connection_failures = 0
            return True
        else:
            return False

    async def start_simple_monitoring(self):
        """Monitoreo opcional simple cada 30 segundos"""
        while True:
            try:
                await asyncio.sleep(30)
                if not self.is_connected():
                    self.logger.warning("⚠️ Conexión perdida detectada por monitoreo")
                    await self.auto_reconnect_on_error()
            except Exception as e:
                self.logger.error(f"Error en monitoreo: {e}")