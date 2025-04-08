#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
로스트아크 서비스 모듈에 대한 테스트.

이 모듈은 로스트아크 API 서비스의 다양한 기능을 테스트합니다.
"""

import json
import os
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
import yaml

from services.lostark_service import LostarkService

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture
    from _pytest.fixtures import FixtureRequest
    from _pytest.logging import LogCaptureFixture
    from _pytest.monkeypatch import MonkeyPatch
    from pytest_mock.plugin import MockerFixture


# 테스트 데이터 디렉토리 경로
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


@pytest.fixture
def mock_members_config() -> List[Dict[str, Any]]:
    """
    멤버 설정 테스트 데이터를 제공하는 fixture.
    
    Returns:
        멤버 설정 목록
    """
    return [
        {
            'id': 'member1',
            'discord_name': 'Member One',
            'discord_id': '123456789',
            'main_characters': ['Character1', 'Character2'],
            'active': True
        },
        {
            'id': 'member2',
            'discord_name': 'Member Two',
            'discord_id': '987654321',
            'main_characters': ['Character3'],
            'active': True
        },
        {
            'id': 'member3',
            'discord_name': 'Inactive Member',
            'discord_id': '555555555',
            'main_characters': ['Character4'],
            'active': False
        }
    ]


@pytest.fixture
def mock_character_data() -> List[Dict[str, Any]]:
    """
    캐릭터 정보 테스트 데이터를 제공하는 fixture.
    
    Returns:
        캐릭터 정보 목록
    """
    return [
        {
            'CharacterName': 'Character1',
            'ServerName': 'Server1',
            'CharacterClassName': 'Class1',
            'ItemMaxLevel': '1620.0'
        },
        {
            'CharacterName': 'Character2',
            'ServerName': 'Server1',
            'CharacterClassName': 'Class2',
            'ItemMaxLevel': '1580.0'
        },
        {
            'CharacterName': 'Character3',
            'ServerName': 'Server2',
            'CharacterClassName': 'Class1',
            'ItemMaxLevel': '1605.5'
        },
        {
            'CharacterName': 'LowLevelCharacter',
            'ServerName': 'Server1',
            'CharacterClassName': 'Class3',
            'ItemMaxLevel': '1550.0'
        }
    ]


@pytest.fixture
def setup_test_dir(request: Any) -> None:
    """
    테스트 데이터 디렉토리를 설정하는 fixture.
    
    Args:
        request: pytest 요청 객체
    """
    # 테스트 데이터 디렉토리 생성
    os.makedirs(TEST_DATA_DIR, exist_ok=True)
    
    # 테스트 후 정리 함수
    def teardown() -> None:
        # 테스트 데이터 파일 삭제
        for file in ['test_output.yaml']:
            file_path = os.path.join(TEST_DATA_DIR, file)
            if os.path.exists(file_path):
                os.remove(file_path)
    
    # 테스트 후 정리 등록
    request.addfinalizer(teardown)


@pytest.fixture
def lostark_service() -> LostarkService:
    """
    테스트용 LostarkService 인스턴스를 제공하는 fixture.
    
    Returns:
        LostarkService 인스턴스
    """
    with patch.object(LostarkService, '__init__', return_value=None):
        service = LostarkService()
        service.api_key = 'test_api_key'
        service.headers = {
            'accept': 'application/json',
            'authorization': f'bearer {service.api_key}'
        }
        return service


class TestLostarkService:
    """
    LostarkService 클래스에 대한 테스트.
    """
    
    def test_filter_characters(self, lostark_service: LostarkService, mock_character_data: List[Dict[str, Any]]) -> None:
        """
        filter_characters 메서드가 지정된 레벨 이상의 캐릭터만 필터링하는지 테스트합니다.
        
        Args:
            lostark_service: LostarkService 인스턴스
            mock_character_data: 캐릭터 정보 테스트 데이터
        """
        # 1600.0 이상 필터
        filtered = lostark_service.filter_characters(mock_character_data, min_level=1600.0)
        assert len(filtered) == 2
        assert any(char['CharacterName'] == 'Character1' for char in filtered)
        assert any(char['CharacterName'] == 'Character3' for char in filtered)
        assert not any(char['CharacterName'] == 'Character2' for char in filtered)
        assert not any(char['CharacterName'] == 'LowLevelCharacter' for char in filtered)
        
        # 1500.0 이상 필터
        filtered = lostark_service.filter_characters(mock_character_data, min_level=1500.0)
        assert len(filtered) == 4
    
    def test_filter_characters_with_invalid_data(self, lostark_service: LostarkService) -> None:
        """
        filter_characters 메서드가 잘못된 데이터를 적절히 처리하는지 테스트합니다.
        
        Args:
            lostark_service: LostarkService 인스턴스
        """
        # 잘못된 형식의 ItemMaxLevel
        invalid_data = [
            {
                'CharacterName': 'InvalidCharacter',
                'ServerName': 'Server1',
                'CharacterClassName': 'Class1',
                'ItemMaxLevel': 'not_a_number'
            },
            {
                'CharacterName': 'MissingLevelCharacter',
                'ServerName': 'Server1',
                'CharacterClassName': 'Class1'
                # ItemMaxLevel 누락
            },
            {
                'CharacterName': 'ValidCharacter',
                'ServerName': 'Server1',
                'CharacterClassName': 'Class1',
                'ItemMaxLevel': '1650.0'
            }
        ]
        
        filtered = lostark_service.filter_characters(invalid_data, min_level=1600.0)
        assert len(filtered) == 1
        assert filtered[0]['CharacterName'] == 'ValidCharacter'
    
    @patch('services.lostark_service.yaml.safe_load')
    def test_load_members_config(self, mock_yaml_load: MagicMock, lostark_service: LostarkService, mock_members_config: List[Dict[str, Any]]) -> None:
        """
        _load_members_config 메서드가 설정 파일을 올바르게 로드하는지 테스트합니다.
        
        Args:
            mock_yaml_load: yaml.safe_load에 대한 mock
            lostark_service: LostarkService 인스턴스
            mock_members_config: 멤버 설정 테스트 데이터
        """
        # yaml.safe_load가 반환할 값 설정
        mock_yaml_load.return_value = {'members': mock_members_config}
        
        # open 함수를
        with patch('builtins.open', MagicMock()):
            members = lostark_service._load_members_config('test_path.yaml')
            
            # 결과 확인
            assert members == mock_members_config
            assert len(members) == 3
            assert members[0]['id'] == 'member1'
            assert members[1]['discord_name'] == 'Member Two'
            assert members[2]['active'] is False
    
    def test_save_members_characters_info(self, lostark_service: LostarkService, setup_test_dir: None) -> None:
        """
        save_members_characters_info 메서드가 데이터를 올바르게 저장하는지 테스트합니다.
        
        Args:
            lostark_service: LostarkService 인스턴스
            setup_test_dir: 테스트 디렉토리 설정 fixture
        """
        # 테스트 데이터
        test_data = {
            'member1': [
                {
                    'CharacterName': 'Character1',
                    'ServerName': 'Server1',
                    'CharacterClassName': 'Class1',
                    'ItemMaxLevel': '1620.0'
                }
            ]
        }
        
        # 테스트 출력 파일 경로
        output_path = os.path.join(TEST_DATA_DIR, 'test_output.yaml')
        
        # 데이터 저장
        lostark_service.save_members_characters_info(test_data, output_path=output_path)
        
        # 저장된 파일 확인
        assert os.path.exists(output_path)
        
        # 저장된 내용 확인
        with open(output_path, 'r', encoding='utf-8') as file:
            saved_data = yaml.safe_load(file)
            assert saved_data == test_data
            assert 'member1' in saved_data
            assert len(saved_data['member1']) == 1
            assert saved_data['member1'][0]['CharacterName'] == 'Character1'
    
    @patch.object(LostarkService, 'get_character_info')
    @patch.object(LostarkService, '_load_members_config')
    def test_collect_all_members_characters(
        self, 
        mock_load_config: MagicMock, 
        mock_get_character_info: MagicMock,
        lostark_service: LostarkService,
        mock_members_config: List[Dict[str, Any]],
        mock_character_data: List[Dict[str, Any]]
    ) -> None:
        """
        collect_all_members_characters 메서드가 모든 멤버의 캐릭터 정보를 올바르게 수집하는지 테스트합니다.
        
        Args:
            mock_load_config: _load_members_config에 대한 mock
            mock_get_character_info: get_character_info에 대한 mock
            lostark_service: LostarkService 인스턴스
            mock_members_config: 멤버 설정 테스트 데이터
            mock_character_data: 캐릭터 정보 테스트 데이터
        """
        # Mock 설정
        mock_load_config.return_value = mock_members_config
        
        # 캐릭터별로 다른 응답 설정
        def get_character_info_side_effect(character_name: str) -> List[Dict[str, Any]]:
            if character_name == 'Character1':
                return [mock_character_data[0], mock_character_data[3]]  # 1620.0, 1550.0
            elif character_name == 'Character2':
                return [mock_character_data[1]]  # 1580.0
            elif character_name == 'Character3':
                return [mock_character_data[2]]  # 1605.5
            else:
                return []
        
        mock_get_character_info.side_effect = get_character_info_side_effect
        
        # 함수 실행
        result = lostark_service.collect_all_members_characters(min_level=1600.0)
        
        # 결과 확인
        assert len(result) == 2  # 활성 멤버 중 1600.0 이상 캐릭터를 가진 멤버
        assert 'member1' in result
        assert 'member2' in result
        assert 'member3' not in result  # 비활성 멤버
        
        # member1의 캐릭터 확인
        assert len(result['member1']) == 1
        assert result['member1'][0]['CharacterName'] == 'Character1'
        assert float(result['member1'][0]['ItemMaxLevel']) >= 1600.0
        
        # member2의 캐릭터 확인
        assert len(result['member2']) == 1
        assert result['member2'][0]['CharacterName'] == 'Character3'
        assert float(result['member2'][0]['ItemMaxLevel']) >= 1600.0 