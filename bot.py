#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Discord 봇의 메인 모듈.

이 모듈은 Discord 봇의 핵심 기능을 구현하고 봇을 실행하는 진입점을 제공합니다.
"""

import asyncio
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Union
from http.server import HTTPServer, BaseHTTPRequestHandler

import discord
from discord.ext import commands
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("discord_bot")

# 환경 변수 로드
load_dotenv(".env.secret")
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("COMMAND_PREFIX", "!")
PORT = int(os.getenv("PORT", "8088"))

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# 봇 인스턴스 생성
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# 상태 확인용 HTTP 서버 핸들러
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """상태 확인 요청에 대한 응답을 처리합니다."""
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Bot is running')
        
    def log_message(self, format, *args):
        """HTTP 서버 로그 메시지를 Discord 봇 로거로 리다이렉트합니다."""
        logger.info(f"Health check: {format % args}")

def start_http_server():
    """상태 확인을 위한 HTTP 서버를 시작합니다."""
    server = HTTPServer(('0.0.0.0', PORT), HealthCheckHandler)
    logger.info(f"상태 확인 서버가 포트 {PORT}에서 시작되었습니다.")
    server.serve_forever()

# 별도의 스레드에서 HTTP 서버 시작
def run_http_server():
    """별도의 스레드에서 HTTP 서버를 실행합니다."""
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    logger.info("상태 확인 HTTP 서버 스레드가 시작되었습니다.")


@bot.event
async def on_ready() -> None:
    """
    봇이 시작되고 Discord에 연결되었을 때 실행되는 이벤트 핸들러.
    
    봇의 기본 정보를 로깅하고 상태를 설정합니다.
    """
    if bot.user:
        logger.info(f"{bot.user.name}({bot.user.id})이(가) 성공적으로 연결되었습니다.")
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name=f"{PREFIX}help"
            )
        )
    
    # 로드된 Cog 목록 출력
    logger.info("로드된 Cog 목록:")
    for cog in bot.cogs:
        logger.info(f"- {cog}")


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """
    명령어 실행 중 오류가 발생했을 때 실행되는 이벤트 핸들러.
    
    Args:
        ctx: 명령어 컨텍스트
        error: 발생한 오류
    """
    # 레이드 관리용 특수 명령어인 경우 오류 메시지를 표시하지 않음
    if isinstance(error, commands.CommandNotFound):
        command_text = ctx.message.content.strip()
        raid_commands = ["!추가", "!제거", "!수정"]
        
        for cmd in raid_commands:
            if command_text.startswith(cmd):
                return  # 레이드 명령어는 오류 메시지 표시하지 않고 종료
    
    # 일반적인 오류 처리
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"명령어를 찾을 수 없습니다. `{PREFIX}help`를 입력하여 사용 가능한 명령어를 확인하세요.")
    elif isinstance(error, commands.MissingRequiredArgument):
        command_name = ctx.command.name if ctx.command else "알 수 없음"
        await ctx.send(f"필수 인자가 누락되었습니다. `{PREFIX}help {command_name}`를 입력하여 사용법을 확인하세요.")
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"명령어 재사용 대기 중입니다. {error.retry_after:.2f}초 후에 다시 시도하세요.")
    else:
        logger.error(f"명령어 '{ctx.command}' 실행 중 오류 발생: {error}", exc_info=True)
        await ctx.send(f"명령어 실행 중 오류가 발생했습니다: {str(error)}")


@bot.command(name="ping")
async def ping(ctx: commands.Context) -> None:
    """
    봇의 응답 속도를 확인하는 명령어.
    
    Args:
        ctx: 명령어 컨텍스트
    """
    latency = round(bot.latency * 1000)
    await ctx.send(f"퐁! 지연 시간: {latency}ms")


async def load_extensions() -> None:
    """
    확장 모듈(Cog)들을 로드합니다.
    """
    # cogs 디렉토리가 존재하면 모든 확장 모듈을 로드
    if os.path.exists("cogs"):
        for filename in os.listdir("cogs"):
            if filename.endswith(".py") and not filename.startswith("_"):
                try:
                    await bot.load_extension(f"cogs.{filename[:-3]}")
                    logger.info(f"확장 모듈 로드 성공: cogs.{filename[:-3]}")
                except Exception as e:
                    logger.error(f"확장 모듈 로드 실패: cogs.{filename[:-3]} - {e}")


async def main() -> None:
    """
    봇의 메인 실행 함수.
    
    확장 모듈을 로드하고 봇을 시작합니다.
    """
    # 상태 확인 HTTP 서버 시작
    run_http_server()
    
    async with bot:
        await load_extensions()
        logger.info("봇 시작 중...")
        if not TOKEN:
            logger.error("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.")
            return
        await bot.start(TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("키보드 인터럽트로 봇이 종료되었습니다.")
    except Exception as e:
        logger.error(f"봇 실행 중 오류 발생: {e}", exc_info=True) 