#!/usr/bin/env python3
"""
XianyuAutoAgent - Main entry point
Automatically handles Xianyu (闲鱼) messages using AI agents
"""

import os
import time
import json
import logging
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from XianyuApis import XianyuApis
from XianyuAgent import XianyuReplyBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('xianyu_agent.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


class XianyuAutoAgent:
    """Main agent that polls for new messages and auto-replies using AI."""

    def __init__(self):
        self.cookies = os.getenv('XIANYU_COOKIES', '')
        self.poll_interval = int(os.getenv('POLL_INTERVAL', '10'))
        self.api = XianyuApis()
        self.bot = XianyuReplyBot()
        self._running = False
        self._processed_msg_ids = set()

    def _load_cookies(self) -> dict:
        """Parse cookie string into dict."""
        cookies = {}
        if not self.cookies:
            logger.warning('No cookies configured. Set XIANYU_COOKIES in .env')
            return cookies
        for part in self.cookies.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                cookies[k.strip()] = v.strip()
        return cookies

    def _check_login(self) -> bool:
        """Verify that current session is authenticated."""
        cookies = self._load_cookies()
        if not cookies:
            return False
        logged_in = self.api.hasLogin(cookies)
        if not logged_in:
            logger.error('Session expired or invalid. Please refresh cookies.')
        return logged_in

    def _handle_message(self, msg: dict) -> None:
        """Process a single incoming message and send AI reply."""
        try:
            msg_id = msg.get('msgId') or msg.get('id')
            if not msg_id or msg_id in self._processed_msg_ids:
                return

            sender = msg.get('senderNick', 'buyer')
            content = msg.get('content', '')
            item_id = msg.get('itemId', '')
            item_title = msg.get('itemTitle', '')

            logger.info(f'New message from {sender}: {content[:80]}')

            # Generate reply using the AI agent
            reply = self.bot.reply(
                user_message=content,
                item_title=item_title,
                item_id=item_id
            )

            if reply:
                cookies = self._load_cookies()
                success = self.api.sendMessage(
                    cookies=cookies,
                    to_user_id=msg.get('senderId', ''),
                    item_id=item_id,
                    content=reply
                )
                if success:
                    logger.info(f'Replied to {sender}: {reply[:80]}')
                    self._processed_msg_ids.add(msg_id)
                    # Keep set from growing unbounded
                    if len(self._processed_msg_ids) > 5000:
                        self._processed_msg_ids = set(
                            list(self._processed_msg_ids)[-2500:]
                        )
                else:
                    logger.warning(f'Failed to send reply to {sender}')
        except Exception as e:
            logger.error(f'Error handling message: {e}', exc_info=True)

    def run(self) -> None:
        """Main polling loop."""
        logger.info('XianyuAutoAgent starting...')

        if not self._check_login():
            logger.error('Login check failed. Exiting.')
            return

        logger.info(f'Logged in successfully. Polling every {self.poll_interval}s')
        self._running = True

        while self._running:
            try:
                cookies = self._load_cookies()
                messages = self.api.getUnreadMessages(cookies)

                if messages:
                    logger.info(f'Fetched {len(messages)} unread message(s)')
                    for msg in messages:
                        self._handle_message(msg)
                else:
                    logger.debug('No new messages')

            except KeyboardInterrupt:
                logger.info('Interrupted by user. Shutting down...')
                self._running = False
                break
            except Exception as e:
                logger.error(f'Polling error: {e}', exc_info=True)

            time.sleep(self.poll_interval)

        logger.info('XianyuAutoAgent stopped.')


if __name__ == '__main__':
    agent = XianyuAutoAgent()
    agent.run()
