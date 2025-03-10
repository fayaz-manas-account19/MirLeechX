import logging
import re
import threading
import time
import math

from bot.helper.telegram_helper.bot_commands import BotCommands
from bot import dispatcher, download_dict, download_dict_lock, STATUS_LIMIT
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
from bot.helper.telegram_helper import button_build, message_utils

LOGGER = logging.getLogger(__name__)

MAGNET_REGEX = r"magnet:\?xt=urn:btih:[a-zA-Z0-9]*"

URL_REGEX = r"(?:(?:https?|ftp):\/\/)?[\w/\-?=%.]+\.[\w/\-?=%.]+"

COUNT = 0
PAGE_NO = 1


class MirrorStatus:
    STATUS_UPLOADING = "𝗨𝗽𝗹𝗼𝗮𝗱𝗶𝗻𝗴...📤"
    STATUS_DOWNLOADING = "𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝗶𝗻𝗴...📥"
    STATUS_CLONING = "𝗖𝗹𝗼𝗻𝗶𝗻𝗴...♻️"
    STATUS_WAITING = "𝗤𝘂𝗲𝘂𝗲𝗱...📝"
    STATUS_FAILED = "𝗙𝗮𝗶𝗹𝗲𝗱 🚫. 𝗖𝗹𝗲𝗮𝗻𝗶𝗻𝗴 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱..."
    STATUS_PAUSE = "𝗣𝗮𝘂𝘀𝗲𝗱...⭕️"
    STATUS_ARCHIVING = "𝗔𝗿𝗰𝗵𝗶𝘃𝗶𝗻𝗴...🔐"
    STATUS_EXTRACTING = "𝗘𝘅𝘁𝗿𝗮𝗰𝘁𝗶𝗻𝗴...📂"
    STATUS_SPLITTING = "𝗦𝗽𝗹𝗶𝘁𝘁𝗶𝗻𝗴...✂️"

SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']


class setInterval:
    def __init__(self, interval, action):
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()
        thread = threading.Thread(target=self.__setInterval)
        thread.start()

    def __setInterval(self):
        nextTime = time.time() + self.interval
        while not self.stopEvent.wait(nextTime - time.time()):
            nextTime += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()

def get_readable_file_size(size_in_bytes) -> str:
    if size_in_bytes is None:
        return '0B'
    index = 0
    while size_in_bytes >= 1024:
        size_in_bytes /= 1024
        index += 1
    try:
        return f'{round(size_in_bytes, 2)}{SIZE_UNITS[index]}'
    except IndexError:
        return 'File too large'

def getDownloadByGid(gid):
    with download_dict_lock:
        for dl in download_dict.values():
            status = dl.status()
            if (
                status
                not in [
                    MirrorStatus.STATUS_ARCHIVING,
                    MirrorStatus.STATUS_EXTRACTING,
                    MirrorStatus.STATUS_SPLITTING,
                ]
                and dl.gid() == gid
            ):
                return dl
    return None

def getAllDownload():
    with download_dict_lock:
        for dlDetails in download_dict.values():
            status = dlDetails.status()
            if (
                status
                not in [
                    MirrorStatus.STATUS_ARCHIVING,
                    MirrorStatus.STATUS_EXTRACTING,
                    MirrorStatus.STATUS_SPLITTING,
                    MirrorStatus.STATUS_CLONING,
                    MirrorStatus.STATUS_UPLOADING,
                ]
                and dlDetails
            ):
                return dlDetails
    return None

def get_progress_bar_string(status):
    completed = status.processed_bytes() / 9
    total = status.size_raw() / 9
    p = 0 if total == 0 else round(completed * 100 / total)
    p = min(max(p, 0), 100)
    cFull = p // 9
    p_str = '■' * cFull
    p_str += '□' * (11 - cFull)
    p_str = f"[{p_str}]"
    return p_str

def get_readable_message():
    with download_dict_lock:
        msg = ""
        start = 0
        if STATUS_LIMIT is not None:
            dick_no = len(download_dict)
            global pages
            pages = math.ceil(dick_no/STATUS_LIMIT)
            if pages != 0 and PAGE_NO > pages:
                globals()['COUNT'] -= STATUS_LIMIT
                globals()['PAGE_NO'] -= 1
            start = COUNT
        for index, download in enumerate(list(download_dict.values())[start:], start=1):
            reply_to = download.message.reply_to_message
            msg += f"<b>▬▬▬▬▬  @KOT_BOTS ▬▬▬▬▬\n\n➜ 𝗙𝗶𝗹𝗲𝗻𝗮𝗺𝗲 :</b><code>{download.name()}</code>"
            msg += f"\n<b>➜ 𝗦𝘁𝗮𝘁𝘂𝘀 :{download.status()}</b>"
            if download.status() not in [
                MirrorStatus.STATUS_ARCHIVING,
                MirrorStatus.STATUS_EXTRACTING,
                MirrorStatus.STATUS_SPLITTING,
            ]:
                msg += f"\n{get_progress_bar_string(download)} {download.progress()}"
                if download.status() == MirrorStatus.STATUS_CLONING:
                    msg += f"\n<b>➜ 𝗖𝗹𝗼𝗻𝗲𝗱 :</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                elif download.status() == MirrorStatus.STATUS_UPLOADING:
                    msg += f"\n<b>➜ 𝗨𝗽𝗹𝗼𝗮𝗱𝗲𝗱 :</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                else:
                    msg += f"\n<b>➜ 𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝗲𝗱 :</b> {get_readable_file_size(download.processed_bytes())} of {download.size()}"
                msg += f"\n<b>➜ 𝗦𝗽𝗲𝗲𝗱 :</b> {download.speed()} | <b>ETA:</b> {download.eta()}"
                if reply_to:
                    msg += f"\n<b>➜ 𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗕𝘆 : <a href='tg://user?id={download.message.from_user.id}'>{download.message.from_user.first_name}</a></b>"
                else:
                    msg += f"\n<b>➜ 𝗥𝗲𝗾𝘂𝗲𝘀𝘁𝗲𝗱 𝗕𝘆 : <a href='tg://user?id={download.message.from_user.id}'>{download.message.from_user.first_name}</a></b>"
                # if hasattr(download, 'is_torrent'):
                try:
                    msg += f"\n<b>➜ 𝗨𝗦𝗘𝗥 𝗜𝗗 :</b><code>/warn {download.message.from_user.id}</code>"
                except:
                    pass
                try:
                    msg += f"\n<b>➜ 𝗦𝗲𝗲𝗱𝗲𝗿𝘀 :</b> {download.aria_download().num_seeders}" \
                           f" | <b>➜ 𝗣𝗲𝗲𝗿𝘀 :</b> {download.aria_download().connections}"
                except:
                    pass
                try:
                    msg += f"\n<b>➜ 𝗦𝗲𝗲𝗱𝗲𝗿𝘀 :</b> {download.torrent_info().num_seeds}" \
                           f" | <b>➜ 𝗟𝗲𝗲𝗰𝗵𝗲𝗿𝘀 :</b> {download.torrent_info().num_leechs}"
                except:
                    pass
                msg += f"\n<b>➜ 𝗧𝗼 𝗖𝗮𝗻𝗰𝗲𝗹 :</b><code>/{BotCommands.CancelMirror} {download.gid()}</code>\n\n══════════════════════════════════════════"
            msg += "\n\n"
            if STATUS_LIMIT is not None and index == STATUS_LIMIT:
                break
        if STATUS_LIMIT is not None and dick_no > STATUS_LIMIT:
            msg += f"<b>𝗣𝗮𝗴𝗲 :</b> {PAGE_NO}/{pages} | <b>𝗧𝗮𝘀𝗸𝘀 :</b> {dick_no}\n"
            buttons = button_build.ButtonMaker()
            buttons.sbutton("<--- 𝗣𝗿𝗲𝘃𝗶𝗼𝘂𝘀", "pre")
            buttons.sbutton("𝗡𝗲𝘅𝘁 --->", "nex")
            button = InlineKeyboardMarkup(buttons.build_menu(2))
            return msg, button
        return msg, ""

def turn(update, context):
    query = update.callback_query
    query.answer()
    global COUNT, PAGE_NO
    if query.data == "nex":
        if PAGE_NO == pages:
            COUNT = 0
            PAGE_NO = 1
        else:
            COUNT += STATUS_LIMIT
            PAGE_NO += 1
    elif query.data == "pre":
        if PAGE_NO == 1:
            COUNT = STATUS_LIMIT * (pages - 1)
            PAGE_NO = pages
        else:
            COUNT -= STATUS_LIMIT
            PAGE_NO -= 1
    message_utils.update_all_messages()

def get_readable_time(seconds: int) -> str:
    result = ''
    (days, remainder) = divmod(seconds, 86400)
    days = int(days)
    if days != 0:
        result += f'{days}d'
    (hours, remainder) = divmod(remainder, 3600)
    hours = int(hours)
    if hours != 0:
        result += f'{hours}h'
    (minutes, seconds) = divmod(remainder, 60)
    minutes = int(minutes)
    if minutes != 0:
        result += f'{minutes}m'
    seconds = int(seconds)
    result += f'{seconds}s'
    return result

def is_url(url: str):
    url = re.findall(URL_REGEX, url)
    return bool(url)

def is_gdrive_link(url: str):
    return "drive.google.com" in url

def is_mega_link(url: str):
    return "mega.nz" in url or "mega.co.nz" in url

def get_mega_link_type(url: str):
    if "folder" in url:
        return "folder"
    elif "file" in url:
        return "file"
    elif "/#F!" in url:
        return "folder"
    return "file"

def is_magnet(url: str):
    magnet = re.findall(MAGNET_REGEX, url)
    return bool(magnet)

def new_thread(fn):
    """To use as decorator to make a function call threaded.
    Needs import
    from threading import Thread"""

    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=fn, args=args, kwargs=kwargs)
        thread.start()
        return thread

    return wrapper


next_handler = CallbackQueryHandler(turn, pattern="nex", run_async=True)
previous_handler = CallbackQueryHandler(turn, pattern="pre", run_async=True)
dispatcher.add_handler(next_handler)
dispatcher.add_handler(previous_handler)
