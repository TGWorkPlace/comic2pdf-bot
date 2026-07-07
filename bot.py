import asyncio
import logging
import os
import shutil
import time
import uuid

from pyrogram import Client, filters
from pyrogram.types import Message

from config import API_ID, API_HASH, BOT_TOKEN, DOWNLOAD_DIR, MAX_FILE_SIZE_MB
from webserver import run_webserver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

COMIC_EXTENSIONS = (".cbz", ".cbr")
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024 if MAX_FILE_SIZE_MB else 0


class ComicConversionError(Exception):
    """Raised when comic2pdf fails to produce a PDF."""


class Comic2PdfBot(Client):
    def __init__(self):
        super().__init__(
            name="comic2pdf_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
        )

    async def start(self, *args, **kwargs):
        await super().start(*args, **kwargs)
        me = await self.get_me()
        logger.info(f"Bot started: @{me.username}")

        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        self._web_runner = await run_webserver()

    async def stop(self, *args, **kwargs):
        if hasattr(self, "_web_runner"):
            await self._web_runner.cleanup()
        await super().stop(*args, **kwargs)
        logger.info("Bot stopped.")


app = Comic2PdfBot()


def _is_comic_file(_, __, message: Message) -> bool:
    doc = message.document
    if not doc or not doc.file_name:
        return False
    return doc.file_name.lower().endswith(COMIC_EXTENSIONS)


comic_filter = filters.create(_is_comic_file)


@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await message.reply(
        "**CBR / CBZ → PDF Converter**\n\n"
        "Send me a `.cbr` or `.cbz` comic archive and I'll convert it "
        "into a `.pdf` and send it back to you.\n\n"
        "Use /help to learn more."
    )


@app.on_message(filters.command("help") & filters.private)
async def help_handler(client: Client, message: Message):
    await message.reply(
        "Just send me a document ending in `.cbr` or `.cbz`.\n\n"
        "• **.cbz** — a renamed ZIP archive of images, works out of the box.\n"
        "• **.cbr** — a renamed RAR archive. Extracting it needs the `unrar` "
        "tool installed on the server (already set up in this bot's Docker "
        "image).\n\n"
        "I'll download the file, convert every page into a single PDF using "
        "the `comic2pdf` library, and upload the result back to you."
    )


@app.on_message(filters.private & filters.document & ~comic_filter)
async def wrong_file_handler(client: Client, message: Message):
    doc = message.document
    if doc and doc.file_name:
        await message.reply(
            "I only convert `.cbr` and `.cbz` comic archives. "
            f"`{doc.file_name}` doesn't look like one of those."
        )


async def _progress(current: int, total: int, status_msg: Message, action: str, state: dict):
    now = time.time()
    if now - state.get("last_edit", 0) < 2 and current != total:
        return
    state["last_edit"] = now
    percent = (current * 100 / total) if total else 0
    try:
        await status_msg.edit_text(f"{action}... {percent:.1f}%")
    except Exception:
        pass


async def convert_to_pdf(input_path: str, out_dir: str) -> str:
    """
    Converts a .cbr/.cbz file to .pdf using the `comic2pdf` CLI tool
    (pip install comic2pdf), which internally handles RAR/ZIP extraction
    and image-to-PDF assembly.
    """
    process = await asyncio.create_subprocess_exec(
        "comic2pdf", "-o", out_dir, "-a", input_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        err = (stderr.decode(errors="ignore").strip()
               or stdout.decode(errors="ignore").strip()
               or "comic2pdf exited with a non-zero status.")
        if "unrar" in err.lower() or "rarfile" in err.lower():
            raise ComicConversionError(
                "This is a `.cbr` (RAR-based) archive and the server is "
                "missing the `unrar` tool needed to extract it."
            )
        raise ComicConversionError(err)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(out_dir, base_name + ".pdf")
    if not os.path.exists(pdf_path):
        raise ComicConversionError("comic2pdf finished but produced no PDF file.")
    return pdf_path


@app.on_message(comic_filter & filters.private)
async def convert_handler(client: Client, message: Message):
    doc = message.document
    file_name = doc.file_name

    if MAX_FILE_SIZE_BYTES and doc.file_size and doc.file_size > MAX_FILE_SIZE_BYTES:
        await message.reply(
            f"⚠️ That file is larger than the {MAX_FILE_SIZE_MB} MB limit set on this bot."
        )
        return

    job_id = uuid.uuid4().hex[:8]
    job_dir = os.path.join(DOWNLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    input_path = os.path.join(job_dir, file_name)

    status = await message.reply("📥 Downloading...")
    state = {"last_edit": 0}

    try:
        await client.download_media(
            message,
            file_name=input_path,
            progress=_progress,
            progress_args=(status, "📥 Downloading", state),
        )
    except Exception as e:
        logger.exception("Download failed")
        await status.edit_text(f"❌ Failed to download the file: {e}")
        shutil.rmtree(job_dir, ignore_errors=True)
        return

    await status.edit_text("⚙️ Converting to PDF...")

    try:
        pdf_path = await convert_to_pdf(input_path, job_dir)
    except ComicConversionError as e:
        await status.edit_text(f"❌ Conversion failed: {e}")
        shutil.rmtree(job_dir, ignore_errors=True)
        return
    except FileNotFoundError:
        logger.exception("comic2pdf executable not found")
        await status.edit_text(
            "❌ The `comic2pdf` tool isn't installed on the server. "
            "Run `pip install comic2pdf` in this bot's environment."
        )
        shutil.rmtree(job_dir, ignore_errors=True)
        return
    except Exception as e:
        logger.exception("Unexpected conversion error")
        await status.edit_text(f"❌ Unexpected error while converting: {e}")
        shutil.rmtree(job_dir, ignore_errors=True)
        return

    await status.edit_text("📤 Uploading PDF...")
    state = {"last_edit": 0}

    try:
        out_name = os.path.splitext(file_name)[0] + ".pdf"
        await client.send_document(
            chat_id=message.chat.id,
            document=pdf_path,
            file_name=out_name,
            caption=f"✅ Converted from `{file_name}`",
            progress=_progress,
            progress_args=(status, "📤 Uploading", state),
        )
        await status.delete()
    except Exception as e:
        logger.exception("Upload failed")
        await status.edit_text(f"❌ Failed to upload the PDF: {e}")
    finally:
        shutil.rmtree(job_dir, ignore_errors=True)


if __name__ == "__main__":
    app.run()
