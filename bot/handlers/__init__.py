from aiogram import Dispatcher

from .start import router as start_router
from .create_quiz import router as create_router
from .common import router as common_router
from .time_limit import router as time_router
from .poll_quiz import router as poll_quiz_router
from .settings import router as settings_router
from .inline import router as inline_router

def setup_routers(dp: Dispatcher) -> None:
    dp.include_router(start_router)
    dp.include_router(create_router)
    dp.include_router(common_router)
    dp.include_router(time_router)
    dp.include_router(poll_quiz_router)
    dp.include_router(settings_router)
    dp.include_router(inline_router)
