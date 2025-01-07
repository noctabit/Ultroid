# Ultroid - UserBot
# Copyright (C) 2021-2023 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://www.github.com/TeamUltroid/Ultroid/blob/main/LICENSE/>.
"""
✘ Commands Available -

• `{i}kickme` : Leaves the group.

• `{i}date` : Show Calender.

• `{i}listreserved`
    List all usernames (channels/groups) you own.

• `{i}stats` : See your profile stats.

• `{i}paste` - `Include long text / Reply to text file.`

• `{i}superinfo <username/userid/chatid>`
    Reply to someone's msg.

• `{i}invite <username/userid>`
    Add user to the chat.

• `{i}rmbg <reply to pic>`
    Remove background from that picture.

• `{i}telegraph <reply to media/text>`
    Upload media/text to telegraph.

• `{i}json <reply to msg>`
    Get the json encoding of the message.

• `{i}suggest <reply to message> or <poll title>`
    Create a Yes/No poll for the replied suggestion.

• `{i}cpy <reply to message>`
   Copy the replied message, with formatting. Expires in 24hrs.
• `{i}pst`
   Paste the copied message, with formatting.

• `{i}thumb <reply file>` : Download the thumbnail of the replied file.

• `{i}getmsg <message link>`
  Get messages from chats with forward/copy restrictions.
"""

import calendar
import html
import io
import os
import pathlib
import time
import math  # Añadido
from datetime import datetime as dt

try:
    from PIL import Image
except ImportError:
    Image = None

from pyUltroid._misc._assistant import asst_cmd
from pyUltroid.dB.gban_mute_db import is_gbanned
from pyUltroid.fns.tools import get_chat_and_msgid

try:
    from telegraph import upload_file as uf
except ImportError:
    uf = None

from telethon.errors.rpcerrorlist import ChatForwardsRestrictedError, UserBotError
from telethon.events import NewMessage
from telethon.tl.custom import Dialog
from telethon.tl.functions.channels import (
    GetAdminedPublicChannelsRequest,
    InviteToChannelRequest,
    LeaveChannelRequest,
)
from telethon.tl.functions.contacts import GetBlockedRequest
from telethon.tl.functions.messages import AddChatUserRequest, GetAllStickersRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    Channel,
    Chat,
    InputMediaPoll,
    Poll,
    PollAnswer,
    TLObject,
    User,
)
from telethon.tl import functions, types  # Añadido
from telethon.utils import get_peer_id

from pyUltroid.fns.info import get_chat_info

from . import (
    HNDLR,
    LOGS,
    Image,
    ReTrieveFile,
    Telegraph,
    asst,
    async_searcher,
    bash,
    check_filename,
    eod,
    eor,
    get_paste,
    get_string,
    inline_mention,
    json_parser,
    mediainfo,
    udB,
    ultroid_cmd,
)

# =================================================================#

TMP_DOWNLOAD_DIRECTORY = "resources/downloads/"

_copied_msg = {}


@ultroid_cmd(pattern="kickme$", fullsudo=True)
async def leave(ult):
    await ult.eor(f"`{ult.client.me.first_name} has left this group, bye!!.`")
    await ult.client(LeaveChannelRequest(ult.chat_id))


@ultroid_cmd(
    pattern="date$",
)
async def date(event):
    m = dt.now().month
    y = dt.now().year
    d = dt.now().strftime("Date - %B %d, %Y\nTime- %H:%M:%S")
    k = calendar.month(y, m)
    await event.eor(f"`{k}\n\n{d}`")


@ultroid_cmd(
    pattern="listreserved$",
)
async def _(event):
    result = await event.client(GetAdminedPublicChannelsRequest())
    if not result.chats:
        return await event.eor("`No username Reserved`")
    output_str = "".join(
        f"- {channel_obj.title} @{channel_obj.username} \n"
        for channel_obj in result.chats
    )
    await event.eor(output_str)


@ultroid_cmd(
    pattern="stats$",
)
async def stats(
    event: NewMessage.Event,
):
    ok = await event.eor("`Collecting stats...`")
    start_time = time.time()
    private_chats = 0
    bots = 0
    groups = 0
    broadcast_channels = 0
    admin_in_groups = 0
    creator_in_groups = 0
    admin_in_broadcast_channels = 0
    creator_in_channels = 0
    unread_mentions = 0
    unread = 0
    dialog: Dialog
    async for dialog in event.client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, Channel) and entity.broadcast:
            broadcast_channels += 1
            if entity.creator or entity.admin_rights:
                admin_in_broadcast_channels += 1
            if entity.creator:
                creator_in_channels += 1

        elif (isinstance(entity, Channel) and entity.megagroup) or isinstance(
            entity, Chat
        ):
            groups += 1
            if entity.creator or entity.admin_rights:
                admin_in_groups += 1
            if entity.creator:
                creator_in_groups += 1

        elif isinstance(entity, User):
            private_chats += 1
            if entity.bot:
                bots += 1

        unread_mentions += dialog.unread_mentions_count
        unread += dialog.unread_count
    stop_time = time.time() - start_time
    try:
        ct = (await event.client(GetBlockedRequest(1, 0))).count
    except AttributeError:
        ct = 0
    try:
        sp = await event.client(GetAllStickersRequest(0))
        sp_count = len(sp.sets)
    except BaseException:
        sp_count = 0
    full_name = inline_mention(event.client.me)
    response = f"🔸 **Stats for {full_name}** \n\n"
    response += f"**Private Chats:** {private_chats} \n"
    response += f"**  •• **`Users: {private_chats - bots}` \n"
    response += f"**  •• **`Bots: {bots}` \n"
    response += f"**Groups:** {groups} \n"
    response += f"**Channels:** {broadcast_channels} \n"
    response += f"**Admin in Groups:** {admin_in_groups} \n"
    response += f"**  •• **`Creator: {creator_in_groups}` \n"
    response += f"**  •• **`Admin Rights: {admin_in_groups - creator_in_groups}` \n"
    response += f"**Admin in Channels:** {admin_in_broadcast_channels} \n"
    response += f"**  •• **`Creator: {creator_in_channels}` \n"
    response += f"**  •• **`Admin Rights: {admin_in_broadcast_channels - creator_in_channels}` \n"
    response += f"**Unread:** {unread} \n"
    response += f"**Unread Mentions:** {unread_mentions} \n"
    response += f"**Blocked Users:** {ct}\n"
    response += f"**Total Stickers Pack Installed :** `{sp_count}`\n\n"
    response += f"**__It Took:__** {stop_time:.02f}s \n"
    await ok.edit(response)


@ultroid_cmd(pattern="paste( (.*)|$)", manager=True, allow_all=True)
async def _(event):
    try:
        input_str = event.text.split(maxsplit=1)[1]
    except IndexError:
        input_str = None
    xx = await event.eor("` 《 Pasting... 》 `")
    downloaded_file_name = None
    if input_str:
        message = input_str
    elif event.reply_to_msg_id:
        previous_message = await event.get_reply_message()
        if previous_message.media:
            downloaded_file_name = await event.client.download_media(
                previous_message,
                "./resources/downloads",
            )
            with open(downloaded_file_name, "r") as fd:
                message = fd.read()
            os.remove(downloaded_file_name)
        else:
            message = previous_message.message
    else:
        message = None
    if not message:
        return await xx.eor(
            "`Reply to a Message/Document or Give me Some Text !`", time=5
        )
    done, key = await get_paste(message)
    if not done:
        return await xx.eor(key)
    link = f"https://spaceb.in/{key}"
    raw = f"https://spaceb.in/api/v1/documents/{key}/raw"
    reply_text = (
        f"• **Pasted to SpaceBin :** [Space]({link})\n• **Raw Url :** : [Raw]({raw})"
    )
    try:
        if event.client._bot:
            return await xx.eor(reply_text)
        ok = await event.client.inline_query(asst.me.username, f"pasta-{key}")
        await ok[0].click(event.chat_id, reply_to=event.reply_to_msg_id, hide_via=True)
        await xx.delete()
    except BaseException as e:
        LOGS.exception(e)
        await xx.edit(reply_text)


@ultroid_cmd(pattern="superinfo( (.*)|$)", manager=True)
async def _(event):
    
    
    # Verifica si el comando tiene un `user_id/username` o si es un mensaje respondido
    if match := event.pattern_match.group(1).strip():
        try:
            user = await event.client.parse_id(match)
        except Exception as er:
            return await event.eor(str(er))
    elif event.is_reply:
        rpl = await event.get_reply_message()
        user = rpl.sender_id
    else:
        user = event.chat_id

    # Mensaje temporal mientras se procesa la solicitud
    xx = await event.eor(get_string("com_1"))

    try:
        # Verifica si el usuario es válido
        _ = await event.client.get_entity(user)
    except Exception as er:
        return await xx.edit(f"**ERROR :** {er}")
    
    # Si el objeto no es un usuario, se asume que es un chat o canal
    if not isinstance(_, User):
        try:
            peer = get_peer_id(_)
            photo, capt = await get_chat_info(_, event)
            
            # Si el chat está globalmente baneado, se agrega la información
            if is_gbanned(peer):
                capt += "\n<b>• ɢʟᴏʙᴀʟ ʙᴀɴ</b> ⇝ <code>Sí✔</code>"
            
            # Si no hay foto, solo se envía el texto
            if not photo:
                return await xx.eor(capt, parse_mode="html")
            
            # Envía la foto junto con la información
            await event.client.send_message(
                event.chat_id, capt[:1024], file=photo, parse_mode="html"
            )
            await xx.delete()
        except Exception as er:
            # Define el mensaje de error según el contenido del error
            if "The provided media object is invalid" in str(er):
                error_msg = (
                    "**ERROR AL ENVIAR INFORMACIÓN AL CHAT**\n"
                    "'Hubo un problema con la foto o el archivo adjunto...'"
                )
            else:
                error_msg = "**ERROR AL ENVIAR INFORMACIÓN AL CHAT**\n" + str(er)
            await event.eor(error_msg)
        return

    try:
        # Obtiene información completa del usuario usando GetFullUserRequest
        full_user = (await event.client(GetFullUserRequest(user))).full_user
    except Exception as er:
        return await xx.edit(f"ERROR : {er}")
    
    # Asigna los datos del usuario
    user = _
    user_photos = (
        await event.client.get_profile_photos(user.id, limit=0)
    ).total or "0"
    user_id = user.id
    first_name = html.escape(user.first_name)
    
    # Limpia los posibles caracteres invisibles en el nombre
    if first_name is not None:
        first_name = first_name.replace("\u2060", "")
    
    last_name = user.last_name
    last_name = (
        last_name.replace("\u2060", "") if last_name else ("No disponible")
    )
    
    user_bio = full_user.about
    if user_bio is not None:
        user_bio = html.escape(full_user.about)
    else:
        user_bio = "No disponible"

    # Aquí añadimos el username del usuario con @
    username = f"@{user.username}" if user.username else "No disponible"
    
    common_chats = full_user.common_chats_count
    if user.photo:
        dc_id = user.photo.dc_id
    else:
        dc_id = "Requiere foto de perfil"

   # Obtiene el ID del remitente y asigna el teléfono del usuario consultado, protegiendo el del remitente.
    remitente = await event.get_sender()  # Obtiene la información del remitente del mensaje
    sender_id = remitente.id  # ID del remitente

    # Verifica si el remitente está consultándose a sí mismo
    is_self = user.id == sender_id

    # Asigna el teléfono, protegiendo el del remitente
    if is_self:
        phone = "Bat-Señal 🦇"
    elif user.phone:
        phone = f"+{user.phone}" if not user.phone.startswith("+") else user.phone
    else:
        phone = "No disponible"

    # Si es un bot asigna valores a los campos adicionales
    bot_inline_placeholder = "Sí✔" if user.bot and user.bot_inline_placeholder else "No✘"
    bot_nochats = "Sí✔" if user.bot and not user.bot_nochats else "No✘"

    # Obtenemos la última conexión considerando todos los posibles estados
    if isinstance(user.status, types.UserStatusOnline):
        last_seen = "En línea ahora"
    elif isinstance(user.status, types.UserStatusOffline):
        last_seen = f"Última vez: {user.status.was_online.strftime('%d/%m/%Y %H:%M:%S')}"
    elif isinstance(user.status, types.UserStatusRecently):
        last_seen = "Activo recientemente (menos de un día)"
    elif isinstance(user.status, types.UserStatusLastWeek):
        last_seen = "Activo en la última semana"
    elif isinstance(user.status, types.UserStatusLastMonth):
        last_seen = "Activo en el último mes"
    else:
        last_seen = "Última conexión desconocida"

    # Mensaje con la información del usuario
    caption = """<b>* ᴰᵃᵗᵃˢᵉᵗ ᵖᵒʳ ᵀᵉˡᵉᵍʳᵃᵐ ᴬᴾᴵ</b>
<b>• ᴛᴇʟᴇɢʀᴀᴍ ɪᴅ</b> ⇝ <code>{}</code>
<b>• ʟɪɴᴋ</b> ⇝ <a href='tg://user?id={}'>Mostrar</a>
<b>• ɴᴏᴍʙʀᴇ</b> ⇝ <code>{}</code>
<b>• ᴀᴘᴇʟʟɪᴅᴏꜱ</b> ⇝ <code>{}</code>
<b>• ᴜsᴇʀɴᴀᴍᴇ</b> ⇝ <code>{}</code>
<b>• ʙɪᴏ</b> ⇝ <code>{}</code>
<b>• ᴘʜᴏɴᴇ</b> ⇝ <code>{}</code>
<b>• ꜰᴏᴛᴏꜱ ᴇɴ ᴘᴇʀꜰɪʟ</b> ⇝ <code>{}</code>
<b>• ᴅᴀᴛᴀ ᴄᴇɴᴛᴇʀ ɪᴅ</b> ⇝ <code>{}</code>
<b>• ᴘʀᴏꜰɪʟᴇ ᴘʜᴏᴛᴏ ɪᴅ</b> ⇝ <code>{}</code>
<b>• ᴄᴏɴᴛᴀᴄᴛᴏ</b> ⇝ <code>{}</code>
<b>• ʙʟᴏᴄᴋ</b> ⇝ <code>{}</code>
<b>• ʀᴇꜱᴛʀɪɴɢɪᴅᴏ</b> ⇝ <code>{}</code>
<b>• ᴠᴇʀɪꜰɪᴄᴀᴅᴏ</b> ⇝ <code>{}</code>
<b>• ᴘʀᴇᴍɪᴜᴍ</b> ⇝ <code>{}</code>
<b>• ꜱᴄᴀᴍ</b> ⇝ <code>{}</code>
<b>• ꜰᴀᴋᴇ</b> ⇝ <code>{}</code>
<b>• ᴛᴇʟᴇɢʀᴀᴍ ꜱᴜᴘᴘᴏʀᴛ</b> ⇝ <code>{}</code>
<b>• ʙᴏᴛ</b> ⇝ <code>{}</code>
<b>• ʙᴏᴛ ɪɴʟɪɴᴇ</b> ⇝ <code>{}</code>
<b>• ʙᴏᴛ ᴘᴇʀᴍɪᴛɪᴅᴏ ᴇɴ ɢʀᴜᴘᴏꜱ</b> ⇝ <code>{}</code>
<b>• ɢʀᴜᴘᴏꜱ ᴄᴏᴍᴘᴀʀᴛɪᴅᴏꜱ</b> ⇝ <code>{}</code>
<b>• ʀᴇɢɪꜱᴛʀᴏ ᴅᴇ ᴀᴄᴛɪᴠɪᴅᴀᴅ</b> ⇝ <code>{}</code>
""".format(
    user_id,
    user_id,
    first_name,
    last_name,
    username,
    user_bio,
    phone,
    user_photos,
    dc_id,
    user.photo.photo_id if user.photo else "No disponible",
    "Sí✔" if user.contact else "No✘",
    "Sí✔" if full_user.blocked else "No✘",
    "Sí✔" if user.restricted else "No✘",
    "Sí✔" if user.verified else "No✘",
    "Sí✔" if user.premium else "No✘",
    "Sí✔" if user.scam else "No✘",
    "Sí✔" if user.fake else "No✘",
    "Sí✔" if user.support else "No✘",
    "Sí✔" if user.bot else "No✘",
    bot_inline_placeholder,
    bot_nochats,
    common_chats,
    last_seen, 
    )

    
    # Si el usuario está globalmente baneado, se agrega la información correspondiente
    if chk := is_gbanned(user_id):
        caption += f"<b>• ꜱᴜᴘᴇʀʙᴀɴ</b> ⇝ <code>Sí✔</code>\n<b>• ᴍᴏᴛɪᴠᴏ</b> ⇝ <code>{chk}</code>"
    
    # Envía la información con la foto de perfil (si está disponible)
    await event.client.send_message(
        event.chat_id,
        caption,
        reply_to=event.reply_to_msg_id,
        parse_mode="HTML",
        file=full_user.profile_photo,
        force_document=False,
        silent=True,
    )
    
    # Elimina el mensaje temporal
    await xx.delete()


@ultroid_cmd(
    pattern="invite( (.*)|$)",
    groups_only=True,
)
async def _(ult):
    xx = await ult.eor(get_string("com_1"))
    to_add_users = ult.pattern_match.group(1).strip()
    if not ult.is_channel and ult.is_group:
        for user_id in to_add_users.split(" "):
            try:
                await ult.client(
                    AddChatUserRequest(
                        chat_id=ult.chat_id,
                        user_id=await ult.client.parse_id(user_id),
                        fwd_limit=1000000,
                    ),
                )
                await xx.edit(f"Successfully invited `{user_id}` to `{ult.chat_id}`")
            except Exception as e:
                await xx.edit(str(e))
    else:
        for user_id in to_add_users.split(" "):
            try:
                await ult.client(
                    InviteToChannelRequest(
                        channel=ult.chat_id,
                        users=[await ult.client.parse_id(user_id)],
                    ),
                )
                await xx.edit(f"Successfully invited `{user_id}` to `{ult.chat_id}`")
            except UserBotError:
                await xx.edit(
                    f"Bots can only be added as Admins in Channel.\nBetter Use `{HNDLR}promote {user_id}`"
                )
            except Exception as e:
                await xx.edit(str(e))


@ultroid_cmd(
    pattern="rmbg($| (.*))",
)
async def abs_rmbg(event):
    RMBG_API = udB.get_key("RMBG_API")
    if not RMBG_API:
        return await event.eor(
            "Get your API key from [here](https://www.remove.bg/) for this plugin to work.",
        )
    match = event.pattern_match.group(1).strip()
    reply = await event.get_reply_message()
    if match and os.path.exists(match):
        dl = match
    elif reply and reply.media:
        if reply.document and reply.document.thumbs:
            dl = await reply.download_media(thumb=-1)
        else:
            dl = await reply.download_media()
    else:
        return await eod(
            event, f"Use `{HNDLR}rmbg` as reply to a pic to remove its background."
        )
    if not (dl and dl.endswith(("webp", "jpg", "png", "jpeg"))):
        os.remove(dl)
        return await event.eor(get_string("com_4"))
    if dl.endswith("webp"):
        file = f"{dl}.png"
        Image.open(dl).save(file)
        os.remove(dl)
        dl = file
    xx = await event.eor("`Sending to remove.bg`")
    dn, out = await ReTrieveFile(dl)
    os.remove(dl)
    if not dn:
        dr = out["errors"][0]
        de = dr.get("detail", "")
        return await xx.edit(
            f"**ERROR ~** `{dr['title']}`,\n`{de}`",
        )
    zz = Image.open(out)
    if zz.mode != "RGB":
        zz.convert("RGB")
    wbn = check_filename("ult-rmbg.webp")
    zz.save(wbn, "webp")
    await event.client.send_file(
        event.chat_id,
        out,
        force_document=True,
        reply_to=reply,
    )
    await event.client.send_file(event.chat_id, wbn, reply_to=reply)
    os.remove(out)
    os.remove(wbn)
    await xx.delete()


@ultroid_cmd(
    pattern="telegraph( (.*)|$)",
)
async def telegraphcmd(event):
    xx = await event.eor(get_string("com_1"))
    match = event.pattern_match.group(1).strip() or "Ultroid"
    reply = await event.get_reply_message()
    if not reply:
        return await xx.eor("`Reply to Message.`")
    if not reply.media and reply.message:
        content = reply.message
    else:
        getit = await reply.download_media()
        dar = mediainfo(reply.media)
        if dar == "sticker":
            file = f"{getit}.png"
            Image.open(getit).save(file)
            os.remove(getit)
            getit = file
        elif dar.endswith("animated"):
            file = f"{getit}.gif"
            await bash(f"lottie_convert.py '{getit}' {file}")
            os.remove(getit)
            getit = file
        if "document" not in dar:
            try:
                nn = f"https://graph.org{uf(getit)[0]}"
                amsg = f"Uploaded to [Telegraph]({nn}) !"
            except Exception as e:
                amsg = f"Error : {e}"
            os.remove(getit)
            return await xx.eor(amsg)
        content = pathlib.Path(getit).read_text()
        os.remove(getit)
    makeit = Telegraph.create_page(title=match, content=[content])
    await xx.eor(
        f"Pasted to Telegraph : [Telegraph]({makeit['url']})", link_preview=False
    )


@ultroid_cmd(pattern="json( (.*)|$)")
async def _(event):
    reply_to_id = None
    match = event.pattern_match.group(1).strip()
    if event.reply_to_msg_id:
        msg = await event.get_reply_message()
        reply_to_id = event.reply_to_msg_id
    else:
        msg = event
        reply_to_id = event.message.id
    if match and hasattr(msg, match.split()[0]):
        msg = getattr(msg, match.split()[0])
        try:
            if hasattr(msg, "to_json"):
                msg = msg.to_json(ensure_ascii=False, indent=1)
            elif hasattr(msg, "to_dict"):
                msg = json_parser(msg.to_dict(), indent=1)
            else:
                msg = TLObject.stringify(msg)
        except Exception:
            pass
        msg = str(msg)
    else:
        msg = json_parser(msg.to_json(), indent=1)
    if "-t" in match:
        try:
            data = json_parser(msg)
            msg = json_parser(
                {key: data[key] for key in data.keys() if data[key]}, indent=1
            )
        except Exception:
            pass
    if len(msg) > 4096:
        with io.BytesIO(str.encode(msg)) as out_file:
            out_file.name = "json-ult.txt"
            await event.client.send_file(
                event.chat_id,
                out_file,
                force_document=True,
                allow_cache=False,
                reply_to=reply_to_id,
            )
            await event.delete()
    else:
        await event.eor(f"```{msg or None}```")


@ultroid_cmd(pattern="suggest( (.*)|$)", manager=True)
async def sugg(event):
    sll = event.text.split(maxsplit=1)
    try:
        text = sll[1]
    except IndexError:
        text = None
    if not (event.is_reply or text):
        return await eod(
            event,
            "`Please reply to a message to make a suggestion poll!`",
        )
    if event.is_reply and not text:
        reply = await event.get_reply_message()
        if reply.text and len(reply.text) < 35:
            text = reply.text
        else:
            text = "Do you Agree to Replied Suggestion ?"
    reply_to = event.reply_to_msg_id if event.is_reply else event.id
    try:
        await event.client.send_file(
            event.chat_id,
            file=InputMediaPoll(
                poll=Poll(
                    id=12345,
                    question=text,
                    answers=[PollAnswer("Yes", b"1"), PollAnswer("No", b"2")],
                ),
            ),
            reply_to=reply_to,
        )
    except Exception as e:
        return await eod(event, f"`Oops, you can't send polls here!\n\n{e}`")
    await event.delete()


@ultroid_cmd(
    pattern="cpy$",
)
async def copp(event):
    msg = await event.get_reply_message()
    if not msg:
        return await event.eor(f"Use `{HNDLR}cpy` as reply to a message!", time=5)
    _copied_msg["CLIPBOARD"] = msg
    await event.eor(f"Copied. Use `{HNDLR}pst` to paste!", time=10)


@asst_cmd(pattern="pst$")
async def pepsodent(event):
    await toothpaste(event)


@ultroid_cmd(
    pattern="pst$",
)
async def colgate(event):
    await toothpaste(event)


async def toothpaste(event):
    try:
        await event.respond(_copied_msg["CLIPBOARD"])
    except KeyError:
        return await eod(
            event,
            f"Nothing was copied! Use `{HNDLR}cpy` as reply to a message first!",
        )
    except Exception as ex:
        return await event.eor(str(ex), time=5)
    await event.delete()


@ultroid_cmd(pattern="thumb$")
async def thumb_dl(event):
    reply = await event.get_reply_message()
    if not (reply and reply.file):
        return await eod(event, get_string("th_1"), time=5)
    if not reply.file.media.thumbs:
        return await eod(event, get_string("th_2"))
    await event.eor(get_string("com_1"))
    x = await event.get_reply_message()
    m = await x.download_media(thumb=-1)
    await event.reply(file=m)
    os.remove(m)


@ultroid_cmd(pattern="getmsg( ?(.*)|$)")
async def get_restriced_msg(event):
    match = event.pattern_match.group(1).strip()
    if not match:
        await event.eor("`Please provide a link!`", time=5)
        return
    xx = await event.eor(get_string("com_1"))
    chat, msg = get_chat_and_msgid(match)
    if not (chat and msg):
        return await event.eor(
            f"{get_string('gms_1')}!\nEg: `https://t.me/TeamUltroid/3 or `https://t.me/c/1313492028/3`"
        )
    try:
        message = await event.client.get_messages(chat, ids=msg)
    except BaseException as er:
        return await event.eor(f"**ERROR**\n`{er}`")
    try:
        await event.client.send_message(event.chat_id, message)
        await xx.try_delete()
        return
    except ChatForwardsRestrictedError:
        pass
    if message.media:
        thumb = None
        if message.document.thumbs:
            thumb = await message.download_media(thumb=-1)
        media, _ = await event.client.fast_downloader(
            message.document,
            show_progress=True,
            event=xx,
            message=f"Downloading {message.file.name}...",
        )
        await xx.edit("`Uploading...`")
        uploaded, _ = await event.client.fast_uploader(
            media.name, event=xx, show_progress=True, to_delete=True
        )
        typ = not bool(message.video)
        await event.reply(
            message.text,
            file=uploaded,
            supports_streaming=typ,
            force_document=typ,
            thumb=thumb,
            attributes=message.document.attributes,
        )
        await xx.delete()
        if thumb:
            os.remove(thumb)
