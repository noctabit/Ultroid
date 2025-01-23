import logging
import asyncio
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError
from telethon.sessions import StringSession
import struct
import base64
import ipaddress
import sys

# Configuraciones para Data Centers
DC_IPV4 = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}
_STRUCT_PREFORMAT = ">BI?256sQ?"

def validate_session(session, logger, _exit=True):
    """Valida y convierte sesiones en un formato estándar (como en Código 2)."""
    from strings import get_string

    if session:
        # Telethon Session
        if session.startswith("1"):  # Verifica si la sesión es Telethon
            if len(session.strip()) != 353:
                logger.exception(get_string("py_c1"))
                if _exit:
                    sys.exit()
            return StringSession(session)

        # Pyrogram Session
        elif len(session) in [351, 356, 362]:  # Verifica si la sesión es Pyrogram
            try:
                data_ = struct.unpack(
                    _STRUCT_PREFORMAT,
                    base64.urlsafe_b64decode(session + "=" * (-len(session) % 4)),
                )
                if len(session) in [351, 356]:
                    auth_id = 2
                else:
                    auth_id = 3
                dc_id, auth_key = data_[0], data_[auth_id]
                return StringSession(
                    "1"
                    + base64.urlsafe_b64encode(
                        struct.pack(
                            _STRUCT_PREFORMAT.format(4),
                            dc_id,
                            ipaddress.ip_address(DC_IPV4[dc_id]).packed,
                            443,
                            auth_key,
                        )
                    ).decode("ascii")
                )
            except Exception as e:
                logger.exception(get_string("py_c1"))
                if _exit:
                    sys.exit()
        else:
            logger.exception(get_string("py_c1"))
            if _exit:
                sys.exit()
    logger.exception(get_string("py_c2"))
    if _exit:
        sys.exit()


class CustomTelegramClient(TelegramClient):
    def __init__(self, session, *args, logger=None, **kwargs):
        kwargs["auto_reconnect"] = False  # Desactivar reconexión automática
        super().__init__(validate_session(session, logger), *args, **kwargs)
        self.logger = logger or logging.getLogger("Reconnections")
        self.retries = [
            (10, 10),  # 10 intentos cada 10 segundos
            (10, 60),  # 10 intentos cada 1 minuto
            (10, 300),  # 10 intentos cada 5 minutos
            (10, 900),  # 10 intentos cada 15 minutos
            (10, 1800),  # 10 intentos cada 30 minutos
            (10, 3600),  # 10 intentos cada hora
        ]

    async def connect(self):
        """Sobreescribe la conexión para utilizar lógica personalizada."""
        self.logger.info("Intentando conectar a Telegram con lógica personalizada...")
        try:
            await super().connect()
            if self.is_connected():
                self.logger.info("Conexión exitosa a Telegram. Estado: True")
            else:
                self.logger.warning("Conexión no establecida correctamente. Estado: False")
        except Exception as e:
            self.logger.error(f"Fallo en la conexión inicial: {e}")
            await self.on_disconnect()

    async def on_disconnect(self):
        """Manejo de la reconexión con estrategia personalizada."""
        self.logger.warning("Se ha detectado una desconexión. Iniciando reconexión progresiva.")
        for attempt_group, delay in self.retries:
            for attempt in range(attempt_group):
                try:
                    if not self.is_connected():
                        self.logger.info(
                            f"Intento de reconexión {attempt + 1}/{attempt_group} "
                            f"(intervalo: {delay}s). Estado actual: False"
                        )
                        await asyncio.sleep(delay)
                        await self.connect()
                        if self.is_connected():
                            self.logger.info("¡Reconexión exitosa! Estado: True")
                            return
                    else:
                        self.logger.info("El cliente ya está conectado. Estado: True")
                        return
                except Exception as e:
                    self.logger.error(f"Error durante el intento de reconexión: {e}")
        self.logger.critical("Todos los intentos de reconexión fallaron. Requiere intervención manual.")






