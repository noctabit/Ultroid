# Ultroid - UserBot
# Copyright (C) 2021-2023 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import contextlib
import inspect
import sys
import time
import logging


from telethon import utils as telethon_utils
from telethon.errors import (
    AccessTokenExpiredError,
    AccessTokenInvalidError,
    ApiIdInvalidError,
    AuthKeyDuplicatedError,
)

from ..configs import Var
from .reconnections import CustomTelegramClient


logger = logging.getLogger(__name__)  # Crear la instancia de logger

class UltroidClient(CustomTelegramClient):  # Cambiado para heredar de CustomTelegramClient
    def __init__(
        self,
        session,
        api_id=None,
        api_hash=None,
        bot_token=None,
        udB=None,
        logger: logging.Logger = logger,  # Usar logging.Logger en la anotación
        log_attempt=True,
        exit_on_error=True,
        *args,
        **kwargs,
    ):
        self._cache = {}
        self._dialogs = []
        self._handle_error = exit_on_error
        self._log_at = log_attempt
        self.logger = logger
        self.udB = udB
        kwargs["api_id"] = api_id or Var.API_ID
        kwargs["api_hash"] = api_hash or Var.API_HASH
        kwargs["logger"] = self.logger  # Pasar logger a CustomTelegramClient
        # Inicializar heartbeat task ANTES de llamar al parent
        self._heartbeat_task = None
        super().__init__(session, **kwargs)
        self.run_in_loop(self.start_client(bot_token=bot_token))
        self.dc_id = self.session.dc_id

    def __repr__(self):
        return f"<Ultroid.Client :\n self: {self.full_name}\n bot: {self._bot}\n>"

    @property
    def __dict__(self):
        if self.me:
            return self.me.to_dict()

    async def start_client(self, **kwargs):
        """function to start client with improved error handling"""
        if self._log_at:
            self.logger.info("Trying to login.")
        try:
            await self.start(**kwargs)
        except ApiIdInvalidError:
            self.logger.critical("❌ API ID and API_HASH combination does not match!")
            sys.exit()
        except (AuthKeyDuplicatedError, EOFError) as er:
            if self._handle_error:
                self.logger.critical("❌ String session expired. Create new!")
                return sys.exit()
            self.logger.critical("⚠️ String session expired.")
        except (AccessTokenExpiredError, AccessTokenInvalidError):
            # AccessTokenError can only occur for Bot account
            # And at Early Process, Its saved in DB.
            if self.udB:
                self.udB.del_key("BOT_TOKEN")
            self.logger.critical(
                "❌ Bot token is expired or invalid. Create new from @Botfather and add in BOT_TOKEN env variable!"
            )
            sys.exit()
        except Exception as e:
            self.logger.error(f"❌ Unexpected error during start_client: {e}")
            if self._handle_error:
                raise e
        
        # Save some stuff for later use...
        try:
            self.me = await self.get_me()
            if self.me.bot:
                me = f"@{self.me.username}"
            else:
                setattr(self.me, "phone", None)
                me = self.full_name
            if self._log_at:
                self.logger.info(f"✅ Logged in as {me}")
            self._bot = await self.is_bot()
            # Iniciar nuestro sistema mejorado de heartbeat después de la conexión exitosa
            # Pero no durante la carga inicial de plugins
            self._start_heartbeat_when_ready()
        except Exception as e:
            self.logger.error(f"❌ Error getting user info: {e}")
            if self._handle_error:
                raise e

    async def fast_uploader(self, file, **kwargs):
        """Upload files in a faster way"""

        import os
        from pathlib import Path

        start_time = time.time()
        path = Path(file)
        filename = kwargs.get("filename", path.name)
        # Set to True and pass event to show progress bar.
        show_progress = kwargs.get("show_progress", False)
        if show_progress:
            event = kwargs["event"]
        # Whether to use cached file for uploading or not
        use_cache = kwargs.get("use_cache", True)
        # Delete original file after uploading
        to_delete = kwargs.get("to_delete", False)
        message = kwargs.get("message", f"Uploading {filename}...")
        by_bot = self._bot
        size = os.path.getsize(file)
        # Don't show progress bar when file size is less than 5MB.
        if size < 5 * 2 ** 20:
            show_progress = False
        if use_cache and self._cache and self._cache.get("upload_cache"):
            for files in self._cache["upload_cache"]:
                if (
                    files["size"] == size
                    and files["path"] == path
                    and files["name"] == filename
                    and files["by_bot"] == by_bot
                ):
                    if to_delete:
                        with contextlib.suppress(FileNotFoundError):
                            os.remove(file)
                    return files["raw_file"], time.time() - start_time
        from pyUltroid.fns.FastTelethon import upload_file
        from pyUltroid.fns.helper import progress

        raw_file = None
        while not raw_file:
            with open(file, "rb") as f:
                raw_file = await upload_file(
                    client=self,
                    file=f,
                    filename=filename,
                    progress_callback=(
                        lambda completed, total: self.loop.create_task(
                            progress(completed, total, event, start_time, message)
                        )
                    )
                    if show_progress
                    else None,
                )
        cache = {
            "by_bot": by_bot,
            "size": size,
            "path": path,
            "name": filename,
            "raw_file": raw_file,
        }
        if self._cache.get("upload_cache"):
            self._cache["upload_cache"].append(cache)
        else:
            self._cache.update({"upload_cache": [cache]})
        if to_delete:
            with contextlib.suppress(FileNotFoundError):
                os.remove(file)
        return raw_file, time.time() - start_time

    async def fast_downloader(self, file, **kwargs):
        """Download files in a faster way"""
        # Set to True and pass event to show progress bar.
        show_progress = kwargs.get("show_progress", False)
        filename = kwargs.get("filename", "")
        if show_progress:
            event = kwargs["event"]
        # Don't show progress bar when file size is less than 10MB.
        if file.size < 10 * 2 ** 20:
            show_progress = False
        import mimetypes

        from telethon.tl.types import DocumentAttributeFilename

        from pyUltroid.fns.FastTelethon import download_file
        from pyUltroid.fns.helper import progress

        start_time = time.time()
        # Auto-generate Filename
        if not filename:
            try:
                if isinstance(file.attributes[-1], DocumentAttributeFilename):
                    filename = file.attributes[-1].file_name
            except IndexError:
                mimetype = file.mime_type
                filename = (
                    mimetype.split("/")[0]
                    + "-"
                    + str(round(start_time))
                    + mimetypes.guess_extension(mimetype)
                )
        message = kwargs.get("message", f"Downloading {filename}...")

        raw_file = None
        while not raw_file:
            with open(filename, "wb") as f:
                raw_file = await download_file(
                    client=self,
                    location=file,
                    out=f,
                    progress_callback=(
                        lambda completed, total: self.loop.create_task(
                            progress(completed, total, event, start_time, message)
                        )
                    )
                    if show_progress
                    else None,
                )
        return raw_file, time.time() - start_time

    def run_in_loop(self, function):
        """run inside asyncio loop"""
        return self.loop.run_until_complete(function)

    def run(self):
        """run asyncio loop"""
        self.run_until_disconnected()

    def add_handler(self, func, *args, **kwargs):
        """Add new event handler, ignoring if exists"""
        if func in [_[0] for _ in self.list_event_handlers()]:
            return
        self.add_event_handler(func, *args, **kwargs)

    @property
    def utils(self):
        return telethon_utils

    @property
    def full_name(self):
        """full name of Client"""
        return self.utils.get_display_name(self.me)

    @property
    def uid(self):
        """Client's user id"""
        return self.me.id

    def _start_heartbeat_when_ready(self):
        """Iniciar heartbeat después de que el cliente esté completamente conectado"""
        import asyncio
        # Programar el heartbeat para la próxima iteración del event loop
        # Esperar un poco más para asegurar que la conexión está estable
        if hasattr(self, 'loop') and self.loop:
            self.loop.call_later(3, self._init_heartbeat_task)
    
    def prepare_for_plugin_loading(self):
        """Preparar cliente para carga de plugins sin interferencias"""
        if hasattr(self, 'set_plugin_loading_state'):
            self.set_plugin_loading_state(True)
            
    def complete_plugin_loading(self):
        """Completar carga de plugins y reactivar sistema de reconexión"""
        if hasattr(self, 'set_plugin_loading_state'):
            self.set_plugin_loading_state(False)
        
    def _init_heartbeat_task(self):
        """Inicializar el task del heartbeat de forma segura"""
        import asyncio
        try:
            if self._heartbeat_task is None:
                self._heartbeat_task = self.loop.create_task(self._heartbeat_loop())
                self.logger.info("💓 Sistema de heartbeat mejorado iniciado")
        except Exception as e:
            self.logger.warning(f"💓 Error al iniciar heartbeat: {e}")

    async def _heartbeat_loop(self):
        """Loop de heartbeat mejorado para mantener conexión activa"""
        import asyncio
        heartbeat_interval = 30  # 30 segundos
        consecutive_failures = 0
        max_failures = 2  # Permitir 2 fallos antes de reconectar
        
        # Espera inicial para permitir que la conexión se estabilice
        await asyncio.sleep(10)
        
        while True:
            try:
                await asyncio.sleep(heartbeat_interval)
                
                # No verificar durante la carga de plugins
                if getattr(self, '_plugin_loading', False):
                    self.logger.debug("💓 Heartbeat pausado durante carga de plugins")
                    continue
                
                # Verificación mejorada de conexión
                if not self.is_connected():
                    consecutive_failures += 1
                    self.logger.debug(f"💓 Heartbeat: Conexión perdida (fallo {consecutive_failures}/{max_failures})")
                    
                    if consecutive_failures >= max_failures:
                        self.logger.warning("💓 Heartbeat: Conexión perdida, activando reconexión")
                        # Activar nuestro sistema de reconexión personalizado
                        if hasattr(self, '_handle_reconnection') and not getattr(self, '_reconnecting', False):
                            asyncio.create_task(self._handle_reconnection())
                        break
                else:
                    # Ping ligero para mantener la conexión activa
                    try:
                        await self.get_me()
                        consecutive_failures = 0  # Reset contador al tener éxito
                        self.logger.debug("💓 Heartbeat: Conexión activa")
                    except Exception as e:
                        consecutive_failures += 1
                        self.logger.debug(f"💓 Heartbeat ping falló (fallo {consecutive_failures}/{max_failures}): {e}")
                        
                        if consecutive_failures >= max_failures:
                            self.logger.warning("💓 Heartbeat: Múltiples fallos de ping, activando reconexión")
                            if hasattr(self, '_handle_reconnection') and not getattr(self, '_reconnecting', False):
                                asyncio.create_task(self._handle_reconnection())
                            break
                        
            except asyncio.CancelledError:
                self.logger.info("💓 Heartbeat cancelado")
                break
            except Exception as e:
                self.logger.error(f"💓 Error en heartbeat: {e}")
                await asyncio.sleep(10)  # Esperar antes de reintentar

    def stop_heartbeat(self):
        """Detener el sistema de heartbeat"""
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()
            self._heartbeat_task = None
            self.logger.info("💓 Heartbeat detenido")

    def to_dict(self):
        return dict(inspect.getmembers(self))

    async def parse_id(self, text):
        with contextlib.suppress(ValueError):
            text = int(text)
        return await self.get_peer_id(text)
