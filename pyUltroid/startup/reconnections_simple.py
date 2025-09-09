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
            print("\n🔧 [DEBUG] ===== INICIANDO PROCESO DE RECONEXIÓN =====")
            print(f"🔧 [DEBUG] Estado inicial: connected={self.is_connected()}")
            print(f"🔧 [DEBUG] Loop running: {hasattr(self, 'loop') and self.loop.is_running()}")
            
            # Verificar estado previo
            if self.is_connected():
                print("🔧 [DEBUG] ⚠️ Cliente ya conectado, desconectando primero...")
                await self.disconnect()
                print(f"🔧 [DEBUG] Post-disconnect: connected={self.is_connected()}")
            
            print("🔧 [DEBUG] 🌐 Ejecutando super().connect()...")
            
            # Llamar al método interno de conexión de Telethon
            await super().connect()
            
            print(f"🔧 [DEBUG] 📡 Post-connect: connected={self.is_connected()}")
            
            if self.is_connected():
                print("🔧 [DEBUG] 🧪 Probando funcionalidad con get_me()...")
                try:
                    me = await self.get_me()
                    print(f"🔧 [DEBUG] ✅ get_me() exitoso: {me.first_name if me else 'None'}")
                    self.logger.info("✅ Reconexión nativa exitosa")
                    return True
                except Exception as test_e:
                    print(f"🔧 [DEBUG] ❌ get_me() falló: {test_e}")
                    return False
            else:
                print("🔧 [DEBUG] ❌ is_connected() devuelve False")
                self.logger.warning("❌ Método nativo falló")
                return False
                
        except Exception as e:
            print(f"🔧 [DEBUG] 💥 Excepción capturada: {type(e).__name__}: {e}")
            print(f"🔧 [DEBUG] Estado post-error: connected={self.is_connected()}")
            self.logger.error(f"💥 Error invocando método nativo: {e}")
            return False
        finally:
            print("🔧 [DEBUG] ===== FIN PROCESO DE RECONEXIÓN =====\n")

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
                    print(f"\n⏳ [MAIN] Intento {attempt}/{max_attempts} - Esperando 10 segundos...")
                    self.logger.info(f"⏳ Intento {attempt}/{max_attempts} - Esperando 10 segundos...")
                    time.sleep(10)
                    
                    print(f"⚡ [MAIN] Ejecutando intento {attempt}/{max_attempts}...")
                    
                    # INVOCAR método nativo (sin transferir control)
                    reconnected = self.loop.run_until_complete(self.call_native_reconnect())
                    
                    if reconnected:
                        print(f"🎉 [MAIN] ¡ÉXITO! Reconectado en intento {attempt}/{max_attempts}")
                        self.logger.info(f"🎉 Reconectado en intento {attempt}/{max_attempts}")
                        break  # Salir del bucle de reconexión
                    else:
                        print(f"❌ [MAIN] Intento {attempt}/{max_attempts} FALLÓ")
                        self.logger.warning(f"❌ Intento {attempt}/{max_attempts} falló")
                        attempt += 1
                
                if not reconnected:
                    self.logger.error(f"💀 Agotados {max_attempts} intentos de reconexión. Cerrando bot...")
                    break  # Salir del bucle principal - cerrar aplicación
                        
                # Una vez reconectado, continuar con el bucle principal
                continue