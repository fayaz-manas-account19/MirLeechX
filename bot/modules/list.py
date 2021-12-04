from telegram.ext import CommandHandler
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot import LOGGER, dispatcher
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.bot_utils import new_thread


@new_thread
def list_drive(update, context):
    try:
        search = update.message.text.split(' ', maxsplit=1)[1]
        LOGGER.info(f"Searching: {search}")
        reply = sendMessage('Searching... Please wait!', context.bot, update)
        gdrive = GoogleDriveHelper()
        msg, button = gdrive.drive_list(search)
        if button:
            editMessage(msg, reply, button)
        else:
            editMessage(f'No result found for <i>{search}</i>', reply)
    except IndexError:
        sendMessage('Send a search key along with command', context.bot, update)

def gdtot_cloner(update, context):
    if update.message.from_user.username:
        uname = f'@{update.message.from_user.username}'
    else:
        uname = f'<a href="tg://user?id={update.message.from_user.id}">{update.message.from_user.first_name}</a>'
    if uname is not None:
        cc = f'\n\n<b>cc: </b>{uname}'
    try:
        search_ = update.message.text.split(' ',maxsplit=1)[1]
        links_ = search_.split(' ')
        button = None
        for search in links_:
            reply = sendMessage('Extracting please wait ....', context.bot, update)
            gdrive = GoogleDriveHelper()
            gdtot = GDTOT(search)
            if STOP_DUPLICATE:
                file_name_ = gdtot.get_filename()
                if file_name_ is not None:
                    smsg, button = gdrive.drive_list(file_name_)
                    if smsg:
                        msg3 = "File is already available in Drive.\nHere are the search results:"
                        editMessage(msg3, reply, button)
                        return
                else:
                    editMessage('The provided link Invlied ....', reply, button)
                    return
            LOGGER.info(f"Extracting gdtot link: {search}")
            button = None
            file_name, file_url = gdtot.parse(search)
            if file_name == 404:
                sendMessage(file_url, context.bot, update)
                return
            if file_url != 404:
                msg, button = gdrive.clone(file_url)
                delete_msg = gdrive.deletefile(file_url)
            if button:
                editMessage(msg + cc, reply, button)
            else:
                editMessage(file_name, reply, button)
    except IndexError:
        sendMessage('Send cmd along with url', context.bot, update)
    except Exception as e:
        LOGGER.info(e)
        
list_handler = CommandHandler(BotCommands.ListCommand, list_drive, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
gdtot_handler = CommandHandler(BotCommands.GDTOTCommand, gdtot_cloner, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
dispatcher.add_handler(list_handler)
dispatcher.add_handler(gdtot_handler)
