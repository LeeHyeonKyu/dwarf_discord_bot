#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
config_utils 모듈 단위 테스트.

이 모듈은 YAML 설정 파일 로드 및 메시지 포맷팅 기능을 테스트합니다.
"""

import os
import tempfile
import pytest
from typing import Dict, List, Any, cast, Generator
import yaml
from pytest_mock import MockerFixture

from utils.config_utils import load_yaml_config, format_raid_message, aload_yaml_config


@pytest.fixture
def mock_raids_config() -> Dict[str, List[Dict[str, Any]]]:
    """
    테스트용 모의 레이드 설정을 제공합니다.
    
    Returns:
        모의 레이드 설정
    """
    return {
        "raids": [
            {
                "name": "노기르",
                "members": 8,
                "min_level": 1660,
                "max_level": 1680,
                "description": "카제로스 1막 노말",
                "elapsed_time": 30
            },
            {
                "name": "하기르",
                "members": 8,
                "min_level": 1680,
                "max_level": None,
                "description": "카제로스 1막 하드",
                "elapsed_time": 30
            }
        ]
    }


@pytest.fixture
def temp_yaml_file(mock_raids_config: Dict[str, List[Dict[str, Any]]]) -> Generator[str, None, None]:
    """
    임시 YAML 파일을 생성하는 fixture.
    
    Args:
        mock_raids_config: 모의 레이드 설정
        
    Yields:
        임시 YAML 파일 경로
    """
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", encoding='utf-8', delete=False) as tmp:
        yaml.dump(mock_raids_config, tmp, allow_unicode=True)
        temp_path = tmp.name
    
    yield temp_path
    
    # 테스트 종료 후 임시 파일 삭제
    os.unlink(temp_path)


class TestConfigUtils:
    """
    config_utils 모듈 테스트 클래스.
    """
    
    def test_load_yaml_config(self, temp_yaml_file: str) -> None:
        """
        load_yaml_config 함수가 YAML 파일을 올바르게 로드하는지 테스트합니다.
        
        Args:
            temp_yaml_file: 임시 YAML 파일 경로
        """
        # 설정 파일 로드
        config = load_yaml_config(temp_yaml_file)
        
        # 검증
        assert "raids" in config
        assert len(config["raids"]) == 2
        assert config["raids"][0]["name"] == "노기르"
        assert config["raids"][1]["min_level"] == 1680
        assert config["raids"][1]["max_level"] is None
    
    def test_load_yaml_config_file_not_found(self) -> None:
        """
        load_yaml_config 함수가 존재하지 않는 파일에 대해 오류를 발생시키는지 테스트합니다.
        """
        with pytest.raises(FileNotFoundError):
            load_yaml_config("non_existent_file.yaml")
    
    def test_format_raid_message_with_max_level(self) -> None:
        """
        format_raid_message 함수가 최대 레벨이 있는 레이드 정보를 올바르게 포맷팅하는지 테스트합니다.
        """
        # 테스트 데이터
        raid = {
            "name": "테스트 레이드",
            "members": 8,
            "min_level": 1600,
            "max_level": 1700,
            "description": "테스트 설명",
            "elapsed_time": 45
        }
        
        # 메시지 포맷팅
        message = format_raid_message(raid)
        
        # 검증
        assert "## 테스트 레이드 (테스트 설명)" in message
        assert "- 최소 레벨: 1600" in message
        assert "- 최대 레벨: 1700" in message
        assert "- 인원: 8명" in message
        assert "- 예상 소요 시간: 45분" in message
    
    def test_format_raid_message_without_max_level(self) -> None:
        """
        format_raid_message 함수가 최대 레벨이 없는 레이드 정보를 올바르게 포맷팅하는지 테스트합니다.
        """
        # 테스트 데이터
        raid = {
            "name": "테스트 레이드",
            "members": 8,
            "min_level": 1600,
            "max_level": None,
            "description": "테스트 설명",
            "elapsed_time": 45
        }
        
        # 메시지 포맷팅
        message = format_raid_message(raid)
        
        # 검증
        assert "## 테스트 레이드 (테스트 설명)" in message
        assert "- 최소 레벨: 1600" in message
        assert "- 최대 레벨: 제한 없음" in message
        assert "- 인원: 8명" in message
        assert "- 예상 소요 시간: 45분" in message
    
    def test_format_raid_message_with_missing_fields(self) -> None:
        """
        format_raid_message 함수가 일부 필드가 누락된 레이드 정보를 올바르게 처리하는지 테스트합니다.
        """
        # 일부 필드가 누락된 테스트 데이터
        raid = {
            "name": "테스트 레이드"
        }
        
        # 메시지 포맷팅
        message = format_raid_message(raid)
        
        # 검증
        assert "## 테스트 레이드 ()" in message
        assert "- 최소 레벨: 알 수 없음" in message
        assert "- 최대 레벨: 제한 없음" in message
        assert "- 인원: 0명" in message
        assert "- 예상 소요 시간: 0분" in message
    
    @pytest.mark.asyncio
    async def test_aload_yaml_config(self, temp_yaml_file: str) -> None:
        """
        aload_yaml_config 함수가 YAML 파일을 올바르게 비동기적으로 로드하는지 테스트합니다.
        
        Args:
            temp_yaml_file: 임시 YAML 파일 경로
        """
        # 비동기 설정 파일 로드
        config = await aload_yaml_config(temp_yaml_file)
        
        # 검증
        assert "raids" in config
        assert len(config["raids"]) == 2
        assert config["raids"][0]["name"] == "노기르"
        assert config["raids"][1]["min_level"] == 1680 