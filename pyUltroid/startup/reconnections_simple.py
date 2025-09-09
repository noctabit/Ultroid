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
        # Habilitar reconexión automática de Telethon pero con control adicional
        kwargs.setdefault("auto_reconnect", True)
        kwargs.setdefault("connection_retries", 5)
        kwargs.setdefault("retry_delay", 1)
        
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger("SimpleReconnection")
        self._reconnecting = False
        self._connection_failures = 0
        self._max_reconnect_attempts = 10  # Más intentos
        self._last_error_103_time = 0

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
                self.logger.warning(f"⏳ Flood wait: {e.seconds}s")
                await asyncio.sleep(e.seconds)
                
            except (ConnectionAbortedError, ConnectionError, OSError) as e:
                error_str = str(e)
                if "103" in error_str or "abort" in error_str.lower():
                    import time
                    self._last_error_103_time = time.time()
                    self.logger.warning(f"🚨 Error 103 detectado durante conexión: {e}")
                else:
                    self.logger.warning(f"🔌 Error de conexión durante connect (intento {attempt + 1}): {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                
        self.logger.error(f"Falló la conexión después de {retries + 1} intentos")
        return False

    async def simple_reconnect(self):
        """Sistema de reconexión simple sin complejidades"""
        if self._reconnecting:
            self.logger.debug("Reconexión ya en progreso, esperando...")
            return False
            
        self._reconnecting = True
        self._connection_failures += 1
        
        try:
            self.logger.warning(f"🔄 Iniciando reconexión simple (fallo #{self._connection_failures})")
            
            # Para errores 103, ser más agresivo
            import time
            current_time = time.time()
            if current_time - self._last_error_103_time < 60:  # Si el último error 103 fue hace menos de 1 min
                self.logger.warning("🚨 Error 103 reciente detectado, usando reconexión agresiva inmediata")
                return await self._aggressive_reconnect()
            
            # Desconectar limpiamente
            try:
                if self.is_connected():
                    await asyncio.wait_for(self.disconnect(), timeout=5.0)
            except:
                pass  # Ignorar errores de desconexión
            
            # Esperar progresivo
            wait_time = min(self._connection_failures * 3, 20)
            self.logger.warning(f"⏳ Esperando {wait_time}s antes de reconectar...")
            await asyncio.sleep(wait_time)
            
            # Intentar reconectar con más reintentos
            success = await self.connect(retries=5)
            
            if success:
                self.logger.info("✅ Reconexión simple exitosa")
                self._connection_failures = 0
                return True
            else:
                self.logger.error("❌ Reconexión simple falló")
                
                # Si falló varias veces, usar reconexión más agresiva
                if self._connection_failures >= 3:  # Más agresivo
                    self.logger.warning("🚨 Múltiples fallos, iniciando reconexión agresiva...")
                    return await self._aggressive_reconnect()
                
                return False
                
        except Exception as e:
            self.logger.error(f"💥 Error durante reconexión simple: {e}")
            return False
            
        finally:
            self._reconnecting = False

    async def _aggressive_reconnect(self):
        """Reconexión más agresiva para casos difíciles como error 103"""
        try:
            self.logger.warning("🚨 Reconexión agresiva iniciada")
            
            # Limpiar completamente la conexión
            try:
                await asyncio.wait_for(self.disconnect(), timeout=10.0)
            except:
                pass  # Ignorar errores de desconexión
                
            await asyncio.sleep(8)  # Espera más larga
            
            # Múltiples intentos con configuración más robusta
            for attempt in range(5):  # Más intentos
                try:
                    self.logger.warning(f"🔄 Intento agresivo {attempt + 1}/5")
                    
                    # Reconectar directamente sin usar auto_reconnect
                    success = await super().connect()
                    
                    if success and self.is_connected():
                        # Verificar que la conexión realmente funciona
                        try:
                            await asyncio.wait_for(self.get_me(), timeout=10.0)
                            self.logger.warning("✅ Reconexión agresiva exitosa")
                            self._connection_failures = 0
                            return True
                        except asyncio.TimeoutError:
                            self.logger.warning(f"⏰ Timeout en verificación de conexión (intento {attempt + 1})")
                            continue
                        except Exception as verify_error:
                            self.logger.warning(f"❌ Verificación falló (intento {attempt + 1}): {verify_error}")
                            continue
                        
                except Exception as e:
                    self.logger.warning(f"💥 Intento agresivo {attempt + 1} falló: {e}")
                    
                # Espera progresiva entre intentos
                if attempt < 4:
                    wait_time = 15 + (attempt * 5)
                    self.logger.warning(f"⏳ Esperando {wait_time}s antes del siguiente intento...")
                    await asyncio.sleep(wait_time)
                        
            self.logger.error("❌ Reconexión agresiva falló completamente")
            return False
            
        except Exception as e:
            self.logger.error(f"💥 Error crítico en reconexión agresiva: {e}")
            return False

    def start_simple_monitoring(self):
        """Iniciar monitoreo simple de la conexión"""
        try:
            asyncio.create_task(self._simple_monitor_loop())
        except RuntimeError:
            # Si no hay event loop corriendo, programar para más tarde
            self.logger.warning("🔍 No hay event loop, programando monitoreo para más tarde")
    
    def schedule_monitoring(self):
        """Programar monitoreo para cuando el event loop esté listo"""
        try:
            # Usar call_later para programar el inicio del monitoreo
            self.loop.call_later(5, self._start_monitoring_task)
        except Exception as e:
            self.logger.warning(f"No se pudo programar monitoreo: {e}")
    
    def _start_monitoring_task(self):
        """Iniciar la tarea de monitoreo en el event loop"""
        try:
            asyncio.create_task(self._simple_monitor_loop())
            self.logger.info("🔍 Monitoreo de conexión iniciado")
        except Exception as e:
            self.logger.warning(f"Error iniciando monitoreo: {e}")

    async def _simple_monitor_loop(self):
        """Loop básico de monitoreo de conexión mejorado"""
        consecutive_failures = 0
        max_failures = 2
        
        while True:
            try:
                await asyncio.sleep(25)  # Verificar cada 25 segundos
                
                # No monitorear durante reconexión
                if self._reconnecting:
                    consecutive_failures = 0
                    continue
                
                # Verificar conexión
                if not self.is_connected():
                    consecutive_failures += 1
                    self.logger.warning(f"🔍 Conexión perdida detectada por monitor (fallo {consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        self.logger.warning("🚨 Monitor: Múltiples desconexiones, iniciando reconexión...")
                        await self.simple_reconnect()
                        consecutive_failures = 0
                else:
                    # Verificar funcionalidad con ping rápido
                    try:
                        await asyncio.wait_for(self.get_me(), timeout=8.0)
                        consecutive_failures = 0  # Reset contador si funciona bien
                    except (ConnectionAbortedError, ConnectionError, OSError) as e:
                        consecutive_failures += 1
                        self.logger.warning(f"🔍 Error de conexión detectado por monitor: {e}")
                        
                        # Marcar tiempo de error 103 para reconexión más agresiva
                        if "103" in str(e) or "abort" in str(e).lower():
                            import time
                            self._last_error_103_time = time.time()
                            self.logger.warning("🚨 Error 103 detectado por monitor, marcando para reconexión agresiva")
                        
                        if consecutive_failures >= max_failures:
                            await self.simple_reconnect()
                            consecutive_failures = 0
                    except asyncio.TimeoutError:
                        consecutive_failures += 1
                        self.logger.warning(f"⏰ Monitor: Timeout de ping (fallo {consecutive_failures}/{max_failures})")
                        if consecutive_failures >= max_failures:
                            await self.simple_reconnect()
                            consecutive_failures = 0
                    except Exception:
                        pass  # Ignorar otros errores de verificación
                    
            except Exception as e:
                self.logger.error(f"💥 Error en monitor: {e}")
                await asyncio.sleep(45)  # Esperar más tiempo si hay error en el monitor