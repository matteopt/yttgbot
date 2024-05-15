import os
import yaml
import shutil
import random
import logging
from glob import glob
from uuid import uuid4
from telegram import Update, MessageEntity
from telegram.ext import Application, CallbackContext, CommandHandler, MessageHandler, filters
from yt_dlp import YoutubeDL


class CustomLogger:
    def error(msg):
        print(msg)
    def warning(msg):
        return
    def debug(msg):
        return


class Config:

    def __init__(self, config):
        self.name = config["name"]
        self.chats = config.get("chats", [])
        self.groups = config.get("groups", [])
        self.messages = {
            k: config.get("messages", {}).get(k, []) for k in
                [
                    "start",
                    "download",
                    "upload",
                    "done",
                    "error"
                ]
        }


class Bot:

    def __init__(self, token: str, config: Config):
        self.log = logging.getLogger(__name__)
        self.config = config
        self.app = Application.builder().token(token).build()

        self.app.add_handler(MessageHandler(
            filters.ChatType.PRIVATE &
            filters.TEXT &
            (
                filters.Entity(MessageEntity.URL) |
                filters.Entity(MessageEntity.TEXT_LINK)
            ),
            self.download_chat
        ))

        self.app.add_handler(MessageHandler(
            filters.ChatType.GROUPS &
            filters.TEXT &
            filters.Entity(MessageEntity.MENTION) &
            (~ filters.FORWARDED) &
            (
                filters.Entity(MessageEntity.URL) |
                filters.Entity(MessageEntity.TEXT_LINK)
            ),
            self.download_group
        ))

        self.app.add_handler(MessageHandler(
            filters.ChatType.GROUPS &
            filters.TEXT &
            filters.Entity(MessageEntity.MENTION) &
            (~ filters.FORWARDED) &
            filters.REPLY,
            self.download_group_reply
        ))

    def mentioned(self, update: Update):
        mentions = filter(lambda e: e.type == MessageEntity.MENTION, update.message.entities)
        for m in mentions:
            if update.message.text[m.offset:m.offset+m.length] == f"@{self.config.name}":
                return True
        return False

    def run(self):
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    async def download_chat(self, update: Update, context: CallbackContext):
        self.log.debug(update.message.text)
        if update.message.chat.id in self.config.chats:
            await self.download(update, update.message)

    async def download_group(self, update: Update, context: CallbackContext):
        self.log.debug(update.message.text)
        if update.message.chat.id in self.config.groups and self.mentioned(update):
            await self.download(update, update.message)

    async def download_group_reply(self, update: Update, context: CallbackContext):
        self.log.debug(update.message.text)
        if update.message.chat.id in self.config.groups and self.mentioned(update):
            await self.download(update, update.message.reply_to_message)

    def get_url(message: MessageEntity):
        url_entities = filter(lambda e: e.type in [MessageEntity.URL, MessageEntity.TEXT_LINK], message.entities)
        url_entity = next(url_entities)

        if url_entity.type == MessageEntity.TEXT_LINK:
            return url_entity.url
        else:
            return message.text[url_entity.offset:url_entity.offset+url_entity.length]

    async def download(self, update: Update, message: MessageEntity):
        id = str(uuid4())
        os.mkdir(f"./tmp/{id}")

        print(id, message.chat.id, message.text)
        await self.download_url(id, Bot.get_url(message), update)

    async def download_url(self, id: str, url: str, update: Update):
        ydl_opts = {
            "quiet": True,
            "outtmpl": f"./tmp/{id}/" + "%(title)s.%(ext)s",
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0"
            }],
            "logger": CustomLogger
        }
        try:
            await update.message.reply_text(random.choice(self.config.messages["download"]))
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            for fn in glob(f"./tmp/{id}/*"):
                with open(fn, "rb") as f:
                    await update.message.reply_text(random.choice(self.config.messages["upload"]), quote=False)
                    await update.message.reply_audio(f, quote=False)
                    await update.message.reply_text(random.choice(self.config.messages["done"]), quote=False)
        except Exception as e:
            print(e)
            await update.message.reply_text(random.choice(self.config.messages["error"]))
        finally:
            shutil.rmtree(f"./tmp/{id}")


def main():
    logging.basicConfig(level=logging.DEBUG)
    token = os.environ["TOKEN"]
    with open("config.yaml", "r") as f:
        config = Config(yaml.load(f, yaml.Loader))
    bot = Bot(token, config)
    bot.run()


if __name__ == "__main__":
    main()
