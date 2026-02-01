#  Pyrogram - Telegram MTProto API Client Library for Python
#  Copyright (C) 2017-present Dan <https://github.com/delivrance>
#
#  This file is part of Pyrogram.
#
#  Pyrogram is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pyrogram is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with Pyrogram.  If not, see <http://www.gnu.org/licenses/>.

import traceback
from typing import AsyncGenerator, Optional

import pyrogram
from pyrogram import types, raw, utils


class GetDialogs:
    async def get_dialogs(
        self: "pyrogram.Client",
        limit: int = 0
    ) -> Optional[AsyncGenerator["types.Dialog", None]]:
        """Get a user's dialogs sequentially.

        .. include:: /_includes/usable-by/users.rst

        Parameters:
            limit (``int``, *optional*):
                Limits the number of dialogs to be retrieved.
                By default, no limit is applied and all dialogs are returned.

        Returns:
            ``Generator``: A generator yielding :obj:`~pyrogram.types.Dialog` objects.

        Example:
            .. code-block:: python

                # Iterate through all dialogs
                async for dialog in app.get_dialogs():
                    print(dialog.chat.first_name or dialog.chat.title)
        """
        current = 0
        total = limit or (1 << 31) - 1
        limit = min(100, total)

        offset_date = 0
        offset_id = 0
        offset_peer = raw.types.InputPeerEmpty()

        while True:
            r = await self.invoke(
                raw.functions.messages.GetDialogs(
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_peer=offset_peer,
                    limit=limit,
                    hash=0
                ),
                sleep_threshold=60
            )

            users = {i.id: i for i in r.users}
            chats = {i.id: i for i in r.chats}

            messages = {}

            for message in r.messages:
                if isinstance(message, raw.types.MessageEmpty):
                    continue

                chat_id = utils.get_peer_id(message.peer_id)
                messages[chat_id] = await types.Message._parse(
                    self,
                    message,
                    users,
                    chats,
                    replies=self.fetch_replies
                )

            dialogs = []

            for dialog in r.dialogs:
                if not isinstance(dialog, raw.types.Dialog):
                    continue

                dialogs.append(types.Dialog._parse(self, dialog, messages, users, chats))

            if not dialogs:
                return

            last = dialogs[-1]

            if last:
                try:
                    if last.top_message:
                        # 정상적인 채팅방: 메시지 객체에서 ID와 날짜를 가져옴
                        offset_id = last.top_message.id
                        offset_date = utils.datetime_to_timestamp(last.top_message.date)
                    else:
                        # Restricted 채팅방: top_message가 None임
                        # raw(TL Object)에서 정수형 ID를 직접 가져오고, 날짜는 0으로 설정
                        offset_id = last._raw.top_message
                        offset_date = 0 
                    
                    # Peer는 채팅방 ID로 변환 (기존 유지)
                    offset_peer = await self.resolve_peer(last.chat.id)
                except Exception as e: # restrict chat
                    traceback.print_exc()

            for dialog in dialogs:
                yield dialog

                current += 1

                if current >= total:
                    return
