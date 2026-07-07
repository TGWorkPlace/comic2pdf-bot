# CBR/CBZ → PDF Telegram Bot

Detects `.cbr` and `.cbz` comic archives sent to the bot, converts them to
`.pdf` using the [`comic2pdf`](https://pypi.org/project/comic2pdf/) CLI
tool, and uploads the PDF back to the user.

## How it works

1. `bot.py` listens for any document whose file name ends in `.cbz` or `.cbr`.
2. The file is downloaded to a per-job temp folder under `DOWNLOAD_DIR`.
3. `comic2pdf -o <job_dir> -a <input_file>` is run as a subprocess.
   - `.cbz` files are ZIP archives of images — no extra dependency needed.
   - `.cbr` files are RAR archives — extraction needs `unrar` (or a
     compatible tool) on `PATH`. The Dockerfile installs `unar`
     (The Unarchiver), which the underlying `rarfile` library auto-detects
     and uses as a fallback backend.
4. The resulting PDF is uploaded back to the chat, and the temp folder is
   deleted.

## Environment variables

| Variable          | Required | Description                                  |
|-------------------|----------|-----------------------------------------------|
| `API_ID`          | yes      | Telegram API ID from my.telegram.org          |
| `API_HASH`        | yes      | Telegram API hash from my.telegram.org        |
| `BOT_TOKEN`       | yes      | Bot token from @BotFather                     |
| `DOWNLOAD_DIR`    | no       | Temp folder for downloads (default `downloads`) |
| `MAX_FILE_SIZE_MB`| no       | Reject files bigger than this (default `500`, `0` disables) |

## Running locally

```bash
pip install -r requirements.txt
export API_ID=... API_HASH=... BOT_TOKEN=...
python bot.py
```

You'll also need `unrar` or `unar` installed locally for `.cbr` support
(e.g. `apt install unar` on Debian/Ubuntu, `brew install unar` on macOS).

## Deploying to Koyeb

The included `Dockerfile` installs `unar` for CBR support and exposes port
`8080` for Koyeb's health checks (`webserver.py`). Set the three required
env vars in the Koyeb service settings and deploy.

## Commands

- `/start` — welcome message
- `/help` — usage instructions
- Send a `.cbr` or `.cbz` file — converts and returns a `.pdf`
