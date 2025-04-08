#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI 서비스 테스트 스크립트.
"""

import logging
import asyncio
import sys
import os

# 로깅 설정
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_raid_command")

# 현재 디렉토리를 기준으로 파이썬 경로 설정
sys.path.append(os.getcwd())

from services.openai_service import OpenAIService


async def test_command_parsing():
    """커맨드 파싱 테스트"""
    service = OpenAIService()
    
    # 테스트할 명령어 목록
    test_commands = [
        "추가 1딜",
        "추가 1폿",
        "추가 1딜 1폿",
        "추가 2딜 2폿",
        "추가 1차 딜러",
        "제거 1차 딜러",
        "수정 1차 토 21시"
    ]
    
    for cmd in test_commands:
        logger.info(f"========== 테스트 명령어: {cmd} ==========")
        result = await service.parse_raid_command("test_user", cmd)
        logger.info(f"파싱 결과: {result}")
        
        # 검증 및 포맷팅 테스트
        formatted = await service.validate_and_format_commands(result, "test_user")
        logger.info(f"포맷팅 결과: {formatted}")
        logger.info(f"========== 테스트 완료 ==========\n")


async def main():
    """메인 함수"""
    await test_command_parsing()


if __name__ == "__main__":
    asyncio.run(main()) 