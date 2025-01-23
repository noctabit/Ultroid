import logging
import asyncio
from telethon import TelegramClient

class CustomTelegramClient(TelegramClient):
    def __init__(self, *args, logger=None, **kwargs):
        super().__init__(*args, **kwargs)
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
                self.logger.info("Conexión exitosa a Telegram.")
        except Exception as e:
            self.logger.error(f"Fallo en la conexión inicial: {e}")
            await self.on_disconnect()

    async def disconnect(self):
        """Sobreescribe la desconexión para manejar la reconexión manualmente."""
        self.logger.warning("Desconectado de Telegram. Llamando a reconexión personalizada.")
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
                            f"(intervalo: {delay}s)"
                        )
                        await self.connect()
                        if self.is_connected():
                            self.logger.info("¡Reconexión exitosa!")
                            return
                    else:
                        self.logger.info("El cliente ya está conectado.")
                        return
                except Exception as e:
                    self.logger.warning(f"Fallo en el intento de reconexión: {e}")
                await asyncio.sleep(delay)
        self.logger.error("Todos los intentos de reconexión fallaron. Requiere intervención manual.")

