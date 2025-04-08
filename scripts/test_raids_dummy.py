#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
더미 레이드 정보 전송 테스트 스크립트.

이 스크립트는 더미 레이드 정보를 사용하여 지정된 디스코드 채널에 메시지를 전송하고 스레드를 생성합니다.
"""

import asyncio
import argparse
import logging
import os
import sys
from typing import Dict, Any, Optional, List

import discord
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.discord_utils import send_raid_info

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("test_raids_dummy")

# 환경 변수 로드
load_dotenv(".env.secret")
TOKEN = os.getenv("DISCORD_TOKEN")

# 더미 레이드 정보
DUMMY_RAID = {
    "name": "dummy name",
    "description": "dummy description",
    "min_level": 1600,
    "max_level": 1800,
    "members": 8,
    "elapsed_time": 30
}


def find_channel_by_keyword(client: discord.Client, keyword: str) -> Optional[discord.TextChannel]:
    """
    키워드로 채널을 찾는 함수.
    
    Args:
        client: 디스코드 클라이언트
        keyword: 검색할 채널 키워드
    
    Returns:
        찾은 채널 또는 None
    """
    matching_channels: List[discord.TextChannel] = []
    
    for guild in client.guilds:
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel) and keyword.lower() in channel.name.lower():
                matching_channels.append(channel)
    
    if not matching_channels:
        return None
    
    # 여러 채널이 일치하는 경우 첫 번째 채널 반환
    if len(matching_channels) > 1:
        logger.warning(f"키워드 '{keyword}'와 일치하는 채널이 여러 개 있습니다. 첫 번째 채널을 사용합니다: {matching_channels[0].name}")
    
    return matching_channels[0]


async def main() -> None:
    """
    메인 함수.
    """
    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description="더미 레이드 정보를 디스코드 채널에 전송합니다.")
    parser.add_argument("--channel", "-c", type=str, default="test", 
                        help="레이드 정보를 전송할 채널 키워드 (기본값: 'test')")
    parser.add_argument("--channel-id", type=int, default=0,
                        help="채널 키워드 대신 직접 채널 ID를 지정할 수 있습니다.")
    args = parser.parse_args()
    
    if not TOKEN:
        logger.error("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.")
        return
    
    # 디스코드 클라이언트 설정
    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready() -> None:
        """
        클라이언트가 준비되었을 때 호출되는 이벤트 핸들러.
        """
        if client.user:
            logger.info(f"{client.user.name}({client.user.id})이(가) 성공적으로 연결되었습니다.")
        else:
            logger.info("클라이언트가 성공적으로 연결되었습니다.")
        
        try:
            channel_id = args.channel_id
            
            # 채널 ID가 제공되지 않은 경우 키워드로 채널 검색
            if channel_id == 0:
                channel = find_channel_by_keyword(client, args.channel)
                if channel:
                    channel_id = channel.id
                    logger.info(f"키워드 '{args.channel}'로 채널을 찾았습니다: {channel.name} (ID: {channel.id})")
                else:
                    logger.error(f"키워드 '{args.channel}'와 일치하는 채널을 찾을 수 없습니다.")
                    await client.close()
                    return
            
            # 더미 레이드 정보 전송
            await send_raid_info(client, channel_id, DUMMY_RAID)
            
            logger.info("더미 레이드 정보 전송 완료")
            
            # 작업 완료 후 연결 종료
            await client.close()
            
        except Exception as e:
            logger.error(f"테스트 중 오류 발생: {str(e)}")
            await client.close()
    
    try:
        await client.start(TOKEN)
    except KeyboardInterrupt:
        logger.info("Ctrl+C로 종료됨")
    except Exception as e:
        logger.error(f"실행 중 오류 발생: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main()) 