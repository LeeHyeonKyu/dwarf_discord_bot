#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 정보 및 참여 가능 캐릭터 정보 게시 테스트 스크립트.

이 스크립트는 레이드 정보를 전송하고 해당 레이드에 참여 가능한 캐릭터 목록을 함께 게시합니다.
"""

import asyncio
import argparse
import logging
import os
import sys
from typing import Dict, Any, Optional

import discord
from dotenv import load_dotenv

# 프로젝트 루트 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.config_utils import load_yaml_config
from utils.discord_utils import send_raid_info_with_characters

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("test_raids_with_characters")

# 환경 변수 로드
load_dotenv(".env.secret")
TOKEN = os.getenv("DISCORD_TOKEN")

# 테스트용 채널 ID 설정
TEST_CHANNEL_ID = int(os.getenv("TEST_CHANNEL_ID", "0"))  # 실제 채널 ID로 변경 필요


async def main(raid_name: Optional[str] = None, update_characters: bool = False) -> None:
    """
    메인 함수.
    
    Args:
        raid_name: 특정 레이드 이름 (지정하지 않으면 첫 번째 레이드 사용)
        update_characters: 캐릭터 정보를 업데이트할지 여부
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
            
            # 레이드 선택
            selected_raid = None
            if raid_name:
                # 특정 레이드 이름이 지정된 경우
                for raid in raids:
                    if raid.get("name", "").lower() == raid_name.lower():
                        selected_raid = raid
                        break
                
                if not selected_raid:
                    logger.error(f"'{raid_name}' 레이드를 찾을 수 없습니다.")
                    await client.close()
                    return
            else:
                # 레이드 이름이 지정되지 않은 경우 첫 번째 레이드 사용
                selected_raid = raids[0]
            
            # 레이드 정보 전송 및 참여 가능 캐릭터 게시
            raid_display_name = selected_raid.get("name", "알 수 없는 레이드")
            logger.info(f"'{raid_display_name}' 레이드 정보 및 참여 가능 캐릭터 정보 게시 중...")
            
            thread = await send_raid_info_with_characters(client, TEST_CHANNEL_ID, selected_raid, update_characters)
            
            if thread:
                logger.info(f"'{raid_display_name}' 레이드 정보 및 참여 가능 캐릭터 정보 게시 완료")
            else:
                logger.error(f"'{raid_display_name}' 레이드 정보 전송 실패")
            
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
    # 명령줄 인자 파서 설정
    parser = argparse.ArgumentParser(description='레이드 정보 및 참여 가능 캐릭터 정보 게시 테스트')
    parser.add_argument(
        '--raid',
        type=str,
        default=None,
        help='특정 레이드 이름 (지정하지 않으면 첫 번째 레이드 사용)'
    )
    parser.add_argument(
        '--update',
        action='store_true',
        help='캐릭터 정보를 업데이트할지 여부'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='디버그 로깅 활성화'
    )
    
    # 명령줄 인자 파싱
    args = parser.parse_args()
    
    # 로깅 레벨 설정
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("discord_utils").setLevel(logging.DEBUG)
    
    # 메인 함수 실행
    asyncio.run(main(raid_name=args.raid, update_characters=args.update)) 