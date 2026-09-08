from aiogram.filters import BaseFilter
from aiogram.types import Message


class IsPlatformAdmin(BaseFilter):
    """
    Only allows the Telegram ID set in PLATFORM_ADMIN_ID to pass through
    the handler. Add this filter to any handler that should only be
    accessible to you (the easymakebot platform admin):

        @router.message(Command("admin_panel"), IsPlatformAdmin())
        async def admin_panel(message: Message) -> None: ...
    """

    def __init__(self, platform_admin_id: int) -> None:
        self.platform_admin_id = platform_admin_id

    async def __call__(self, message: Message) -> bool:
        return message.from_user is not None and (
            message.from_user.id == self.platform_admin_id
        )
