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
)


class SimpleReconnectionClient(TelegramClient):
    """Cliente simplificado con reconexión básica sin complejidades"""
    
    def __init__(self, *args, **kwargs):
        # Deshabilitar reconexión automática de Telethon para control manual
        kwargs.setdefault("auto_reconnect", False)
        kwargs.setdefault("connection_retries", 0)
        kwargs.setdefault("retry_delay", 0)
        
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("SimpleReconnection")
        self._reconnecting = False
        self._connection_failures = 0
        self._max_reconnect_attempts = 5

    async def connect(self, retries=3, *args, **kwargs):
        """Conexión con reintentos básicos"""
        for attempt in range(retries + 1):
            try:
                if self.is_connected():
                    self.logger.info("Ya conectado")
                    return True
                
                self.logger.info(f"Conectando... (intento {attempt + 1}/{retries + 1})")
                await super().connect(*args, **kwargs)
                
                if self.is_connected():
                    # Verificar que la conexión funciona
                    await self.get_me()
                    self._connection_failures = 0
                    self.logger.info("✅ Conexión exitosa")
                    return True
                    
            except (ConnectionError, OSError) as e:
                self.logger.warning(f"Error de conexión (intento {attempt + 1}): {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                    
            except (AuthKeyUnregisteredError, AuthKeyInvalidError, AuthKeyDuplicatedError) as e:
                self.logger.critical(f"Error de autenticación crítico: {e}")
                raise e
                
            except FloodWaitError as e:
                self.logger.warning(f"Flood wait: {e.seconds}s")
                await asyncio.sleep(e.seconds)
                
        self.logger.error(f"Falló la conexión después de {retries + 1} intentos")
        return False

    async def simple_reconnect(self):
        """Sistema de reconexión simple sin complejidades"""
        if self._reconnecting:
            return False
            
        self._reconnecting = True
        self._connection_failures += 1
        
        try:
            self.logger.warning(f"Iniciando reconexión simple (fallo #{self._connection_failures})")
            
            # Desconectar limpiamente si es necesario
            if self.is_connected():
                await self.disconnect()
            
            # Esperar antes de reconectar
            await asyncio.sleep(min(self._connection_failures * 2, 30))
            
            # Intentar reconectar
            success = await self.connect(retries=3)
            
            if success:
                self.logger.info("✅ Reconexión simple exitosa")
                self._connection_failures = 0
                return True
            else:
                self.logger.error("❌ Reconexión simple falló")
                
                # Si falló muchas veces, usar reconexión más agresiva
                if self._connection_failures >= self._max_reconnect_attempts:
                    self.logger.warning("Demasiados fallos, intentando reconexión agresiva...")
                    return await self._aggressive_reconnect()
                
                return False
                
        except Exception as e:
            self.logger.error(f"Error durante reconexión simple: {e}")
            return False
            
        finally:
            self._reconnecting = False

    async def _aggressive_reconnect(self):
        """Reconexión más agresiva para casos difíciles"""
        try:
            self.logger.warning("🚨 Reconexión agresiva iniciada")
            
            # Desconectar completamente
            await self.disconnect()
            await asyncio.sleep(5)
            
            # Múltiples intentos con diferentes configuraciones
            for attempt in range(3):
                try:
                    self.logger.warning(f"Intento agresivo {attempt + 1}/3")
                    
                    # Reconectar con configuración básica
                    await super().connect()
                    
                    if self.is_connected():
                        await self.get_me()  # Verificar funcionalidad
                        self.logger.warning("✅ Reconexión agresiva exitosa")
                        self._connection_failures = 0
                        return True
                        
                except Exception as e:
                    self.logger.warning(f"Intento agresivo {attempt + 1} falló: {e}")
                    if attempt < 2:
                        await asyncio.sleep(10 * (attempt + 1))
                        
            self.logger.error("❌ Reconexión agresiva falló completamente")
            return False
            
        except Exception as e:
            self.logger.error(f"Error crítico en reconexión agresiva: {e}")
            return False

    def start_simple_monitoring(self):
        """Iniciar monitoreo simple de la conexión"""
        asyncio.create_task(self._simple_monitor_loop())

    async def _simple_monitor_loop(self):
        """Loop básico de monitoreo de conexión"""
        while True:
            try:
                await asyncio.sleep(30)  # Verificar cada 30 segundos
                
                if not self.is_connected():
                    self.logger.warning("Conexión perdida detectada por monitor")
                    await self.simple_reconnect()
                    
            except Exception as e:
                self.logger.error(f"Error en monitor: {e}")
                await asyncio.sleep(60)  # Esperar más tiempo si hay error