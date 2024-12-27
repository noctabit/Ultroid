# Ultroid - UserBot
# Copyright (C) 2021-2023 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.
"""
✘ Commands Available -

• `{i}gban <reply user/ username>`
• `{i}ungban`
    Ban/Unban Globally.

• `{i}gstat <reply to user/userid/username>`
   Check if user is GBanned.

• `{i}listgban` : List all GBanned users.

• `{i}gmute` | `{i}ungmute` <reply user/ username>
    Mute/UnMute Globally.

• `{i}gkick <reply/username>` `Globally Kick User`
• `{i}gcast <text/reply>` `Globally Send msg in all grps`

• `{i}gadmincast <text/reply>` `Globally broadcast in your admin chats`
• `{i}gucast <text/reply>` `Globally send msg in all pm users`

• `{i}gblacklist <chat id/username/nothing (for current chat)`
   Add chat to blacklist and ignores global broadcast.
• `{i}ungblacklist` `Remove the chat from blacklist.`

• `{i}gpromote <reply to user> <channel/group/all> <rank>`
    globally promote user where you are admin
    - Set whether To promote only in groups/channels/all.
    Eg- `gpromote group boss` ~ promotes user in all grps.
        `gpromote @username all sar` ~ promote the user in all group & channel
• `{i}gdemote` - `demote user globally`
"""

import asyncio
import os
import html
import time
from telethon.errors.rpcerrorlist import ChatAdminRequiredError, FloodWaitError
from telethon.tl.functions.channels import EditAdminRequest
from telethon.tl.functions.contacts import BlockRequest, UnblockRequest
from telethon.tl.types import ChatAdminRights, User

from pyUltroid.dB import DEVLIST
from pyUltroid.dB.base import KeyManager
from pyUltroid.dB.gban_mute_db import (
    gban,
    gmute,
    is_gbanned,
    is_gmuted,
    list_gbanned,
    ungban,
    ungmute,
)
from pyUltroid.fns.tools import create_tl_btn, format_btn, get_msg_button

from . import (
    HNDLR,
    LOGS,
    NOSPAM_CHAT,
    OWNER_NAME,
    eod,
    eor,
    get_string,
    inline_mention,
    ultroid_bot,
    ultroid_cmd,
)
from ._inline import something

_gpromote_rights = ChatAdminRights(
    add_admins=False,
    invite_users=True,
    change_info=False,
    ban_users=True,
    delete_messages=True,
    pin_messages=True,
)

_gdemote_rights = ChatAdminRights(
    add_admins=False,
    invite_users=False,
    change_info=False,
    ban_users=False,
    delete_messages=False,
    pin_messages=False,
)

keym = KeyManager("GBLACKLISTS", cast=list)


@ultroid_cmd(pattern="gpromote( (.*)|$)", fullsudo=True)
async def _(e):
    x = e.pattern_match.group(1).strip()
    ultroid_bot = e.client
    if not x:
        return await e.eor(get_string("schdl_2"), time=5)
    user = await e.get_reply_message()
    if user:
        ev = await e.eor("`Promoting Replied User Globally`")
        ok = e.text.split()
        key = "all"
        if len(ok) > 1 and (("group" in ok[1]) or ("channel" in ok[1])):
            key = ok[1]
        rank = ok[2] if len(ok) > 2 else "AdMin"
        c = 0
        user.id = user.peer_id.user_id if e.is_private else user.from_id.user_id
        async for x in e.client.iter_dialogs():
            if (
                "group" in key.lower()
                and x.is_group
                or "group" not in key.lower()
                and "channel" in key.lower()
                and x.is_channel
            ):
                try:
                    await e.client(
                        EditAdminRequest(
                            x.id,
                            user.id,
                            _gpromote_rights,
                            rank,
                        ),
                    )
                    c += 1
                except BaseException:
                    pass
            elif (
                ("group" not in key.lower() or x.is_group)
                and (
                    "group" in key.lower()
                    or "channel" not in key.lower()
                    or x.is_channel
                )
                and (
                    "group" in key.lower()
                    or "channel" in key.lower()
                    or x.is_group
                    or x.is_channel
                )
            ):
                try:
                    await e.client(
                        EditAdminRequest(
                            x.id,
                            user.id,
                            _gpromote_rights,
                            rank,
                        ),
                    )
                    c += 1
                except Exception as er:
                    LOGS.info(er)
        await eor(ev, f"Promoted The Replied Users in Total : {c} {key} chats")
    else:
        k = e.text.split()
        if not k[1]:
            return await eor(
                e, "`Give someone's username/id or replied to user.", time=5
            )
        user = k[1]
        if user.isdigit():
            user = int(user)
        try:
            name = await e.client.get_entity(user)
        except BaseException:
            return await e.eor(f"`No User Found Regarding {user}`", time=5)
        ev = await e.eor(f"`Promoting {name.first_name} globally.`")
        key = "all"
        if len(k) > 2 and (("group" in k[2]) or ("channel" in k[2])):
            key = k[2]
        rank = k[3] if len(k) > 3 else "AdMin"
        c = 0
        async for x in e.client.iter_dialogs():
            if (
                "group" in key.lower()
                and x.is_group
                or "group" not in key.lower()
                and "channel" in key.lower()
                and x.is_channel
                or "group" not in key.lower()
                and "channel" not in key.lower()
                and (x.is_group or x.is_channel)
            ):
                try:
                    await ultroid_bot(
                        EditAdminRequest(
                            x.id,
                            user,
                            _gpromote_rights,
                            rank,
                        ),
                    )
                    c += 1
                except BaseException:
                    pass
        await eor(ev, f"Promoted {name.first_name} in Total : {c} {key} chats.")


@ultroid_cmd(pattern="gdemote( (.*)|$)", fullsudo=True)
async def _(e):
    x = e.pattern_match.group(1).strip()
    ultroid_bot = e.client
    if not x:
        return await e.eor(get_string("schdl_2"), time=5)
    user = await e.get_reply_message()
    if user:
        user.id = user.peer_id.user_id if e.is_private else user.from_id.user_id
        ev = await e.eor("`Demoting Replied User Globally`")
        ok = e.text.split()
        key = "all"
        if len(ok) > 1 and (("group" in ok[1]) or ("channel" in ok[1])):
            key = ok[1]
        rank = "Not AdMin"
        c = 0
        async for x in e.client.iter_dialogs():
            if (
                "group" in key.lower()
                and x.is_group
                or "group" not in key.lower()
                and "channel" in key.lower()
                and x.is_channel
                or "group" not in key.lower()
                and "channel" not in key.lower()
                and (x.is_group or x.is_channel)
            ):
                try:
                    await ultroid_bot(
                        EditAdminRequest(
                            x.id,
                            user.id,
                            _gdemote_rights,
                            rank,
                        ),
                    )
                    c += 1
                except BaseException:
                    pass
        await eor(ev, f"Demoted The Replied Users in Total : {c} {key} chats")
    else:
        k = e.text.split()
        if not k[1]:
            return await eor(
                e, "`Give someone's username/id or replied to user.", time=5
            )
        user = k[1]
        if user.isdigit():
            user = int(user)
        try:
            name = await ultroid_bot.get_entity(user)
        except BaseException:
            return await e.eor(f"`No User Found Regarding {user}`", time=5)
        ev = await e.eor(f"`Demoting {name.first_name} globally.`")
        key = "all"
        if len(k) > 2 and (("group" in k[2]) or ("channel" in k[2])):
            key = k[2]
        rank = "Not AdMin"
        c = 0
        async for x in ultroid_bot.iter_dialogs():
            if (
                "group" in key.lower()
                and x.is_group
                or "group" not in key.lower()
                and "channel" in key.lower()
                and x.is_channel
                or "group" not in key.lower()
                and "channel" not in key.lower()
                and (x.is_group or x.is_channel)
            ):
                try:
                    await ultroid_bot(
                        EditAdminRequest(
                            x.id,
                            user,
                            _gdemote_rights,
                            rank,
                        ),
                    )
                    c += 1
                except BaseException:
                    pass
        await eor(ev, f"Demoted {name.first_name} in Total : {c} {key} chats.")


# --- Sección 1: Comando .gban ---
@ultroid_cmd(pattern="gban( (.*)|$)", fullsudo=True)
async def _(e):
    # Registrar el inicio del tiempo
    start_time = time.time()

    # Mensaje inicial mientras se procesa el comando
    api_calls = 1  # Contador de llamadas a la API (inicia en 1 tras mandar el comando)

    xx = await e.eor("`Good bye, my friend...`")
    reason = ""
    api_calls += 1  # Incrementamos el contador

    # --- Bloque 1: Identificación del usuario y motivo ---
    if e.reply_to_msg_id:  # Si se responde a un mensaje
        replied_msg = await e.get_reply_message()  # Llama a la API para obtener el mensaje respondido 
        api_calls += 1  # Incrementamos el contador
        userid = replied_msg.sender_id  # Extrae el ID del remitente del mensaje
        try:
            reason = e.text.split(" ", maxsplit=1)[1]  # Obtén el motivo (si existe)
        except IndexError:
            reason = ""  # Si no hay motivo, se deja vacío
    elif e.pattern_match.group(1).strip():  # Si se pasa el usuario/motivo como texto
        usr = e.text.split(maxsplit=2)[1]
        try:
            userid = await e.client.parse_id(usr)  # Tercera posible llamada
            api_calls += 1  # Incrementamos el contador
        except ValueError:
            userid = usr
        try:
            reason = e.text.split(maxsplit=2)[2]
        except IndexError:
            pass
    elif e.is_private:  # Si el comando se usa en un chat privado
        userid = e.chat_id
        try:
            reason = e.text.split(" ", maxsplit=1)[1]
        except IndexError:
            pass
    else:  # Si no se especifica usuario ni motivo
        return await xx.eor("`Responde a un mensaje o especifica un ID/username`", time=5)

    # --- Bloque 2: Verificación del usuario ---
    user = None
    try:
        user = await e.client.get_entity(userid)  # # Llamada a la API para obtener información básica
        api_calls += 1  # Incrementar aquí
        name = (f'<a href="tg://user?id={user.id}">{html.escape(user.first_name)}</a>')
    except BaseException:
        userid = int(userid)  # Convierte a entero si falla (conversación interna, no es llamada a la API)
        name = str(userid)
    
    # Prevenir autobloqueo
    if userid == ultroid_bot.uid:
        return await xx.eor("`No puedes gbanearte a ti mismo`", time=3)
    elif is_gbanned(userid):
        return await e.eor("`El usuario ya está gbaneado`", time=4)

    # --- Bloque 3: Aplicación del bloqueo en todos los chats ---
    chats = 0  # Contador de chats afectados
    dialog_cache = getattr(e.client, "_dialog_cache", None)  # Busca la caché de diálogos existente

    if not dialog_cache:  # Si no hay caché, crea una nueva iterativamente
        dialog_cache = []
        async for dialog in e.client.iter_dialogs():  # Iteración para evitar carga completa
            if dialog.is_group or dialog.is_channel:
                dialog_cache.append(dialog)
        e.client._dialog_cache = dialog_cache  # Almacena la caché temporalmente

    for ggban in dialog_cache:  # Recorre los diálogos en la caché
        if ggban.is_group or ggban.is_channel:  # Aplica solo a grupos o canales
            try:
                await e.client.edit_permissions(ggban.id, userid, view_messages=False)
                api_calls += 1  # Incrementa el contador de llamadas
                chats += 1
            except FloodWaitError as fw:
                LOGS.info(
                    f"[FLOOD_WAIT_ERROR] : Comando `gban` pausado por {fw.seconds + 10}s"
                )
                await asyncio.sleep(fw.seconds + 10)  # Manejo de espera por límite de tiempo
                try:
                    await e.client.edit_permissions(
                        gban.id, userid, view_messages=False
                    )
                    api_calls += 1  # Incrementa el contador de llamadas en reintento
                    chats += 1
                except BaseException as er:
                    LOGS.exception(er)
            except (ChatAdminRequiredError, ValueError):
                pass  # Si no tiene permisos para administrar en un chat
            except BaseException as er:
                LOGS.exception(er)

    # --- Bloque 4: Registro y bloqueo del usuario ---
    gban(userid, reason)  # Registra el bloqueo global en la base de datos
    if isinstance(user, User):
        await e.client(BlockRequest(userid))  # Bloquea al usuario
        api_calls += 1  # Incrementa el contador para esta llamada

    # Obtén el estado actualizado el usuario completo después del bloqueo
    try:
        full_user = (await e.client(GetFullUserRequest(userid))).full_user  # Obtiene entidad completa
        api_calls += 1  # Incrementa el contador de llamadas a la API
        block_status = 'Sí✔' if full_user.blocked else 'No✘'
    except Exception as error:
        LOGS.exception(f"Error al verificar el estado de bloqueo del usuario {userid}: {error}")
        block_status = 'No disponible'

    # Registrar el tiempo de ejecución
    execution_time = time.time() - start_time

    # --- Bloque 5: Mensaje de confirmación ---
    api_calls += 1  # Incrementa el contador al inicio del bloque 5

    # Verifica si `name` parece ser un ID (6 o más números consecutivos) y reemplázalo por "No disponible"
    if name.isdigit() and len(name) >= 6:
        name = "<code>No disponible</code>"

    gb_msg = f"<b>#GLOBALBAN</b>\n"
    gb_msg += f"<b>• ɴᴏᴍʙʀᴇ</b> ⇝ {name}\n"
    gb_msg += f"<b>• ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ</b> ⇝ {userid}\n"
    gb_msg += f"<b>• ᴄʜᴀᴛꜱ</b> ⇝ <code>{chats} ban(s)</code>\n"
    gb_msg += f"<b>• ʙʟᴏᴄᴋ</b> ⇝ <code>{block_status}</code>\n"
    gb_msg += "━━━━━━━━━━━━\n"  # Separador
    gb_msg += f"<b>• ᴀᴘɪ ᴄᴀʟʟꜱ</b> ⇝ <code>{api_calls}</code>\n"
    gb_msg += f"<b>• ᴛɪᴇᴍᴘᴏ ᴄᴏᴍᴘᴜᴛᴀᴅᴏ</b> ⇝ <code>{execution_time:.2f}s</code>\n"
    gb_msg += "━━━━━━━━━━━━\n"  # Separador
    if reason:
        gb_msg += f"<b>• ᴍᴏᴛɪᴠᴏ</b> ⇝ <code>{reason}</code>\n"
    await xx.edit(gb_msg, parse_mode='html')


# --- Sección 2: Comando .ungban ---
@ultroid_cmd(pattern="ungban( (.*)|$)", fullsudo=True)
async def _(e):
    # Registrar el inicio del tiempo
    start_time = time.time()

    # Mensaje inicial mientras se procesa el comando
    api_calls = 1  # Contador de llamadas a la API (inicia en 1 tras mandar el comando)
    xx = await e.eor("`Restableciendo permisos y desbloqueando...`")
    reason = ""
    api_calls += 1  # Incrementamos el contador

    # --- Bloque 1: Identificación del usuario y motivo ---
    if e.reply_to_msg_id:
        replied_msg = await e.get_reply_message()  # Llama a la API para obtener el mensaje respondido
        api_calls += 1
        userid = replied_msg.sender_id  # Extrae el ID del remitente del mensaje
        try:
            reason = e.text.split(" ", maxsplit=1)[1]
        except IndexError:
            reason = ""
    elif e.pattern_match.group(1).strip():
        usr = e.text.split(maxsplit=2)[1]
        try:
            userid = await e.client.parse_id(usr)  # Parsear el ID o username
            api_calls += 1
        except ValueError:
            userid = usr
        try:
            reason = e.text.split(maxsplit=2)[2]
        except IndexError:
            pass
    elif e.is_private:
        userid = e.chat_id
        try:
            reason = e.text.split(" ", maxsplit=1)[1]
        except IndexError:
            pass
    else:
        return await xx.eor("`Responde a un mensaje o especifica un ID/username`", time=5)

    # --- Bloque 2: Verificación del usuario ---
    user = None
    try:
        user = await e.client.get_entity(userid)
        api_calls += 1
        name = (f'<a href="tg://user?id={user.id}">{html.escape(user.first_name)}</a>')
    except BaseException:
        userid = int(userid)
        name = str(userid)

    # Prevenir errores innecesarios
    if userid == ultroid_bot.uid:
        return await xx.eor("`No puedes realizar esta acción contigo mismo.`", time=3)
    elif not is_gbanned(userid):
        return await e.eor("`El usuario no está gbaneado.`", time=4)

    # --- Bloque 3: Eliminación de restricciones en todos los chats ---
    chats = 0
    dialog_cache = getattr(e.client, "_dialog_cache", None)

    if not dialog_cache:
        dialog_cache = []
        async for dialog in e.client.iter_dialogs():
            if dialog.is_group or dialog.is_channel:
                dialog_cache.append(dialog)
        e.client._dialog_cache = dialog_cache

    for unggban in dialog_cache:
        if unggban.is_group or unggban.is_channel:
            try:
                await e.client.edit_permissions(unggban.id, userid, view_messages=True)
                api_calls += 1
                chats += 1
            except FloodWaitError as fw:
                LOGS.info(
                    f"[FLOOD_WAIT_ERROR] : Comando `unggban` pausado por {fw.seconds + 10}s"
                )
                await asyncio.sleep(fw.seconds + 10)
                try:
                    await e.client.edit_permissions(
                        unggban.id, userid, view_messages=True
                    )
                    api_calls += 1
                    chats += 1
                except BaseException as er:
                    LOGS.exception(er)
            except (ChatAdminRequiredError, ValueError):
                pass
            except BaseException as er:
                LOGS.exception(er)

    # --- Bloque 4: Eliminación del baneo global y desbloqueo ---
    ungban(userid)  # Elimina el registro del bloqueo global
    if isinstance(user, User):
        await e.client(UnblockRequest(userid))  # Desbloquea al usuario
        api_calls += 1

    # Obtén el estado actualizado el usuario completo después del bloqueo
    try:
        full_user = (await e.client(GetFullUserRequest(userid))).full_user  # Obtiene entidad completa
        api_calls += 1  # Incrementa el contador de llamadas a la API
        block_status = 'Sí✔' if full_user.blocked else 'No✘'
    except Exception as error:
        LOGS.exception(f"Error al verificar el estado de bloqueo del usuario {userid}: {error}")
        block_status = 'No disponible'

    # Registrar el tiempo de ejecución
    execution_time = time.time() - start_time

    # --- Bloque 5: Mensaje de confirmación ---
    api_calls += 1  # Incrementa el contador al inicio del bloque 5

    # Verifica si `name` parece ser un ID (6 o más números consecutivos) y reemplázalo por "No disponible"
    if name.isdigit() and len(name) >= 6:
        name = "<code>No disponible</code>"

    unsuperban_msg = f"<b>#UNGLOBALBAN</b>\n"
    unsuperban_msg += f"<b>• ɴᴏᴍʙʀᴇ</b> ⇝ {name}\n"
    unsuperban_msg += f"<b>• ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ</b> ⇝ {userid}\n"
    unsuperban_msg += f"<b>• ᴄʜᴀᴛꜱ</b> ⇝ <code>{chats} desbloqueado(s)</code>\n"
    unsuperban_msg += f"<b>• ʙʟᴏᴄᴋ</b> ⇝ <code>{'No✘' if not full_user.blocked else 'Sí✔'}</code>\n"
    unsuperban_msg += "━━━━━━━━━━━━\n"
    unsuperban_msg += f"<b>• ᴀᴘɪ ᴄᴀʟʟꜱ</b> ⇝ <code>{api_calls}</code>\n"
    unsuperban_msg += f"<b>• ᴛɪᴇᴍᴘᴏ ᴄᴏᴍᴘᴜᴛᴀᴅᴏ</b> ⇝ <code>{execution_time:.2f}s</code>\n"
    unsuperban_msg += "━━━━━━━━━━━━\n"
    if reason:
        unsuperban_msg += f"<b>• ᴍᴏᴛɪᴠᴏ</b> ⇝ <code>{reason}</code>\n"
    await xx.edit(unsuperban_msg, parse_mode='html')


@ultroid_cmd(pattern="g(admin|)cast( (.*)|$)", fullsudo=True)
async def gcast(event):
    text, btn, reply = "", None, None
    if xx := event.pattern_match.group(2):
        msg, btn = get_msg_button(event.text.split(maxsplit=1)[1])
    elif event.is_reply:
        reply = await event.get_reply_message()
        msg = reply.text
        if reply.buttons:
            btn = format_btn(reply.buttons)
        else:
            msg, btn = get_msg_button(msg)
    else:
        return await eor(
            event, "`Give some text to Globally Broadcast or reply a message..`"
        )

    kk = await event.eor("`Globally Broadcasting Msg...`")
    er = 0
    done = 0
    err = ""
    if event.client._dialogs:
        dialog = event.client._dialogs
    else:
        dialog = await event.client.get_dialogs()
        event.client._dialogs.extend(dialog)
    for x in dialog:
        if x.is_group:
            chat = x.entity.id
            if (
                not keym.contains(chat)
                and int(f"-100{str(chat)}") not in NOSPAM_CHAT
                and (
                    (
                        event.text[2:7] != "admin"
                        or (x.entity.admin_rights or x.entity.creator)
                    )
                )
            ):
                try:
                    if btn:
                        bt = create_tl_btn(btn)
                        await something(
                            event,
                            msg,
                            reply.media if reply else None,
                            bt,
                            chat=chat,
                            reply=False,
                        )
                    else:
                        await event.client.send_message(
                            chat, msg, file=reply.media if reply else None
                        )
                    done += 1
                except FloodWaitError as fw:
                    await asyncio.sleep(fw.seconds + 10)
                    try:
                        if btn:
                            bt = create_tl_btn(btn)
                            await something(
                                event,
                                msg,
                                reply.media if reply else None,
                                bt,
                                chat=chat,
                                reply=False,
                            )
                        else:
                            await event.client.send_message(
                                chat, msg, file=reply.media if reply else None
                            )
                        done += 1
                    except Exception as rr:
                        err += f"• {rr}\n"
                        er += 1
                except BaseException as h:
                    err += f"• {str(h)}" + "\n"
                    er += 1
    text += f"Done in {done} chats, error in {er} chat(s)"
    if err != "":
        open("gcast-error.log", "w+").write(err)
        text += f"\nYou can do `{HNDLR}ul gcast-error.log` to know error report."
    await kk.edit(text)


@ultroid_cmd(pattern="gucast( (.*)|$)", fullsudo=True)
async def gucast(event):
    msg, btn, reply = "", None, None
    if xx := event.pattern_match.group(1).strip():
        msg, btn = get_msg_button(event.text.split(maxsplit=1)[1])
    elif event.is_reply:
        reply = await event.get_reply_message()
        msg = reply.text
        if reply.buttons:
            btn = format_btn(reply.buttons)
        else:
            msg, btn = get_msg_button(msg)
    else:
        return await eor(
            event, "`Give some text to Globally Broadcast or reply a message..`"
        )
    kk = await event.eor("`Globally Broadcasting Msg...`")
    er = 0
    done = 0
    if event.client._dialogs:
        dialog = event.client._dialogs
    else:
        dialog = await event.client.get_dialogs()
        event.client._dialogs.extend(dialog)
    for x in dialog:
        if x.is_user and not x.entity.bot:
            chat = x.id
            if not keym.contains(chat):
                try:
                    if btn:
                        bt = create_tl_btn(btn)
                        await something(
                            event,
                            msg,
                            reply.media if reply else None,
                            bt,
                            chat=chat,
                            reply=False,
                        )
                    else:
                        await event.client.send_message(
                            chat, msg, file=reply.media if reply else None
                        )
                    done += 1
                except BaseException:
                    er += 1
    await kk.edit(f"Done in {done} chats, error in {er} chat(s)")


@ultroid_cmd(pattern="gkick( (.*)|$)", fullsudo=True)
async def gkick(e):
    xx = await e.eor("`Gkicking...`")
    if e.reply_to_msg_id:
        userid = (await e.get_reply_message()).sender_id
    elif e.pattern_match.group(1).strip():
        userid = await e.client.parse_id(e.pattern_match.group(1).strip())
    elif e.is_private:
        userid = e.chat_id
    else:
        return await xx.edit("`Reply to some msg or add their id.`", time=5)
    name = (await e.client.get_entity(userid)).first_name
    chats = 0
    if userid == ultroid_bot.uid:
        return await xx.eor("`I can't gkick myself.`", time=3)
    if userid in DEVLIST:
        return await xx.eor("`I can't gkick my Developers.`", time=3)
    if e.client._dialogs:
        dialog = e.client._dialogs
    else:
        dialog = await e.client.get_dialogs()
        e.client._dialogs.extend(dialog)
    for gkick in dialog:
        if gkick.is_group or gkick.is_channel:
            try:
                await e.client.kick_participant(gkick.id, userid)
                chats += 1
            except BaseException:
                pass
    await xx.edit(f"`Gkicked` [{name}](tg://user?id={userid}) `in {chats} chats.`")


@ultroid_cmd(pattern="gmute( (.*)|$)", fullsudo=True)
async def _(e):
    xx = await e.eor("`Gmuting...`")
    if e.reply_to_msg_id:
        userid = (await e.get_reply_message()).sender_id
    elif e.pattern_match.group(1).strip():
        userid = await e.client.parse_id(e.pattern_match.group(1).strip())
    elif e.is_private:
        userid = e.chat_id
    else:
        return await xx.eor("`Reply to some msg or add their id.`", tome=5, time=5)
    name = await e.client.get_entity(userid)
    chats = 0
    if userid == ultroid_bot.uid:
        return await xx.eor("`I can't gmute myself.`", time=3)
    if userid in DEVLIST:
        return await xx.eor("`I can't gmute my Developers.`", time=3)
    if is_gmuted(userid):
        return await xx.eor("`User is already gmuted.`", time=4)
    if e.client._dialogs:
        dialog = e.client._dialogs
    else:
        dialog = await e.client.get_dialogs()
        e.client._dialogs.extend(dialog)
    for onmute in dialog:
        if onmute.is_group:
            try:
                await e.client.edit_permissions(onmute.id, userid, send_messages=False)
                chats += 1
            except BaseException:
                pass
    gmute(userid)
    await xx.edit(f"`Gmuted` {inline_mention(name)} `in {chats} chats.`")


@ultroid_cmd(pattern="ungmute( (.*)|$)", fullsudo=True)
async def _(e):
    xx = await e.eor("`UnGmuting...`")
    if e.reply_to_msg_id:
        userid = (await e.get_reply_message()).sender_id
    elif e.pattern_match.group(1).strip():
        userid = await e.client.parse_id(e.pattern_match.group(1).strip())
    elif e.is_private:
        userid = e.chat_id
    else:
        return await xx.eor("`Reply to some msg or add their id.`", time=5)
    name = (await e.client.get_entity(userid)).first_name
    chats = 0
    if not is_gmuted(userid):
        return await xx.eor("`User is not gmuted.`", time=3)
    if e.client._dialogs:
        dialog = e.client._dialogs
    else:
        dialog = await e.client.get_dialogs()
        e.client._dialogs.extend(dialog)
    for hurr in dialog:
        if hurr.is_group:
            try:
                await e.client.edit_permissions(hurr.id, userid, send_messages=True)
                chats += 1
            except BaseException:
                pass
    ungmute(userid)
    await xx.edit(f"`Ungmuted` {inline_mention(name)} `in {chats} chats.`")


@ultroid_cmd(
    pattern="listgban$",
)
async def list_gengbanned(event):
    users = list_gbanned()
    x = await event.eor(get_string("com_1"))
    msg = ""
    if not users:
        return await x.edit("`You haven't GBanned anyone!`")
    for i in users:
        try:
            name = await event.client.get_entity(int(i))
        except BaseException:
            name = i
        msg += f"<strong>User</strong>: {inline_mention(name, html=True)}\n"
        reason = users[i]
        msg += f"<strong>Reason</strong>: {reason}\n\n" if reason is not None else "\n"
    gbanned_users = f"<strong>List of users GBanned by {OWNER_NAME}</strong>:\n\n{msg}"
    if len(gbanned_users) > 4096:
        with open("gbanned.txt", "w") as f:
            f.write(
                gbanned_users.replace("<strong>", "")
                .replace("</strong>", "")
                .replace("<a href=tg://user?id=", "")
                .replace("</a>", "")
            )
        await x.reply(
            file="gbanned.txt",
            message=f"List of users GBanned by {inline_mention(ultroid_bot.me)}",
        )
        os.remove("gbanned.txt")
        await x.delete()
    else:
        await x.edit(gbanned_users, parse_mode="html")


@ultroid_cmd(
    pattern="gstat( (.*)|$)",
)
async def gstat_(e):
    xx = await e.eor(get_string("com_1"))
    if e.is_private:
        userid = (await e.get_chat()).id
    elif e.reply_to_msg_id:
        userid = (await e.get_reply_message()).sender_id
    elif e.pattern_match.group(1).strip():
        try:
            userid = await e.client.parse_id(e.pattern_match.group(1).strip())
        except Exception as err:
            return await xx.eor(f"{err}", time=10)
    else:
        return await xx.eor("`Reply to some msg or add their id.`", time=5)
    name = (await e.client.get_entity(userid)).first_name
    msg = f"**{name} is "
    is_banned = is_gbanned(userid)
    reason = list_gbanned().get(userid)
    if is_banned:
        msg += "Globally Banned"
        msg += f" with reason** `{reason}`" if reason else ".**"
    else:
        msg += "not Globally Banned.**"
    await xx.edit(msg)


@ultroid_cmd(pattern="gblacklist$")
async def blacklist_(event):
    await gblacker(event, "add")


@ultroid_cmd(pattern="ungblacklist$")
async def ungblacker(event):
    await gblacker(event, "remove")


async def gblacker(event, type_):
    try:
        chat_id = int(event.text.split(maxsplit=1)[1])
        try:
            chat_id = (await event.client.get_entity(chat_id)).id
        except Exception as e:
            return await event.eor(f"**ERROR**\n`{str(e)}`")
    except IndexError:
        chat_id = event.chat_id
    if type_ == "add":
        keym.add(chat_id)
    elif type_ == "remove":
        keym.remove(chat_id)
    await event.eor(f"Global Broadcasts: \n{type_}ed {chat_id}")
