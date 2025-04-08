#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI 서비스 테스트 모듈.

이 모듈은 OpenAI API를 사용한 레이드 명령어 파싱 기능을 테스트합니다.
"""

import logging
import os
import json
import asyncio
import pytest
from typing import Dict, List, Any, Optional, cast
from unittest.mock import patch, MagicMock, AsyncMock

from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock.plugin import MockerFixture

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_openai_service")

# 시스템 경로에 프로젝트 루트 추가
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.openai_service import OpenAIService

# pytest-asyncio 설정
pytest_plugins = ['pytest_asyncio']


@pytest.fixture
def openai_service() -> OpenAIService:
    """
    OpenAI 서비스 인스턴스를 생성하는 fixture.
    
    Returns:
        OpenAIService 인스턴스
    """
    return OpenAIService()


@pytest.mark.asyncio
async def test_parse_raid_command(openai_service: OpenAIService, caplog: LogCaptureFixture) -> None:
    """
    레이드 명령어 파싱 기능을 테스트합니다.
    
    Args:
        openai_service: OpenAIService 인스턴스
        caplog: 로그 캡처 fixture
    """
    caplog.set_level(logging.DEBUG)
    
    # 테스트할 명령어 목록
    test_commands = [
        "추가 1딜",
        "추가 1폿",
        "추가 1딜 1폿",
        "추가 2딜 2폿",
        "추가 1차 딜러",
        "제거 1차 딜러",
        "수정 1차 토 21시",
        "제거 1딜 2폿"
    ]
    
    user_id = "test_user_123"
    
    for cmd in test_commands:
        logger.info(f"========== 테스트 명령어: {cmd} ==========")
        # 원본 명령어 로깅
        logger.info(f"입력: user_id={user_id}, command_text={cmd}")
        
        # 명령어 파싱
        commands = await openai_service.parse_raid_command(user_id, cmd)
        
        # 파싱 결과 로깅
        logger.info(f"파싱 결과: {json.dumps(commands, ensure_ascii=False, indent=2)}")
        
        # 검증 및 포맷팅
        valid_commands = await openai_service.validate_and_format_commands(commands, user_id)
        
        # 최종 결과 로깅
        logger.info(f"검증 및 포맷팅 결과: {json.dumps(valid_commands, ensure_ascii=False, indent=2)}")
        logger.info(f"검증된 명령어 개수: {len(valid_commands)}")
        logger.info("========== 테스트 완료 ==========\n")
        
        # 명령어 검증
        assert isinstance(valid_commands, list)
        
        # 명령어 개수 검증 (2딜 2폿의 경우 4개, 1딜 1폿의 경우 2개 등)
        if "2딜 2폿" in cmd:
            assert len(valid_commands) == 4
        elif "1딜 1폿" in cmd:
            assert len(valid_commands) == 2
        
        # 각 명령어의 필수 필드 검증
        for command in valid_commands:
            assert "user" in command
            assert "command" in command
            assert command["user"] == user_id


@pytest.mark.asyncio
async def test_parse_raid_command_with_discord_message(openai_service: OpenAIService, mocker: MockerFixture) -> None:
    """
    디스코드 메시지 객체를 사용한 레이드 명령어 파싱을 테스트합니다.
    
    Args:
        openai_service: OpenAIService 인스턴스
        mocker: pytest-mock fixture
    """
    # Discord 메시지 목 객체 생성
    mock_author = mocker.MagicMock()
    mock_author.id = 123456789
    
    mock_message = mocker.MagicMock()
    mock_message.content = "추가 2딜 1폿"
    mock_message.author = mock_author
    
    # OpenAI API 응답 모킹
    fake_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps([
                        {"user": str(mock_author.id), "command": "add", "role": "dps", "round": None, "round_edit": None},
                        {"user": str(mock_author.id), "command": "add", "role": "dps", "round": None, "round_edit": None},
                        {"user": str(mock_author.id), "command": "add", "role": "sup", "round": None, "round_edit": None}
                    ])
                }
            }
        ]
    }
    
    # aiohttp 세션 모킹
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=fake_response)
    
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post = AsyncMock(return_value=mock_response)
    
    # ClientSession 모킹
    mocker.patch('aiohttp.ClientSession', return_value=mock_session)
    
    # 명령어 파싱
    logger.info(f"========== 디스코드 메시지 테스트 ==========")
    logger.info(f"입력: message.content={mock_message.content}, message.author.id={mock_message.author.id}")
    
    commands = await openai_service.parse_raid_command(mock_message, mock_message.content)
    
    # 파싱 결과 로깅
    logger.info(f"파싱 결과: {json.dumps(commands, ensure_ascii=False, indent=2)}")
    
    # 검증 및 포맷팅
    valid_commands = await openai_service.validate_and_format_commands(commands, str(mock_message.author.id))
    
    # 최종 결과 로깅
    logger.info(f"검증 및 포맷팅 결과: {json.dumps(valid_commands, ensure_ascii=False, indent=2)}")
    logger.info("========== 테스트 완료 ==========\n")
    
    # 명령어 검증
    assert isinstance(valid_commands, list)
    assert len(valid_commands) == 3  # 2딜 1폿 -> 3개의 명령어
    
    # 사용자 ID 확인
    for command in valid_commands:
        assert command["user"] == str(mock_message.author.id)


@pytest.mark.asyncio
async def test_mock_openai_response(mocker: MockerFixture) -> None:
    """
    OpenAI API 응답을 모킹하여 명령어 파싱을 테스트합니다.
    
    Args:
        mocker: pytest-mock fixture
    """
    # 가짜 응답 데이터 준비
    fake_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps([
                        {"user": "test_user", "command": "add", "role": "dps", "round": None, "round_edit": None},
                        {"user": "test_user", "command": "add", "role": "dps", "round": None, "round_edit": None},
                        {"user": "test_user", "command": "add", "role": "sup", "round": None, "round_edit": None}
                    ])
                }
            }
        ]
    }
    
    # aiohttp 세션 모킹
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value=fake_response)
    
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.post = AsyncMock(return_value=mock_response)
    
    # ClientSession 모킹
    mocker.patch('aiohttp.ClientSession', return_value=mock_session)
    
    # OpenAI 서비스 생성
    service = OpenAIService(api_key="fake_api_key")
    
    # 명령어 파싱
    logger.info(f"========== OpenAI API 모킹 테스트 ==========")
    
    command_text = "추가 2딜 1폿"
    user_id = "test_user"
    
    logger.info(f"입력: user_id={user_id}, command_text={command_text}")
    logger.info(f"모킹된 OpenAI 응답: {json.dumps(fake_response, ensure_ascii=False, indent=2)}")
    
    commands = await service.parse_raid_command(user_id, command_text)
    
    # 결과 로깅
    logger.info(f"파싱 결과: {json.dumps(commands, ensure_ascii=False, indent=2)}")
    logger.info("========== 테스트 완료 ==========\n")
    
    # 검증
    assert len(commands) == 3
    assert commands[0]["command"] == "add"
    assert commands[0]["role"] == "dps"
    assert commands[1]["command"] == "add"
    assert commands[1]["role"] == "dps"
    assert commands[2]["command"] == "add"
    assert commands[2]["role"] == "sup"


if __name__ == "__main__":
    # 직접 실행 시 테스트 수행
    # 로깅 설정
    logging.basicConfig(level=logging.INFO, 
                      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # OpenAI 서비스 인스턴스 생성
    service = OpenAIService()
    
    # 테스트 함수 직접 호출
    async def run_test():
        # 테스트 명령어 리스트 일부만 사용
        test_commands = ["추가 1딜", "추가 1차 딜러"]
        user_id = "test_user_123"
        
        for cmd in test_commands:
            logger.info(f"========== 테스트 명령어: {cmd} ==========")
            logger.info(f"입력: user_id={user_id}, command_text={cmd}")
            
            # 명령어 파싱
            commands = await service.parse_raid_command(user_id, cmd)
            
            # 파싱 결과 로깅
            logger.info(f"파싱 결과: {json.dumps(commands, ensure_ascii=False, indent=2)}")
            
            # 검증 및 포맷팅
            valid_commands = await service.validate_and_format_commands(commands, user_id)
            
            # 최종 결과 로깅
            logger.info(f"검증 및 포맷팅 결과: {json.dumps(valid_commands, ensure_ascii=False, indent=2)}")
            logger.info("========== 테스트 완료 ==========\n")
    
    # 비동기 테스트 실행
    asyncio.run(run_test()) 