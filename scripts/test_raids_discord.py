#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 정보 전송 및 스레드 생성 테스트 스크립트.

이 스크립트는 지정된 디스코드 채널에 레이드 정보를 전송하고 스레드를 생성합니다.
"""

import asyncio
import logging
import os
import sys
from typing import Dict, Any

import discord
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_utils import load_yaml_config
from utils.discord_utils import send_raid_info

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("test_raids_discord")

# 환경 변수 로드
load_dotenv(".env.secret")
TOKEN = os.getenv("DISCORD_TOKEN")

# 테스트용 채널 ID 설정
TEST_CHANNEL_ID = int(os.getenv("TEST_CHANNEL_ID", "0"))  # 실제 채널 ID로 변경 필요


async def main() -> None:
    """
    메인 함수.
    """
    if not TOKEN:
        logger.error("DISCORD_TOKEN 환경 변수가 설정되지 않았습니다.")
        return
    
    if TEST_CHANNEL_ID == 0:
        logger.error("TEST_CHANNEL_ID 환경 변수를 실제 채널 ID로 설정해주세요.")
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
            # 레이드 설정 로드
            config_path = "configs/raids_config.yaml"
            config = load_yaml_config(config_path)
            raids = config.get("raids", [])
            
            if not raids:
                logger.error("레이드 정보를 찾을 수 없습니다.")
                await client.close()
                return
            
            # 모든 레이드 정보 전송
            for raid in raids:
                await send_raid_info(client, TEST_CHANNEL_ID, raid)
            
            logger.info("모든 레이드 정보 전송 완료")
            
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