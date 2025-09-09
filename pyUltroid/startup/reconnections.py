import logging
import asyncio
from telethon import TelegramClient, events
from telethon.errors import (
    FloodWaitError,
    AuthKeyUnregisteredError,
    AuthKeyInvalidError,
    AuthKeyDuplicatedError,
    SessionPasswordNeededError,
    UnauthorizedError,
)
import socket

class CustomTelegramClient(TelegramClient):
    def __init__(self, *args, logger=None, **kwargs):
        # DESHABILITAR el sistema de reconexión nativo de Telethon para evitar conflictos
        kwargs["auto_reconnect"] = False  # Nuestro sistema toma control completo
        kwargs["connection_retries"] = 1   # Solo 1 intento nativo, luego nuestro sistema
        kwargs["retry_delay"] = 0         # Sin delay nativo
        super().__init__(*args, **kwargs)
        self.logger = logger or logging.getLogger("Reconnections")
        self._reconnecting = False
        self._max_retries = 50
        self._current_retries = 0
        self._plugin_loading = False  # Flag para evitar conflictos durante carga de plugins
        self.retries = [
            (5, 5),     # 5 intentos cada 5 segundos
            (5, 10),    # 5 intentos cada 10 segundos  
            (5, 30),    # 5 intentos cada 30 segundos
            (5, 60),    # 5 intentos cada 1 minuto
            (5, 300),   # 5 intentos cada 5 minutos
            (5, 900),   # 5 intentos cada 15 minutos
            (10, 1800), # 10 intentos cada 30 minutos
            (10, 3600), # 10 intentos cada hora
        ]
        
        # Registrar manejadores de eventos de conexión DESPUÉS de la carga de plugins
        # Para evitar interferencias durante la inicialización
        self._event_handlers_registered = False

    async def connect(self, retries=3, *args, **kwargs):
        """Conexión mejorada con manejo de errores"""
        for attempt in range(retries + 1):
            try:
                if self.is_connected():
                    self.logger.info("Cliente ya conectado")
                    return True
                    
                self.logger.info(f"Intentando conectar... (intento {attempt + 1}/{retries + 1})")
                await super().connect(*args, **kwargs)
                
                # Verificar conexión más robusta
                if self.is_connected():
                    try:
                        # Hacer una prueba real de la conexión
                        await self.get_me()
                        self.logger.info("✅ Conexión exitosa a Telegram")
                        self._current_retries = 0
                        self._reconnecting = False
                        return True
                    except Exception as e:
                        self.logger.warning(f"⚠️ Conexión establecida pero no funcional: {e}")
                else:
                    self.logger.warning("⚠️ Conexión no establecida correctamente")
                    
            except (OSError, socket.error, socket.timeout) as e:
                self.logger.warning(f"🔄 Error de conexión (intento {attempt + 1}): {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    self.logger.error(f"❌ Falló la conexión después de {retries + 1} intentos")
                    if not self._reconnecting:
                        asyncio.create_task(self._handle_reconnection())
                    
            except (AuthKeyUnregisteredError, AuthKeyInvalidError, AuthKeyDuplicatedError) as e:
                self.logger.critical(f"❌ Error de autenticación crítico: {e}")
                raise e
                
            except FloodWaitError as e:
                self.logger.warning(f"⏳ Flood wait: esperando {e.seconds} segundos")
                await asyncio.sleep(e.seconds)
                
            except Exception as e:
                self.logger.error(f"❌ Error inesperado durante la conexión: {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    if not self._reconnecting:
                        asyncio.create_task(self._handle_reconnection())
        
        return False

    def _register_disconnect_handlers(self):
        """Registrar manejadores de desconexión después de que todo esté listo"""
        if not self._event_handlers_registered:
            self.add_event_handler(self._handle_disconnect, events.Raw)
            self._event_handlers_registered = True
            self.logger.info("🔌 Manejadores de desconexión registrados")

    async def _handle_disconnect(self, event):
        """Maneja eventos de desconexión automáticamente"""
        # No procesar eventos durante la carga de plugins
        if self._plugin_loading:
            return
            
        if hasattr(event, 'original_update') and hasattr(event.original_update, '__class__'):
            event_type = event.original_update.__class__.__name__
            if 'UpdatesTooLong' in event_type or 'UpdateConnectionState' in event_type:
                # Doble verificación antes de activar reconexión
                await asyncio.sleep(2)  # Pequeña pausa para evitar reconexiones precipitadas
                if not self.is_connected() and not self._reconnecting:
                    self.logger.warning(f"🔌 Evento de desconexión detectado: {event_type}")
                    asyncio.create_task(self._handle_reconnection())

    async def _handle_reconnection(self):
        """Manejo mejorado de la reconexión con estrategia escalonada"""
        if self._reconnecting:
            self.logger.debug("🔄 Reconexión ya en progreso, ignorando solicitud")
            return
        
        # No reconectar durante la carga de plugins
        if self._plugin_loading:
            self.logger.debug("🔄 Carga de plugins en progreso, posponiendo reconexión")
            await asyncio.sleep(10)
            if self._plugin_loading:  # Si sigue cargando después de 10s
                return
        
        # Verificar una vez más antes de iniciar reconexión
        if self.is_connected():
            try:
                await self.get_me()
                self.logger.debug("✅ Conexión verificada como activa, cancelando reconexión")
                return True
            except Exception as e:
                self.logger.debug(f"🔍 Verificación de conexión falló: {e}, procediendo con reconexión")
            
        self._reconnecting = True
        self.logger.warning("🔄 Iniciando proceso de reconexión...")
        
        for retry_group_idx, (attempts, delay) in enumerate(self.retries):
            self.logger.info(f"📋 Grupo de reconexión {retry_group_idx + 1}: {attempts} intentos cada {delay}s")
            
            for attempt in range(attempts):
                if self.is_connected():
                    try:
                        # Verificar que la conexión realmente funciona
                        await self.get_me()
                        self.logger.info("✅ Cliente ya reconectado y funcional")
                        self._reconnecting = False
                        return True
                    except Exception as e:
                        self.logger.debug(f"🔍 Conexión no funcional: {e}, continuando reconexión")
                
                try:
                    self._current_retries += 1
                    if self._current_retries > self._max_retries:
                        self.logger.critical("❌ Máximo número de reintentos alcanzado")
                        self._reconnecting = False
                        return False
                    
                    self.logger.info(
                        f"🔄 Intento de reconexión {attempt + 1}/{attempts} "
                        f"(grupo {retry_group_idx + 1}, total: {self._current_retries})"
                    )
                    
                    # Desconectar si está parcialmente conectado
                    if hasattr(self, '_sender') and self._sender:
                        try:
                            await self.disconnect_async()
                        except:
                            pass
                            
                    await asyncio.sleep(min(delay, 5))  # Espera inicial mínima
                    
                    # Intentar reconectar
                    if await self.connect(retries=1):
                        self.logger.info("✅ Reconexión exitosa!")
                        self._reconnecting = False
                        return True
                        
                except FloodWaitError as e:
                    self.logger.warning(f"⏳ Flood wait durante reconexión: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    
                except (AuthKeyUnregisteredError, AuthKeyInvalidError, UnauthorizedError) as e:
                    self.logger.critical(f"❌ Error crítico de autorización: {e}")
                    self._reconnecting = False
                    raise e
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Error durante reconexión: {e}")
                
                if attempt < attempts - 1:
                    await asyncio.sleep(delay)
        
        self.logger.critical("❌ Todos los intentos de reconexión fallaron")
        self._reconnecting = False
        return False

    def disconnect(self):
        """Desconexión controlada - DEBE ser síncrono para compatibilidad con Telethon"""
        try:
            if self.is_connected():
                self.logger.info("🔌 Desconectando cliente...")
                # Usar la desconexión síncrona del padre para evitar RuntimeWarning
                result = super().disconnect()
                self.logger.info("✅ Cliente desconectado")
                return result
        except Exception as e:
            self.logger.warning(f"⚠️ Error durante desconexión: {e}")
            return None
    
    async def disconnect_async(self):
        """Versión async de desconexión para uso interno"""
        try:
            if self.is_connected():
                self.logger.info("🔌 Desconectando cliente (async)...")
                await super().disconnect()
                self.logger.info("✅ Cliente desconectado (async)")
        except Exception as e:
            self.logger.warning(f"⚠️ Error durante desconexión async: {e}")

    def is_connected(self):
        """Verificación mejorada del estado de conexión"""
        try:
            base_connected = super().is_connected()
            if not base_connected:
                return False
            
            # Verificación adicional de sender solo si tenemos uno
            if hasattr(self, '_sender') and self._sender:
                try:
                    return not self._sender.is_disconnected()
                except AttributeError:
                    # Si no tiene is_disconnected, asumimos que está conectado
                    return True
            
            return base_connected
        except Exception:
            # En caso de error, usar solo la verificación básica
            try:
                return super().is_connected()
            except Exception:
                return False
    
    def set_plugin_loading_state(self, loading=True):
        """Establecer estado de carga de plugins para evitar conflictos"""
        self._plugin_loading = loading
        if loading:
            self.logger.debug("🔌 Iniciando carga de plugins - pausando sistema de reconexión")
        else:
            self.logger.debug("🔌 Carga de plugins completada - reactivando sistema de reconexión")
            # Registrar manejadores ahora que los plugins están cargados
            self._register_disconnect_handlers()







