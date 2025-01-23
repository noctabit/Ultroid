import logging
import asyncio
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError
from telethon.sessions import StringSession
import struct
import base64
import ipaddress

# Configuraciones para Data Centers
DC_IPV4 = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}
_STRUCT_PREFORMAT = ">BI?256sQ?"

def validate_session(session, logger):
    """Valida y convierte sesiones en un formato estándar."""
    if session.startswith("1"):  # Sesión Telethon
        if len(session) != 353:
            logger.error("Sesión Telethon inválida. Longitud incorrecta.")
            raise ValueError("Sesión Telethon inválida.")
        return StringSession(session)

    elif len(session) in {351, 356, 362}:  # Sesión Pyrogram
        try:
            data = struct.unpack(
                _STRUCT_PREFORMAT,
                base64.urlsafe_b64decode(session + "=" * (-len(session) % 4)),
            )
            dc_id, auth_key = data[0], data[-1]
            return StringSession(
                "1" + base64.urlsafe_b64encode(
                    struct.pack(
                        _STRUCT_PREFORMAT,
                        dc_id,
                        ipaddress.ip_address(DC_IPV4[dc_id]).packed,
                        443,
                        auth_key,
                    )
                ).decode("ascii")
            )
        except Exception as e:
            logger.error(f"Error al validar sesión Pyrogram: {e}")
            raise ValueError("Sesión Pyrogram inválida.")
    else:
        logger.error("Formato de sesión no reconocido.")
        raise ValueError("Formato de sesión no reconocido.")


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






