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
                    # 1. ID는 _raw에서 안전하게 가져옵니다. (기존 유지)
                    offset_id = last._raw.top_message
        
                    # 2. [핵심 수정] 날짜를 0으로 바로 설정하지 않고, r.messages에서 검색합니다.
                    # Restricted 채널이라도 API 응답의 'messages' 리스트(Vector<Message>)에는 
                    # 해당 ID의 메시지 헤더 정보(date 등)가 들어있는 경우가 많습니다.
                    
                    # 먼저 High-level 객체에 있는지 확인
                    if last.top_message:
                        offset_date = utils.datetime_to_timestamp(last.top_message.date)
                    else:
                        # High-level에 없으면(None이면), Raw 응답(r)의 messages 목록을 뒤집니다.
                        # r은 invoke로 받아온 변수입니다.
                        found_raw_msg = next((m for m in r.messages if m.id == offset_id), None)
                        
                        if found_raw_msg:
                            # 찾았다! 진짜 날짜를 사용합니다. (무한 루프 방지)
                            offset_date = found_raw_msg.date
                            print(f"[Fix] Found hidden date for restricted chat: {offset_date}")
                        else:
                            # 진짜로 정보가 아예 없으면 어쩔 수 없이 0 사용
                            offset_date = 0
        
                    # 3. Peer 설정 (기존 유지)
                    offset_peer = await self.resolve_peer(last.chat.id)
                except Exception as e: # restrict chat
                    traceback.print_exc()

            for dialog in dialogs:
                yield dialog

                current += 1

                if current >= total:
                    return
