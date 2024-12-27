# Ultroid - UserBot
# Copyright (C) 2021-2023 TeamUltroid
#
# This file is a part of < https://github.com/TeamUltroid/Ultroid/ >
# PLease read the GNU Affero General Public License in
# <https://github.com/TeamUltroid/pyUltroid/blob/main/LICENSE>.

import math

from telethon.tl import functions, types

from .. import LOGS

async def get_uinfo(e):
    user, data = None, None
    reply = await e.get_reply_message()
    if reply:
        user = await e.client.get_entity(reply.sender_id)
        data = e.pattern_match.group(1)
    else:
        ok = e.pattern_match.group(1).split(maxsplit=1)
        if len(ok) > 1:
            data = ok[1]
        try:
            user = await e.client.get_entity(await e.client.parse_id(ok[0]))
        except IndexError:
            pass
        except ValueError as er:
            await e.eor(str(er))
            return None, None
    return user, data


async def get_chat_info(chat, event):
    if isinstance(chat, types.Channel):
        chat_info = await event.client(functions.channels.GetFullChannelRequest(chat))
    elif isinstance(chat, types.Chat):
        chat_info = await event.client(functions.messages.GetFullChatRequest(chat))
    else:
        return await event.eor("'Usa esto para Grupos/Canales'")
    full = chat_info.full_chat
    chat_photo = full.chat_photo
    broadcast = getattr(chat, "broadcast", False)
    chat_type = "• ᴄʜᴀɴɴᴇʟ" if broadcast else "• ɢʀᴜᴘᴏ"
    chat_title = chat.title
    try:
        msg_info = await event.client(
            functions.messages.GetHistoryRequest(
                peer=chat.id,
                offset_id=0,
                offset_date=None,
                add_offset=-0,
                limit=0,
                max_id=0,
                min_id=0,
                hash=0,
            )
        )
    except Exception as er:
        msg_info = None
        if not event.client._bot:
            LOGS.exception(er)
    first_msg_valid = bool(
        msg_info and msg_info.messages and msg_info.messages[0].id == 1
    )

    creator_valid = bool(first_msg_valid and msg_info.users)
    creator_id = msg_info.users[0].id if creator_valid else None
    creator_firstname = (
        msg_info.users[0].first_name
        if creator_valid and msg_info.users[0].first_name is not None
        else "Deleted Account"
    )
    creator_username = (
        msg_info.users[0].username
        if creator_valid and msg_info.users[0].username is not None
        else None
    )
    created = msg_info.messages[0].date if first_msg_valid else None
    if not isinstance(chat.photo, types.ChatPhotoEmpty):
        dc_id = chat.photo.dc_id
    else:
        dc_id = "Null"

    restricted_users = getattr(full, "banned_count", None)
    members = getattr(full, "participants_count", chat.participants_count)
    admins = getattr(full, "admins_count", None)
    banned_users = getattr(full, "kicked_count", None)
    members_online = getattr(full, "online_count", 0)
    group_stickers = (
        full.stickerset.title if getattr(full, "stickerset", None) else None
    )
    messages_viewable = msg_info.count if msg_info else None
    messages_sent = getattr(full, "read_inbox_max_id", None)
    messages_sent_alt = getattr(full, "read_outbox_max_id", None)
    exp_count = getattr(full, "pts", None)
    supergroup = "<b>Yes</b>" if getattr(chat, "megagroup", None) else "No"
    creator_username = "@{}".format(creator_username) if creator_username else None

    if admins is None:
        try:
            participants_admins = await event.client(
                functions.channels.GetParticipantsRequest(
                    channel=chat.id,
                    filter=types.ChannelParticipantsAdmins(),
                    offset=0,
                    limit=0,
                    hash=0,
                )
            )
            admins = participants_admins.count if participants_admins else None
        except Exception as e:
            LOGS.info(f"Exception: {e}")
    caption = "<b>* ᴰᵃᵗᵃˢᵉᵗ ᵖᵒʳ ᵀᵉˡᵉᵍʳᵃᵐ ᴬᴾᴵ</b>\n"
    caption += f"<b>• ᴄʜᴀᴛ ɪᴅ</b> ⇝ <code>{chat.id}</code>\n"
    if chat_title is not None:
        caption += f"<b>{chat_type} ɴᴏᴍʙʀᴇ</b> ⇝ <code>{chat_title}</code>\n"
    if chat.username:
        caption += f"<b>• ʟɪɴᴋ</b> ⇝ @{chat.username}\n"
    else:
        caption += f"<b>{chat_type} ᴛɪᴘᴏ</b> ⇝ <code>Privado</code>\n"
    if creator_username:
        caption += f"<b>• ᴄʀᴇᴀᴅᴏʀ</b> ⇝ {creator_username}\n"
    elif creator_valid:
        caption += f'<b>• ᴄʀᴇᴀᴅᴏʀ</b> ⇝ <a href="tg://user?id={creator_id}">{creator_firstname}</a>\n'
    if created:
        caption += f"<b>• ᴄʀᴇᴀᴅᴏ</b> ⇝ <code>{created.date().strftime('%b %d, %Y')} - {created.time()}</code>\n"
    else:
        caption += f"<b>• ᴄʀᴇᴀᴅᴏ</b> ⇝ <code>{chat.date.date().strftime('%b %d, %Y')} - {chat.date.time()}</code>\n"
    caption += f"<b>• ᴅᴀᴛᴀ ᴄᴇɴᴛᴇʀ ɪᴅ</b> ⇝  <code>{dc_id}</code>\n"
    if exp_count is not None:
        chat_level = int((1 + math.sqrt(1 + 7 * exp_count / 14)) / 2)
        caption += f"<b>{chat_type} ʟᴇᴠᴇʟ</b> ⇝ <code>{chat_level}</code>\n"
    if messages_viewable is not None:
        caption += f"<b>• ᴍᴇɴꜱᴀᴊᴇꜱ ᴠɪꜱɪʙʟᴇꜱ</b> ⇝ <code>{messages_viewable}</code>\n"
    if messages_sent:
        caption += f"<b>• ᴛᴏᴛᴀʟ ᴅᴇ ᴍᴇɴꜱᴀᴊᴇꜱ</b> ⇝ <code>{messages_sent}</code>\n"
    elif messages_sent_alt:
        caption += f"<b>• ᴛᴏᴛᴀʟ ᴅᴇ ᴍᴇɴꜱᴀᴊᴇꜱ</b> ⇝ <code>{messages_sent_alt}</code> ⚠\n"
    if members is not None:
        caption += f"<b>• ᴍɪᴇᴍʙʀᴏꜱ</b> ⇝ <code>{members}</code>\n"
    if admins:
        caption += f"<b>• ᴀᴅᴍɪɴɪꜱ</b> ⇝ <code>{admins}</code>\n"
    if full.bot_info:
        caption += f"<b>• ʙᴏᴛꜱ</b> ⇝ <code>{len(full.bot_info)}</code>\n"
    if members_online:
        caption += f"<b>• ᴍɪᴇᴍʙʀᴏꜱ ᴏɴʟɪɴᴇ</b> ⇝ <code>{members_online}</code>\n"
    if restricted_users is not None:
        caption += f"<b>• ᴍɪᴇᴍʙʀᴏꜱ ʀᴇꜱᴛʀɪɴɢɪᴅᴏꜱ</b> ⇝ <code>{restricted_users}</code>\n"
    if banned_users:
        caption += f"<b>• ᴜꜱᴜᴀʀɪᴏꜱ ʙᴀɴᴇᴀᴅᴏꜱ</b> ⇝ <code>{banned_users}</code>\n"
    if group_stickers:
        caption += f'<b>{chat_type} ꜱᴛɪᴄᴋᴇʀꜱ</b> ⇝ <a href="t.me/addstickers/{full.stickerset.short_name}">{group_stickers}</a>\n'
    if not broadcast:
        if getattr(chat, "slowmode_enabled", None):
            caption += f"<b>• ꜱʟᴏᴡ ᴍᴏᴅᴇ</b> ⇝ <code>Sí✔</code>"
            caption += f" <code>[{full.slowmode_seconds}s]</code>\n"
        else:
            caption += f"<b>• ꜱᴜᴘᴇʀɢʀᴜᴘᴏ</b> ⇝ <code>{supergroup}</code>\n"
    if getattr(chat, "restricted", None):
        caption += f"<b>• ʀᴇꜱᴛʀɪɴɢɪɢᴏ</b> ⇝ <code>{chat.restricted}</code>\n"
        rist = chat.restriction_reason[0]
        caption += f"> PLATAFORMA ⇝ <code>{rist.platform}</code>\n"
        caption += f"> MOTIVO ⇝ <code>{rist.reason}</code>\n"
        caption += f"> TEXTO ⇝ <code>{rist.text}</code>\n\n"
    if getattr(chat, "scam", None):
        caption += "<b>• ꜱᴄᴀᴍ:</b> <b>Yes</b>\n"
    if getattr(chat, "verified", None):
        caption += f"<b>• ᴠᴇʀɪꜰɪᴄᴀᴅᴏ</b> ⇝ <code>Yes</code>\n\n"
    if full.about:
        caption += f"<b>• ᴅᴇᴛᴀʟʟᴇ</b> ↯ \n<code>{full.about}</code>\n"
    return chat_photo, caption
