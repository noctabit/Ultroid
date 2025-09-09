# Ultroid - UserBot
# Copyright (C) 2021-2023 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import asyncio
import logging
import time
from telethon import TelegramClient


class SimpleReconnectionClient(TelegramClient):
    """Cliente que llama a métodos nativos de Telethon cada 10s sin transferir control"""
    
    def __init__(self, *args, **kwargs):
        # Desactivar reconexión automática - MI código mantiene control total
        kwargs.setdefault("auto_reconnect", False)
        kwargs.setdefault("connection_retries", 0)
        kwargs.setdefault("retry_delay", 0)
        
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("SimpleReconnection")

    async def call_native_reconnect(self):
        """Mi código invoca métodos nativos de Telethon sin transferir control"""
        try:
            self.logger.info("🔧 Invocando métodos nativos de Telethon...")
            
            # Llamar al método interno de conexión de Telethon
            # Esto usa toda la lógica nativa (servidores, protocolos, etc.)
            await super().connect()
            
            if self.is_connected():
                # Verificar que la conexión funciona
                await self.get_me()
                self.logger.info("✅ Reconexión nativa exitosa")
                return True
            else:
                self.logger.warning("❌ Método nativo falló")
                return False
                
        except Exception as e:
            self.logger.error(f"💥 Error invocando método nativo: {e}")
            return False

    def run(self):
        """run con bucle que invoca métodos nativos cada 10s"""
        while True:
            try:
                self.run_until_disconnected()
                break  # Salida normal
            except Exception as e:
                self.logger.error(f"❌ Conexión perdida: {e}")
                
                # MI código mantiene control, pero invoca métodos nativos cada 10s
                reconnected = False
                attempt = 1
                max_attempts = 50
                
                while not reconnected and attempt <= max_attempts:
                    self.logger.info(f"⏳ Intento {attempt}/{max_attempts} - Esperando 10 segundos...")
                    time.sleep(10)
                    
                    # INVOCAR método nativo (sin transferir control)
                    reconnected = self.loop.run_until_complete(self.call_native_reconnect())
                    
                    if reconnected:
                        self.logger.info(f"🎉 Reconectado en intento {attempt}/{max_attempts}")
                        break  # Salir del bucle de reconexión
                    else:
                        self.logger.warning(f"❌ Intento {attempt}/{max_attempts} falló")
                        attempt += 1
                
                if not reconnected:
                    self.logger.error(f"💀 Agotados {max_attempts} intentos de reconexión. Cerrando bot...")
                    break  # Salir del bucle principal - cerrar aplicación
                        
                # Una vez reconectado, continuar con el bucle principal
                continue