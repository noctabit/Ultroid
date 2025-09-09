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
    RPCError,
)
import socket
import errno
import sys
from typing import Optional

class CustomTelegramClient(TelegramClient):
    def __init__(self, *args, logger=None, **kwargs):
        # DESHABILITAR COMPLETAMENTE el sistema de reconexión nativo de Telethon
        kwargs["auto_reconnect"] = False  # Deshabilitado completamente
        kwargs["connection_retries"] = 0   # Cero intentos nativos
        kwargs["retry_delay"] = 0         # Sin delay nativo
        super().__init__(*args, **kwargs)
        self.logger = logger or logging.getLogger("Reconnections")
        self._reconnecting = False
        self._max_retries = 50
        self._current_retries = 0
        self._plugin_loading = False  # Flag para evitar conflictos durante carga de plugins
        self._last_connection_error = None  # Último error de conexión para diagnóstico
        self._connection_abort_count = 0  # Contador específico para errores de abort
        self._force_cleanup_on_reconnect = False  # Flag para limpieza forzada
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
        
        # Deshabilitar completamente el sistema de keepalive de Telethon
        self._keepalive_task = None
        
        # Sobrescribir métodos internos de Telethon para control total
        self._setup_complete_override()

    async def connect(self, retries=3, *args, **kwargs):
        """Conexión mejorada con manejo de errores"""
        for attempt in range(retries + 1):
            try:
                if self.is_connected():
                    self.logger.info("Cliente ya conectado")
                    return True
                    
                self.logger.info(f"Intentando conectar... (intento {attempt + 1}/{retries + 1})")
                
                # Forzar configuración sin reconexiones antes de conectar
                self._auto_reconnect = False
                
                await super().connect(*args, **kwargs)
                
                # IMPORTANTE: Deshabilitar completamente todos los sistemas nativos
                self._disable_native_systems()
                
                # Aplicar sobrescrituras inmediatamente después de conectar
                self._apply_sender_overrides()
                
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
                    
            except (ConnectionAbortedError, ConnectionResetError, ConnectionError) as e:
                # Manejo específico para errores de conexión abortada (Errno 103)
                self._last_connection_error = e
                self._connection_abort_count += 1
                self.logger.warning(f"💥 Error 103/abort detectado (intento {attempt + 1}): {e} [Count: {self._connection_abort_count}]")
                
                # Para error 103, SIEMPRE forzar limpieza completa
                self.logger.info("🧹 Error 103: Forzando limpieza completa antes del siguiente intento")
                await self._force_connection_cleanup()
                
                if attempt < retries:
                    # Backoff específico para errores 103
                    delay = min(3 + self._connection_abort_count, 10)
                    self.logger.info(f"⏳ Error 103: Esperando {delay}s antes del siguiente intento")
                    await asyncio.sleep(delay)
                else:
                    self.logger.error(f"❌ Falló la conexión después de {retries + 1} intentos (Error 103)")
                    # NO crear tareas recursivas automáticamente
                    return False
                        
            except (OSError, socket.error, socket.timeout) as e:
                self._last_connection_error = e
                self.logger.warning(f"🔄 Error de conexión general (intento {attempt + 1}): {e}")
                if attempt < retries:
                    await asyncio.sleep(2 ** attempt)  # Backoff exponencial
                else:
                    self.logger.error(f"❌ Falló la conexión después de {retries + 1} intentos")
                    # NO crear tareas recursivas automáticamente
                    return False
                    
            except (AuthKeyUnregisteredError, AuthKeyInvalidError, AuthKeyDuplicatedError) as e:
                self.logger.critical(f"❌ Error de autenticación crítico: {e}")
                raise e
                
            except FloodWaitError as e:
                self.logger.warning(f"⏳ Flood wait: esperando {e.seconds} segundos")
                await asyncio.sleep(e.seconds)
                
            except Exception as e:
                self._last_connection_error = e
                self.logger.error(f"❌ Error inesperado durante la conexión: {e}")
                # Verificar si es un error relacionado con conexión abortada
                if 'abort' in str(e).lower() or 'reset' in str(e).lower():
                    self._connection_abort_count += 1
                    self._force_cleanup_on_reconnect = True
                    
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
        """Manejo mejorado de la reconexión con estrategia escalonada y limpieza agresiva"""
        if self._reconnecting:
            self.logger.debug("🔄 Reconexión ya en progreso, ignorando solicitud")
            return
        
        # No reconectar durante la carga de plugins
        if self._plugin_loading:
            self.logger.debug("🔄 Carga de plugins en progreso, posponiendo reconexión")
            await asyncio.sleep(10)
            if self._plugin_loading:  # Si sigue cargando después de 10s
                return
        
        # Verificar si realmente necesitamos reconectar
        # Pero si hay force_cleanup_on_reconnect, forzar reconexión incluso si parece conectado
        if self.is_connected() and not self._force_cleanup_on_reconnect:
            try:
                # Verificación más robusta con timeout corto
                await asyncio.wait_for(self.get_me(), timeout=3.0)
                self.logger.debug("✅ Conexión verificada como activa, cancelando reconexión")
                self._reset_connection_counters()
                return True
            except asyncio.TimeoutError:
                self.logger.warning("⏰ Timeout en verificación - conexión zombie detectada")
                # Conexión zombie - proceder con reconexión
                self._force_cleanup_on_reconnect = True
            except (ConnectionAbortedError, ConnectionResetError, ConnectionError) as e:
                self.logger.warning(f"💥 Error 103/conexión durante verificación: {e}")
                self._connection_abort_count += 1
                self._force_cleanup_on_reconnect = True
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
                        f"🔄 Reconexión {attempt + 1}/{attempts} "
                        f"(grupo {retry_group_idx + 1}, total: {self._current_retries})"
                    )
                    
                    # PASO 1: Forzar desconexión completa si hay conexión zombie (error 103)
                    if self._connection_abort_count > 0 or 'abort' in str(self._last_connection_error or '').lower():
                        self.logger.info(f"💀 Conexión zombie detectada tras error 103 - forzando desconexión completa")
                        
                        # Método 1: Intentar desconexión forzada del sender
                        try:
                            if hasattr(self, '_sender') and self._sender:
                                self.logger.debug("🔧 Forzando desconexión del sender...")
                                await self._sender.disconnect()
                        except Exception as e:
                            self.logger.debug(f"⚠️ Error desconectando sender: {e}")
                        
                        # Método 2: Desconexión a nivel de cliente
                        try:
                            self.logger.debug("🔧 Forzando desconexión del cliente...")
                            await super().disconnect()
                        except Exception as e:
                            self.logger.debug(f"⚠️ Error desconectando cliente: {e}")
                            
                        # Método 3: Resetear flags internos manualmente
                        try:
                            self._connected = False
                            if hasattr(self, '_authorized'):
                                self._authorized = False
                        except Exception:
                            pass
                            
                        self.logger.info("💀 Desconexión zombie completada")
                        await asyncio.sleep(2.0)  # Esperar más para que tome efecto
                        
                    else:
                        # Desconexión normal para otros casos
                        try:
                            if super().is_connected():
                                self.logger.debug("🔌 Desconexión normal antes de reconectar...")
                                await self.disconnect_async()
                                await asyncio.sleep(1.0)
                        except Exception as e:
                            self.logger.debug(f"⚠️ Error durante desconexión normal: {e}")
                    
                    # PASO 2: Verificar que realmente está desconectado
                    max_disconnect_checks = 3
                    for check in range(max_disconnect_checks):
                        if not super().is_connected():
                            self.logger.debug("✅ Confirmada desconexión completa")
                            break
                        else:
                            self.logger.warning(f"⚠️ Aún reporta conexión - intento {check + 1}/{max_disconnect_checks}")
                            await asyncio.sleep(1.0)
                    
                    # PASO 3: Espera antes de reconectar
                    if self._connection_abort_count > 0:
                        wait_time = 3 + self._connection_abort_count  # Espera extra para errores 103
                        self.logger.info(f"⏳ Esperando {wait_time}s tras error 103...")
                    else:
                        wait_time = min(delay, 3)
                        self.logger.debug(f"⏳ Esperando {wait_time}s...")
                    
                    await asyncio.sleep(wait_time)
                    
                    # PASO 4: Reconexión directa y simple
                    self.logger.info("🔗 Iniciando reconexión...")
                    
                    try:
                        # Configurar antes de conectar
                        self._auto_reconnect = False
                        
                        # Reconexión directa usando Telethon base
                        await super().connect()
                        
                        # Inmediatamente después de conectar, deshabilitar sistemas nativos
                        self._disable_native_systems()
                        self._apply_sender_overrides()
                        
                        # Verificar que funciona
                        if self.is_connected():
                            try:
                                # Test rápido
                                await asyncio.wait_for(self.get_me(), timeout=3.0)
                                self.logger.info("✅ Reconexión exitosa y verificada!")
                                self._reset_connection_counters()
                                self._reconnecting = False
                                return True
                            except Exception as e:
                                self.logger.warning(f"❌ Test de reconexión falló: {e}")
                                # Desconectar si el test falla
                                try:
                                    await super().disconnect()
                                except:
                                    pass
                        else:
                            self.logger.warning("❌ Reconexión no establecida")
                            
                    except (ConnectionAbortedError, ConnectionResetError, ConnectionError) as e:
                        self.logger.warning(f"💥 Error 103 durante reconexión: {e}")
                        self._connection_abort_count += 1
                        # Marcar para limpieza más agresiva en siguiente intento
                        self._force_cleanup_on_reconnect = True
                        
                    except Exception as e:
                        self.logger.warning(f"❌ Error durante reconexión: {e}")
                    
                    self.logger.warning(f"❌ Intento de reconexión {attempt + 1} falló")
                        
                except FloodWaitError as e:
                    self.logger.warning(f"⏳ Flood wait durante reconexión: {e.seconds}s")
                    await asyncio.sleep(e.seconds)
                    
                except (AuthKeyUnregisteredError, AuthKeyInvalidError, UnauthorizedError) as e:
                    self.logger.critical(f"❌ Error crítico de autorización: {e}")
                    self._reconnecting = False
                    raise e
                    
                except (ConnectionAbortedError, ConnectionResetError, ConnectionError) as e:
                    self.logger.warning(f"💥 Error de conexión abortada durante reconexión: {e}")
                    self._connection_abort_count += 1
                    # Forzar limpieza completa en el próximo intento
                    self._force_cleanup_on_reconnect = True
                    
                except Exception as e:
                    self.logger.warning(f"⚠️ Error durante reconexión: {e}")
                    self._last_connection_error = e
                
                if attempt < attempts - 1:
                    await asyncio.sleep(delay)
        
        self.logger.critical("❌ Todos los intentos de reconexión fallaron")
        self._reconnecting = False
        # Resetear contadores para futuras reconexiones
        self._connection_abort_count = min(self._connection_abort_count, 10)
        return False
    
    async def _total_telethon_annihilation(self):
        """Aniquilación total de Telethon sin piedad"""
        try:
            # 1. FORZAR desconexión sin piedad
            if hasattr(self, '_sender') and self._sender:
                try:
                    await self._sender.disconnect()
                except Exception:
                    pass
                    
            try:
                await super().disconnect()
            except Exception:
                pass
                
            # 2. RESETEAR flags internos por la fuerza
            self._connected = False
            if hasattr(self, '_authorized'):
                self._authorized = False
                
            # 3. ANIQUILAR tasks de keepalive
            if hasattr(self, '_keepalive_task') and self._keepalive_task:
                self._keepalive_task.cancel()
                self._keepalive_task = None
                
            self.logger.debug("💀 ANIQUILACIÓN TOTAL COMPLETADA")
            
        except Exception as e:
            self.logger.debug(f"⚠️ Error durante aniquilación: {e}")

    async def _force_connection_cleanup(self):
        """Limpieza agresiva específica para errores 103 y conexiones zombie"""
        try:
            self.logger.info("🧹 Iniciando limpieza agresiva para error 103/conexión zombie")
            
            # 1. Forzar desconexión usando el método nativo de Telethon
            try:
                if hasattr(self, '_sender') and self._sender:
                    # Intentar desconexión normal del sender primero
                    await self._sender.disconnect()
                    await asyncio.sleep(0.2)
            except Exception as e:
                self.logger.debug(f"🧹 Error en desconexión normal del sender: {e}")
            
            # 2. Usar disconnect nativo de Telethon
            try:
                await super().disconnect()
                await asyncio.sleep(0.3)
            except Exception as e:
                self.logger.debug(f"🧹 Error en desconexión super(): {e}")
                
            # 3. Resetear flags de estado interno básicos
            try:
                self._connected = False
                if hasattr(self, '_authorized'):
                    self._authorized = False
            except Exception as e:
                self.logger.debug(f"🧹 Error reseteando flags: {e}")
                
            # 4. Esperar para que la limpieza tome efecto
            await asyncio.sleep(1.0)  # Esperar más tiempo para errores 103
            
            self.logger.info("✅ Limpieza agresiva completada - listo para reconectar")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error durante limpieza agresiva: {e}")
            # Esperar de todos modos
            await asyncio.sleep(0.5)
    
    def _reset_connection_counters(self):
        """Resetear contadores de error cuando la conexión es exitosa"""
        self._current_retries = 0
        self._connection_abort_count = 0
        self._last_connection_error = None
        self._force_cleanup_on_reconnect = False
        self.logger.debug("📊 Contadores de conexión reseteados")
    
    async def _handle_connection_aborted(self):
        """Manejo específico para error 103 - SISTEMA MEJORADO"""
        self.logger.error("🚨 MANEJO DE ERROR 103 ACTIVADO")
        
        # Prevenir múltiples ejecuciones del manejo de error 103
        if getattr(self, '_handling_103', False):
            self.logger.info("🚨 Manejo de error 103 ya en progreso")
            return False
        
        self._handling_103 = True
        
        try:
            # Marcar específicamente error 103
            self._connection_abort_count += 1
            self._last_connection_error = "ConnectionAbortedError (103)"
            
            self.logger.error(f"🚨 Error 103 #{self._connection_abort_count} detectado")
            
            # PASO 1: Limpieza agresiva inmediata para error 103
            await self._aggressive_103_cleanup()
            
            # PASO 2: Intentos específicos para error 103
            success = await self._error_103_recovery()
            
            if success:
                self.logger.error("✅ ERROR 103 SUPERADO EXITOSAMENTE!")
                self._reset_connection_counters()
            else:
                self.logger.error("❌ Error 103 no pudo ser superado")
            
            return success
            
        finally:
            self._handling_103 = False
    
    async def _simple_reconnect(self):
        """Método simple de reconexión sin complejidad recursiva"""
        try:
            # 1. Desconectar si está conectado
            if self.is_connected():
                await super().disconnect()
                await asyncio.sleep(1.0)
            
            # 2. Reconectar con método simple
            await super().connect()
            
            # 3. Verificar que la conexión funciona
            if self.is_connected():
                try:
                    await asyncio.wait_for(self.get_me(), timeout=5.0)
                    self._disable_native_systems()
                    return True
                except Exception as e:
                    self.logger.warning(f"Conexión establecida pero no funcional: {e}")
                    return False
            else:
                return False
                
        except Exception as e:
            self.logger.error(f"Error en reconexión simple: {e}")
            return False

    async def _handle_reconnection(self, attempts=None, delay=None):
        """Sistema paulatino de reconexión sin recursión"""
        if self._reconnecting:
            self.logger.info("🔄 Reconexión ya en progreso")
            return False
            
        self._reconnecting = True
        
        try:
            self.logger.warning("🚀 Iniciando sistema de reconexión paulatino")
            
            # Usar el sistema paulatino existente
            for phase_index, (phase_attempts, phase_delay) in enumerate(self.retries):
                self.logger.info(f"📊 Fase {phase_index + 1}: {phase_attempts} intentos cada {phase_delay}s")
                
                for attempt in range(phase_attempts):
                    try:
                        self.logger.info(f"🔄 Intento {attempt + 1}/{phase_attempts} de fase {phase_index + 1}")
                        
                        # Limpieza antes del intento
                        await self._force_connection_cleanup()
                        await asyncio.sleep(1)
                        
                        # Intentar conexión
                        await super().connect()
                        
                        if self.is_connected():
                            # Probar funcionalidad
                            await asyncio.wait_for(self.get_me(), timeout=5.0)
                            self._disable_native_systems()
                            
                            self.logger.info("✅ Reconexión paulatina exitosa!")
                            self._reset_connection_counters()
                            return True
                            
                    except Exception as e:
                        self.logger.warning(f"❌ Intento falló: {e}")
                        if attempt < phase_attempts - 1:
                            await asyncio.sleep(phase_delay)
                
                # Si esta fase falló completamente, esperar antes de la siguiente
                if phase_index < len(self.retries) - 1:
                    self.logger.warning(f"⏳ Fase {phase_index + 1} fallida, esperando antes de siguiente fase")
                    await asyncio.sleep(phase_delay * 2)
            
            self.logger.error("❌ Todas las fases de reconexión fallaron")
            return False
            
        finally:
            self._reconnecting = False

    async def _aggressive_103_cleanup(self):
        """Limpieza ultra-agresiva específica para error 103"""
        self.logger.error("🧹 LIMPIEZA AGRESIVA ERROR 103")
        
        try:
            # Cancelar cualquier tarea pendiente
            if hasattr(self, '_sender') and self._sender:
                try:
                    # Forzar desconexión del sender
                    await self._sender.disconnect()
                    self.logger.debug("🧹 Sender desconectado")
                except:
                    pass
            
            # Desconexión forzada del cliente
            try:
                await super().disconnect()
                self.logger.debug("🧹 Cliente desconectado")
            except:
                pass
            
            # Resetear flags manualmente
            self._connected = False
            if hasattr(self, '_authorized'):
                self._authorized = False
            
            # Espera específica para error 103
            await asyncio.sleep(2.0)
            
            self.logger.error("✅ Limpieza agresiva 103 completada")
            
        except Exception as e:
            self.logger.error(f"⚠️ Error durante limpieza 103: {e}")
    
    async def _error_103_recovery(self):
        """Sistema de recuperación específico para error 103"""
        self.logger.error("🔄 INICIANDO RECUPERACIÓN ERROR 103")
        
        # Configuración específica para error 103
        max_attempts = 5
        base_delay = 1.0
        
        for attempt in range(1, max_attempts + 1):
            self.logger.error(f"🚨 RECUPERACIÓN 103 - Intento {attempt}/{max_attempts}")
            
            try:
                # Configurar parámetros anti-reconexión nativa
                self._auto_reconnect = False
                
                # Intentar reconexión directa
                await super().connect()
                
                # Verificar conexión inmediatamente
                if self.is_connected():
                    # Test funcional con timeout corto para error 103
                    try:
                        await asyncio.wait_for(self.get_me(), timeout=3.0)
                        
                        # Deshabilitar sistemas nativos inmediatamente
                        self._disable_native_systems()
                        
                        self.logger.error("✅ RECUPERACIÓN 103 EXITOSA!")
                        return True
                        
                    except asyncio.TimeoutError:
                        self.logger.error(f"❌ Timeout en test - intento {attempt}")
                    except Exception as test_e:
                        self.logger.error(f"❌ Test falló: {test_e}")
                else:
                    self.logger.error(f"❌ Conexión no establecida - intento {attempt}")
                    
            except Exception as conn_e:
                self.logger.error(f"❌ Error conexión intento {attempt}: {conn_e}")
            
            # Esperar antes del siguiente intento (incrementalmente)
            if attempt < max_attempts:
                delay = base_delay * attempt
                self.logger.error(f"⏳ Esperando {delay}s antes del siguiente intento...")
                await asyncio.sleep(delay)
        
        self.logger.error("❌ RECUPERACIÓN 103 FALLÓ COMPLETAMENTE")
        return False

    async def _aggressive_reconnection_takeover(self, force=False):
        """MI SISTEMA de reconexión ULTRA AGRESIVO - optimizado para ERROR 103"""
        
        # DETECTAR si es específicamente error 103
        is_error_103 = ('103' in str(self._last_connection_error or '') or 
                       self._connection_abort_count > 0)
        
        if is_error_103:
            self.logger.error("🚀 RECONEXIÓN AGRESIVA ESPECÍFICA para ERROR 103")
        else:
            self.logger.warning("🚀 RECONEXIÓN AGRESIVA GENÉRICA")
        
        # PASO 1: ANIQUILAR todo lo que quede de Telethon INMEDIATAMENTE
        await self._total_telethon_annihilation()
        
        # PASO 2: ESPERA ESPECÍFICA para error 103
        if is_error_103:
            if force:
                await asyncio.sleep(0.4)  # ERROR 103 forzado: espera mínima
            else:
                await asyncio.sleep(1.2)  # ERROR 103: espera moderada
        else:
            # Otros errores
            await asyncio.sleep(0.8)
        
        # PASO 3: INTENTOS ESPECÍFICOS para error 103
        max_attempts = 7 if is_error_103 else 5  # Más intentos para error 103
        
        for attempt in range(1, max_attempts + 1):
            if is_error_103:
                self.logger.error(f"🚨 INTENTO ESPECÍFICO 103: {attempt}/{max_attempts}")
            else:
                self.logger.warning(f"⚡ INTENTO AGRESIVO: {attempt}/{max_attempts}")
            
            try:
                # PASO A: RECONEXIÓN DIRECTA
                await super().connect()
                
                # PASO B: VERIFICAR que conectó REALMENTE
                if not super().is_connected():
                    raise Exception("Conexión no establecida después de super().connect()")
                
                # PASO C: INMEDIATAMENTE tomar control TOTAL
                self._setup_complete_override()  # ANIQUILAR sistemas nativos
                self._disable_native_systems()   # DESHABILITAR todo
                
                # PASO D: VERIFICAR que mi interceptor está activo
                if hasattr(self, '_sender') and self._sender:
                    if not hasattr(self._sender, 'send') or self._sender.send.__name__ != '_error_103_interceptor':
                        if is_error_103:
                            self.logger.warning("🔧 Reactivando interceptor 103 tras reconexión")
                        self._reactivate_error_103_interceptor()
                
                # PASO E: TEST FUNCIONAL optimizado para error 103
                try:
                    # Timeout específico para error 103
                    timeout = 1.8 if is_error_103 else 2.5
                    test_result = await asyncio.wait_for(self.get_me(), timeout=timeout)
                    
                    if test_result:
                        if is_error_103:
                            self.logger.error("🚨 ERROR 103 SUPERADO EXITOSAMENTE!")
                        else:
                            self.logger.info("⚡ RECONEXIÓN AGRESIVA EXITOSA!")
                        
                        self._reset_connection_counters()
                        self._reconnecting = False
                        return True
                    else:
                        raise Exception("get_me() retornó None")
                        
                except asyncio.TimeoutError:
                    if is_error_103:
                        self.logger.error("❌ Test 103 timeout - reintentando")
                    else:
                        self.logger.warning("❌ Test timeout - reintentando")
                except Exception as test_error:
                    if is_error_103:
                        self.logger.error(f"❌ Test 103 falló: {test_error}")
                    else:
                        self.logger.warning(f"❌ Test falló: {test_error}")
                        
            except Exception as e:
                if is_error_103:
                    self.logger.error(f"❌ Intento 103 #{attempt} falló: {e}")
                else:
                    self.logger.warning(f"❌ Intento #{attempt} falló: {e}")
                
            # Espera específica entre intentos para error 103
            if attempt < max_attempts:
                delay = 0.3 if is_error_103 else 0.5
                await asyncio.sleep(delay)
        
        if is_error_103:
            self.logger.error("❌ TODOS los intentos específicos para ERROR 103 FALLARON")
        else:
            self.logger.error("❌ TODOS los intentos agresivos fallaron")
        
        self._reconnecting = False
        return False
    
    async def _total_telethon_annihilation(self):
        """ANIQUILAR COMPLETAMENTE todo rastro de Telethon activo"""
        self.logger.warning("💀 ANIQUILACIÓN TOTAL DE TELETHON EN PROGRESO")
        
        try:
            # FORZAR desconexión completa sin piedad
            if hasattr(self, '_sender') and self._sender:
                try:
                    await self._sender.disconnect()
                except:
                    pass
            
            try:
                await super().disconnect()
            except:
                pass
                
            # RESETEAR flags internos por la fuerza
            self._connected = False
            if hasattr(self, '_authorized'):
                self._authorized = False
                
            # ANIQUILAR tasks de keepalive si existen
            if hasattr(self, '_keepalive_task') and self._keepalive_task:
                self._keepalive_task.cancel()
                self._keepalive_task = None
                
        except Exception as e:
            self.logger.debug(f"⚠️ Error en aniquilación: {e}")
        
        self.logger.warning("💀 ANIQUILACIÓN COMPLETA TERMINADA")
    
    async def _emergency_103_recovery(self):
        """SISTEMA DE EMERGENCIA ESPECÍFICO para error 103 - MÁXIMA PRIORIDAD"""
        import asyncio
        
        self.logger.error("🚨 SISTEMA DE EMERGENCIA 103 ACTIVADO")
        
        # PREVENIR múltiples activaciones
        if hasattr(self, '_emergency_103_active') and self._emergency_103_active:
            self.logger.warning("⚠️ Emergencia 103 ya activa - ignorando")
            return
        
        self._emergency_103_active = True
        
        try:
            # PASO 1: ANIQUILACIÓN INMEDIATA Y COMPLETA
            self.logger.error("🚨 PASO 1: Aniquilación de emergencia para 103")
            await self._total_telethon_annihilation()
            
            # PASO 2: ESPERA MÍNIMA para estabilización
            await asyncio.sleep(0.8)
            
            # PASO 3: RECONEXIÓN DE EMERGENCIA ULTRA RÁPIDA
            self.logger.error("🚨 PASO 3: Reconexión de emergencia 103")
            
            for emergency_attempt in range(1, 4):  # Solo 3 intentos rápidos
                self.logger.error(f"🚨 INTENTO EMERGENCIA 103: {emergency_attempt}/3")
                
                try:
                    # RECONEXIÓN DIRECTA sin verificaciones previas
                    await super().connect()
                    
                    # CONTROL INMEDIATO
                    self._setup_complete_override()
                    self._disable_native_systems()
                    
                    # TEST ULTRA RÁPIDO
                    if self.is_connected():
                        try:
                            await asyncio.wait_for(self.get_me(), timeout=1.5)
                            self.logger.error("🚨 EMERGENCIA 103 RESUELTA EXITOSAMENTE!")
                            
                            # RESETEAR todo
                            self._reset_connection_counters()
                            self._reconnecting = False
                            self._emergency_103_active = False
                            return True
                            
                        except asyncio.TimeoutError:
                            self.logger.error("❌ Test emergencia timeout")
                        except Exception as test_e:
                            self.logger.error(f"❌ Test emergencia falló: {test_e}")
                    
                except Exception as conn_e:
                    self.logger.error(f"❌ Intento emergencia {emergency_attempt} falló: {conn_e}")
                
                # Espera MUY corta entre intentos
                if emergency_attempt < 3:
                    await asyncio.sleep(0.3)
            
            self.logger.error("❌ TODOS los intentos de emergencia 103 FALLARON")
            
        except Exception as emergency_error:
            self.logger.error(f"❌ ERROR CRÍTICO en emergencia 103: {emergency_error}")
        finally:
            self._emergency_103_active = False
            
        return False

    def disconnect(self):
        """Desconexión controlada compatible con sync/async"""
        import asyncio
        
        async def _async_disconnect():
            try:
                if self.is_connected():
                    self.logger.info("🔌 Desconectando cliente...")
                    await super(CustomTelegramClient, self).disconnect()
                    self.logger.info("✅ Cliente desconectado")
            except Exception as e:
                self.logger.warning(f"⚠️ Error durante desconexión: {e}")
        
        # Si estamos en un loop de asyncio activo, retornar una corrutina
        try:
            loop = asyncio.get_running_loop()
            if loop and loop.is_running():
                # Retornar la corrutina para que pueda ser awaited
                return _async_disconnect()
        except RuntimeError:
            # No hay loop activo, ejecutar sincrónicamente
            pass
        
        # Ejecutar sincrónicamente si no hay loop activo
        try:
            if self.is_connected():
                self.logger.info("🔌 Desconectando cliente (sync)...")
                # Usar versión sincrónica básica
                if hasattr(self, '_sender') and self._sender:
                    try:
                        self._sender.disconnect()
                    except Exception:
                        pass
                self.logger.info("✅ Cliente desconectado (sync)")
        except Exception as e:
            self.logger.warning(f"⚠️ Error durante desconexión sync: {e}")
        
        return None
    
    async def disconnect_async(self):
        """Versión async explícita para uso interno"""
        try:
            if self.is_connected():
                self.logger.info("🔌 Desconectando cliente (async explícito)...")
                await super().disconnect()
                self.logger.info("✅ Cliente desconectado (async explícito)")
        except Exception as e:
            self.logger.warning(f"⚠️ Error durante desconexión async explícito: {e}")
    
    def _setup_complete_override(self):
        """ANIQUILAR COMPLETAMENTE todos los sistemas nativos de Telethon"""
        
        # ANIQUILAR keepalive completamente
        def _kill_keepalive(*args, **kwargs):
            self.logger.debug("💀 Keepalive nativo ANIQUILADO completamente")
            return None
        
        async def _kill_keepalive_async(*args, **kwargs):
            self.logger.debug("💀 Keepalive async nativo ANIQUILADO completamente")  
            return None
            
        # SOBRESCRIBIR AGRESIVAMENTE todos los métodos del cliente
        methods_to_kill_client = [
            '_keepalive_loop', 'keepalive_loop', '_keepalive_task', 'keepalive_task',
            '_auto_reconnect', 'auto_reconnect', '_connection_retries', 'connection_retries',
            '_retry_delay', 'retry_delay', '_reconnect', 'reconnect'
        ]
        
        for method_name in methods_to_kill_client:
            if hasattr(self, method_name):
                if 'async' in method_name or 'loop' in method_name or 'task' in method_name:
                    setattr(self, method_name, _kill_keepalive_async)
                else:
                    # Para propiedades booleanas y numéricas, forzar valores
                    if 'reconnect' in method_name:
                        setattr(self, method_name, False)
                    elif 'retries' in method_name or 'delay' in method_name:
                        setattr(self, method_name, 0)
                    else:
                        setattr(self, method_name, _kill_keepalive)
                        
                self.logger.debug(f"💀 Método cliente {method_name} ANIQUILADO")
        
        # ANIQUILAR métodos críticos de reconexiones
        self._override_sender_methods()
        
        self.logger.warning("💀 TODOS los sistemas nativos del cliente ANIQUILADOS")
        
    # ELIMINADO: async def _dummy_keepalive_loop() - ANIQUILADO completamente
    
    def _disable_native_systems(self):
        """Deshabilitar agresivamente todos los sistemas nativos de reconexión"""
        try:
            # Cancelar cualquier task de keepalive activo
            if hasattr(self, '_keepalive_task') and self._keepalive_task:
                self._keepalive_task.cancel()
                self._keepalive_task = None
                
            # Deshabilitar a nivel de sender si existe
            if hasattr(self, '_sender') and self._sender:
                # Configuraciones básicas de reconexión
                if hasattr(self._sender, '_auto_reconnect'):
                    self._sender._auto_reconnect = False
                if hasattr(self._sender, '_retries'):
                    self._sender._retries = 0
                if hasattr(self._sender, '_retry_delay'):
                    self._sender._retry_delay = 0
                    
                # Configuraciones adicionales que podrían existir
                for attr in ['auto_reconnect', 'connection_retries', 'retry_delay']:
                    if hasattr(self._sender, attr):
                        setattr(self._sender, attr, False if 'reconnect' in attr else 0)
                        
                # Deshabilitar a nivel de conexión si existe
                if hasattr(self._sender, '_connection') and self._sender._connection:
                    conn = self._sender._connection
                    for attr in ['_auto_reconnect', 'auto_reconnect', '_retries', 'retries']:
                        if hasattr(conn, attr):
                            setattr(conn, attr, False if 'reconnect' in attr else 0)
                    
            # Forzar configuración a nivel de cliente
            self._auto_reconnect = False
            if hasattr(self, 'connection_retries'):
                self.connection_retries = 0
                
            self.logger.debug("🚫 Sistemas nativos de Telethon completamente deshabilitados")
        except Exception as e:
            self.logger.debug(f"⚠️ Error deshabilitando sistemas nativos: {e}")
    
    def _override_sender_methods(self):
        """Sobrescribir métodos específicos del MTProtoSender"""
        import asyncio
        
        # DESTRUIR COMPLETAMENTE todos los métodos nativos de reconexión
        def _kill_native_reconnection(*args, **kwargs):
            """ANIQUILAR cualquier intento de reconexión nativa"""
            self.logger.warning("💀 RECONEXIÓN NATIVA BLOQUEADA - usando sistema personalizado")
            return False
            
        async def _kill_native_reconnection_async(*args, **kwargs):
            """ANIQUILAR cualquier intento async de reconexión nativa"""  
            self.logger.warning("💀 RECONEXIÓN ASYNC NATIVA BLOQUEADA - usando sistema personalizado")
            return False
            
        def _kill_keepalive(*args, **kwargs):
            """ANIQUILAR keepalive nativo"""
            self.logger.debug("💀 Keepalive nativo ANIQUILADO")
            return None
            
        # SOBRESCRIBIR AGRESIVAMENTE todos los métodos de reconexión
        if hasattr(self, '_sender') and self._sender:
            # Lista completa de métodos que hay que ANIQUILAR
            methods_to_kill = [
                'auto_reconnect', '_auto_reconnect', 'reconnect', '_reconnect',
                '_handle_auto_reconnect', 'handle_auto_reconnect', 
                '_try_reconnect', 'try_reconnect', '_reconnect_async', 'reconnect_async',
                '_connection_retries', 'connection_retries', '_retry_delay', 'retry_delay',
                '_keepalive_loop', 'keepalive_loop', '_keepalive_task', 'keepalive_task'
            ]
            
            for method_name in methods_to_kill:
                if hasattr(self._sender, method_name):
                    if 'async' in method_name or 'loop' in method_name:
                        setattr(self._sender, method_name, _kill_native_reconnection_async)
                    else:
                        setattr(self._sender, method_name, _kill_native_reconnection)
                    self.logger.debug(f"💀 Método {method_name} ANIQUILADO")
            
            # ANIQUILAR también a nivel de conexión
            if hasattr(self._sender, '_connection') and self._sender._connection:
                conn = self._sender._connection
                for method_name in methods_to_kill:
                    if hasattr(conn, method_name):
                        if 'async' in method_name or 'loop' in method_name:
                            setattr(conn, method_name, _kill_native_reconnection_async)
                        else:
                            setattr(conn, method_name, _kill_native_reconnection)
            
            self.logger.warning("💀 TODOS los métodos nativos de reconexión ANIQUILADOS")
        
        # INTERCEPTOR SEGURO: Sin crear tareas recursivas
        if hasattr(self, '_sender') and self._sender:
            # Guardar método original si no está guardado
            if not hasattr(self, '_original_sender_send'):
                self._original_sender_send = self._sender.send
                
            # INTERCEPTOR MEJORADO para error 103
            async def _error_103_interceptor(request, ordered=True, timeout=None):
                try:
                    return await self._original_sender_send(request, ordered, timeout)
                except (ConnectionAbortedError, ConnectionResetError, ConnectionError) as e:
                    error_msg = str(e).lower()
                    
                    # Detectar específicamente error 103
                    if '103' in error_msg or 'abort' in error_msg or 'software caused connection' in error_msg:
                        self.logger.error(f"🚨 ERROR 103 INTERCEPTADO: {e}")
                        
                        # Marcar error 103
                        self._connection_abort_count += 1
                        self._last_connection_error = f"Error 103 interceptado: {e}"
                        
                        # Activar manejo de error 103 en background SIN ESPERAR
                        if not getattr(self, '_handling_103', False):
                            import asyncio
                            asyncio.create_task(self._handle_connection_aborted())
                        
                        # Relanzar para que llegue a BaseClient.run()
                        raise ConnectionAbortedError(f"Error 103 detectado: {e}")
                    else:
                        # Otros errores de conexión
                        self.logger.warning(f"💥 Error conexión interceptado: {e}")
                        raise e
            
            # APLICAR interceptor seguro
            self._sender.send = _error_103_interceptor
            self.logger.warning("🚨 Interceptor 103 activado (sin recursión)")
        
        # Aplicar sobrescrituras en el próximo tick para asegurar que el sender existe
        if hasattr(self, 'loop') and self.loop:
            self.loop.call_soon(self._apply_sender_overrides)
    
    def _apply_sender_overrides(self):
        """Aplicar sobrescrituras mínimas al sender - SOLO desactivar reconexión"""
        try:
            if hasattr(self, '_sender') and self._sender:
                # SOLO deshabilitar auto_reconnect - NO tocar otros métodos
                if hasattr(self._sender, 'auto_reconnect'):
                    self._sender.auto_reconnect = False
                if hasattr(self._sender, '_auto_reconnect'):
                    self._sender._auto_reconnect = False
                    
                self.logger.debug("🚫 Reconexión de sender deshabilitada (sin tocar handlers)")
        except Exception as e:
            self.logger.debug(f"⚠️ Error deshabilitando reconexión de sender: {e}")

    def is_connected(self):
        """Verificación mejorada y más robusta del estado de conexión"""
        try:
            # Verificación básica primero
            base_connected = super().is_connected()
            if not base_connected:
                return False
            
            # Verificaciones adicionales para detectar conexiones zombie
            if hasattr(self, '_sender') and self._sender:
                try:
                    # Verificar si el sender está desconectado
                    if hasattr(self._sender, 'is_disconnected') and self._sender.is_disconnected():
                        return False
                        
                    # Verificar estado de la conexión del sender
                    if hasattr(self._sender, '_connection') and self._sender._connection:
                        conn = self._sender._connection
                        
                        # Verificar si la conexión tiene un socket válido
                        if hasattr(conn, '_socket') and conn._socket:
                            try:
                                # Verificar que el socket no esté cerrado
                                if conn._socket.fileno() == -1:
                                    return False
                            except (OSError, AttributeError):
                                return False
                                
                        # Verificar estado de conexión interno
                        if hasattr(conn, '_connected') and not conn._connected:
                            return False
                            
                    # Si el sender existe pero no tiene _connection, podría ser problemático
                    elif not hasattr(self._sender, '_connection') or not self._sender._connection:
                        # Permitir esto solo durante las fases iniciales de conexión
                        if hasattr(self._sender, '_connected') and not self._sender._connected:
                            return False
                            
                except (AttributeError, OSError, ConnectionError) as e:
                    self.logger.debug(f"🔍 Error verificando estado detallado de conexión: {e}")
                    # Si hay errores de conexión al verificar, probablemente no estamos conectados
                    return False
            
            return base_connected
            
        except Exception as e:
            # En caso de error, intentar verificación básica como fallback
            self.logger.debug(f"🔍 Error en verificación mejorada de conexión: {e}")
            try:
                return super().is_connected()
            except Exception:
                return False
                
    async def ping_connection(self, timeout: float = 5.0) -> bool:
        """Verificación activa de la conexión con timeout"""
        try:
            if not self.is_connected():
                return False
                
            # Hacer ping real con timeout
            await asyncio.wait_for(self.get_me(), timeout=timeout)
            return True
            
        except asyncio.TimeoutError:
            self.logger.debug(f"⏰ Ping timeout después de {timeout}s")
            return False
        except (ConnectionAbortedError, ConnectionResetError, ConnectionError) as e:
            self.logger.debug(f"💥 Error de conexión durante ping: {e}")
            self._last_connection_error = e
            self._connection_abort_count += 1
            return False
        except Exception as e:
            self.logger.debug(f"❌ Error durante ping: {e}")
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
            # Asegurar que los sistemas nativos siguen deshabilitados
            self._disable_native_systems()
            # Resetear contadores si todo está funcionando bien
            if self.is_connected():
                try:
                    # Verificar que la conexión funciona después de cargar plugins
                    loop = asyncio.get_event_loop()
                    if loop and not loop.is_closed():
                        loop.create_task(self._verify_post_plugin_connection())
                except Exception as e:
                    self.logger.debug(f"⚠️ No se pudo programar verificación post-plugins: {e}")
                    
    async def _verify_post_plugin_connection(self):
        """Verificar que la conexión sigue funcionando después de cargar plugins"""
        try:
            await asyncio.sleep(2)  # Esperar que los plugins se estabilicen
            if await self.ping_connection(timeout=3.0):
                self.logger.debug("✅ Conexión verificada exitosamente después de cargar plugins")
                self._reset_connection_counters()
            else:
                self.logger.warning("⚠️ Conexión no responde después de cargar plugins")
                if not self._reconnecting:
                    self.logger.info("🔄 Activando reconexión preventiva post-plugins")
                    asyncio.create_task(self._handle_reconnection())
        except Exception as e:
            self.logger.debug(f"⚠️ Error verificando conexión post-plugins: {e}")







