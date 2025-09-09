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
        # Configuración para reconexión paulatina
        kwargs.setdefault("auto_reconnect", False)
        kwargs.setdefault("connection_retries", 0)
        kwargs.setdefault("retry_delay", 0)
        
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("GradualReconnection")
        self._reconnecting = False
        self._connection_failures = 0

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
                    await self.get_me()
                    self._connection_failures = 0
                    self.logger.info("Conexión exitosa")
                    return True
                    
            except (ConnectionError, OSError, ConnectionAbortedError) as e:
                self.logger.warning(f"Error de conexión (intento {attempt + 1}): {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
                    
            except (AuthKeyUnregisteredError, AuthKeyInvalidError, AuthKeyDuplicatedError) as e:
                self.logger.critical(f"Error de autenticación crítico: {e}")
                raise e
                
            except FloodWaitError as e:
                self.logger.warning(f"Flood wait: {e.seconds}s")
                await asyncio.sleep(e.seconds)
                
        self.logger.error(f"Falló la conexión después de {retries + 1} intentos")
        return False


    async def gradual_reconnect(self):
        """Sistema de reconexión paulatina por fases como el original"""
        if self._reconnecting:
            return False
            
        self._reconnecting = True
        phases = [
            {"name": "Básica", "wait": 2, "retries": 2},
            {"name": "Intermedia", "wait": 5, "retries": 3},  
            {"name": "Avanzada", "wait": 10, "retries": 4},
            {"name": "Intensiva", "wait": 20, "retries": 5},
            {"name": "Final", "wait": 30, "retries": 6}
        ]
        
        try:
            for phase_num, phase in enumerate(phases, 1):
                self.logger.info(f"Fase {phase_num}: Reconexión {phase['name']}")
                
                # Desconectar limpiamente
                try:
                    if self.is_connected():
                        await asyncio.wait_for(self.disconnect(), timeout=5.0)
                except:
                    pass
                
                # Esperar tiempo progresivo
                await asyncio.sleep(phase["wait"])
                
                # Intentar reconectar con los reintentos de esta fase
                for attempt in range(phase["retries"]):
                    try:
                        self.logger.info(f"Fase {phase_num} - Intento {attempt + 1}/{phase['retries']}")
                        await super().connect()
                        
                        if self.is_connected():
                            # Verificar que funciona
                            await asyncio.wait_for(self.get_me(), timeout=10.0)
                            self.logger.info(f"Reconexión exitosa en fase {phase_num}")
                            self._connection_failures = 0
                            return True
                            
                    except Exception as e:
                        self.logger.warning(f"Fase {phase_num} intento {attempt + 1} falló: {e}")
                        if attempt < phase["retries"] - 1:
                            await asyncio.sleep(2)
                
                self.logger.warning(f"Fase {phase_num} completada sin éxito")
            
            self.logger.error("Todas las fases de reconexión paulatina fallaron")
            return False
            
        except Exception as e:
            self.logger.error(f"Error crítico en reconexión paulatina: {e}")
            return False
            
        finally:
            self._reconnecting = False