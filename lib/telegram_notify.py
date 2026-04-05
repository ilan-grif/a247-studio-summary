#!/usr/bin/env python3
"""
Telegram Bot API utility — send messages, buttons, and files.

Usage:
    from lib.telegram_notify import send_message
    send_message("Hello")
"""

import os
import sys
import json
import logging
import argparse
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
API_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"

MAX_MESSAGE_LENGTH = 4096

logger = logging.getLogger("telegram_notify")


def _api_call(method, payload, files=None):
    """Make a Telegram Bot API call.

    Args:
        method: API method name (e.g., "sendMessage")
        payload: dict of parameters
        files: dict of {field_name: file_path} for multipart uploads

    Returns:
        dict — API response, or None on error
    """
    url = f"{API_BASE}/{method}"

    if files:
        # Multipart form-data for file uploads
        import mimetypes
        boundary = "----TelegramBotBoundary"
        body_parts = []

        for key, value in payload.items():
            body_parts.append(
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{key}\"\r\n\r\n"
                f"{value}\r\n"
            )

        for field_name, file_path in files.items():
            filename = Path(file_path).name
            mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
            body_parts.append(
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"{field_name}\"; "
                f"filename=\"{filename}\"\r\n"
                f"Content-Type: {mime_type}\r\n\r\n"
            )
            with open(file_path, "rb") as f:
                file_data = f.read()
            body_parts.append(None)  # placeholder for binary data

        body_parts.append(f"--{boundary}--\r\n")

        # Build binary body
        body = b""
        for i, part in enumerate(body_parts):
            if part is None:
                body += file_data + b"\r\n"
            else:
                body += part.encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
    else:
        # JSON for text-only calls
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("ok"):
                return result.get("result")
            else:
                logger.error(f"Telegram API error: {result.get('description')}")
                return None
    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error {e.code}: {e.read().decode()}")
        return None
    except Exception as e:
        logger.error(f"Request failed: {e}")
        return None


def send_message(text, chat_id=None, parse_mode="HTML", reply_to=None):
    """Send a text message.

    Args:
        text: Message text (max 4096 chars, auto-split if longer)
        chat_id: Target chat (defaults to TELEGRAM_CHAT_ID)
        parse_mode: "HTML" or "MarkdownV2"
        reply_to: Message ID to reply to

    Returns:
        dict — sent message, or None on error
    """
    chat_id = chat_id or CHAT_ID

    # Split long messages
    if len(text) > MAX_MESSAGE_LENGTH:
        chunks = _split_text(text)
        last_result = None
        for chunk in chunks:
            last_result = send_message(chunk, chat_id=chat_id,
                                       parse_mode=parse_mode, reply_to=reply_to)
        return last_result

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_to:
        payload["reply_to_message_id"] = reply_to

    return _api_call("sendMessage", payload)


def send_buttons(text, buttons, chat_id=None, parse_mode="HTML", columns=2):
    """Send a message with inline keyboard buttons.

    Args:
        text: Message text
        buttons: list of dicts with "text" and "callback_data" keys
        chat_id: Target chat (defaults to TELEGRAM_CHAT_ID)
        parse_mode: "HTML" or "MarkdownV2"
        columns: Number of buttons per row

    Returns:
        dict — sent message, or None on error
    """
    chat_id = chat_id or CHAT_ID

    # Arrange buttons into rows
    rows = []
    for i in range(0, len(buttons), columns):
        row = [{"text": b["text"], "callback_data": b["callback_data"]}
               for b in buttons[i:i + columns]]
        rows.append(row)

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "reply_markup": json.dumps({"inline_keyboard": rows}),
    }

    return _api_call("sendMessage", payload)


def send_video(file_path, caption=None, chat_id=None, buttons=None):
    """Upload and send a video file.

    Telegram limits: 50MB for sendVideo, 2GB for sendDocument.
    For files >50MB, falls back to sendDocument.

    Args:
        file_path: Path to video file
        caption: Optional caption (max 1024 chars)
        chat_id: Target chat
        buttons: Optional inline keyboard buttons

    Returns:
        dict — sent message, or None on error
    """
    chat_id = chat_id or CHAT_ID
    file_size = Path(file_path).stat().st_size

    # Choose method based on file size
    method = "sendVideo" if file_size < 50 * 1024 * 1024 else "sendDocument"

    payload = {"chat_id": chat_id}
    if caption:
        payload["caption"] = caption[:1024]
        payload["parse_mode"] = "HTML"

    if buttons:
        rows = []
        for i in range(0, len(buttons), 2):
            row = [{"text": b["text"], "callback_data": b["callback_data"]}
                   for b in buttons[i:i + 2]]
            rows.append(row)
        payload["reply_markup"] = json.dumps({"inline_keyboard": rows})

    file_field = "video" if method == "sendVideo" else "document"
    return _api_call(method, payload, files={file_field: file_path})


def send_file(file_path, caption=None, chat_id=None):
    """Upload and send any file as a document.

    Args:
        file_path: Path to file
        caption: Optional caption
        chat_id: Target chat

    Returns:
        dict — sent message, or None on error
    """
    chat_id = chat_id or CHAT_ID
    payload = {"chat_id": chat_id}
    if caption:
        payload["caption"] = caption[:1024]
        payload["parse_mode"] = "HTML"
    return _api_call("sendDocument", payload, files={"document": file_path})


def update_message(message_id, text, chat_id=None, parse_mode="HTML",
                   buttons=None):
    """Edit an existing message's text and/or buttons.

    Args:
        message_id: ID of the message to edit
        text: New text
        chat_id: Target chat
        parse_mode: "HTML" or "MarkdownV2"
        buttons: Optional new inline keyboard

    Returns:
        dict — edited message, or None on error
    """
    chat_id = chat_id or CHAT_ID
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if buttons:
        rows = []
        for i in range(0, len(buttons), 2):
            row = [{"text": b["text"], "callback_data": b["callback_data"]}
                   for b in buttons[i:i + 2]]
            rows.append(row)
        payload["reply_markup"] = json.dumps({"inline_keyboard": rows})

    return _api_call("editMessageText", payload)


def remove_buttons(message_id, chat_id=None):
    """Remove inline keyboard from a message (after action taken).

    Args:
        message_id: ID of the message
        chat_id: Target chat

    Returns:
        dict — edited message, or None
    """
    chat_id = chat_id or CHAT_ID
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": json.dumps({"inline_keyboard": []}),
    }
    return _api_call("editMessageReplyMarkup", payload)


def _split_text(text):
    """Split text into chunks ≤ MAX_MESSAGE_LENGTH, preferring newline breaks."""
    chunks = []
    while len(text) > MAX_MESSAGE_LENGTH:
        # Find last newline within limit
        split_at = text.rfind("\n", 0, MAX_MESSAGE_LENGTH)
        if split_at == -1:
            split_at = MAX_MESSAGE_LENGTH
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks


def main():
    parser = argparse.ArgumentParser(description="Send Telegram message")
    parser.add_argument("--message", help="Text message to send")
    parser.add_argument("--file", help="File to upload")
    parser.add_argument("--caption", help="Caption for file upload")
    parser.add_argument("--chat-id", default=CHAT_ID, help="Target chat ID")
    args = parser.parse_args()

    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not set")
        sys.exit(1)
    if not args.chat_id:
        print("Error: No chat ID (set TELEGRAM_CHAT_ID or use --chat-id)")
        sys.exit(1)

    if args.file:
        result = send_video(args.file, caption=args.caption, chat_id=args.chat_id)
    elif args.message:
        result = send_message(args.message, chat_id=args.chat_id)
    else:
        print("Error: Provide --message or --file")
        sys.exit(1)

    if result:
        print(f"Sent! Message ID: {result.get('message_id')}")
    else:
        print("Failed to send")
        sys.exit(1)


if __name__ == "__main__":
    main()
