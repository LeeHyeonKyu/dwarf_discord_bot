#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
로스트아크 API 서비스 모듈.

이 모듈은 로스트아크 API와 통신하여 캐릭터 정보를 수집하고 처리하는 기능을 제공합니다.
"""

import asyncio
import json
import logging
import os
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import aiohttp
import requests
import yaml
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger("lostark_service")


class LostarkService:
    """
    로스트아크 API와 통신하여 캐릭터 정보를 수집하고 처리하는 서비스 클래스.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        """
        LostarkService 클래스 초기화.
        
        Args:
            api_key: 로스트아크 API 키. 제공되지 않으면 환경 변수에서 로드합니다.
        """
        # API 키 설정
        if api_key:
            self.api_key = api_key
        else:
            load_dotenv(".env.secret")
            self.api_key = os.getenv("LOSTARK_API_KEY")
            if not self.api_key:
                raise ValueError("LOSTARK_API_KEY 환경 변수가 설정되지 않았습니다.")
        
        # 헤더 설정
        self.headers = {
            'accept': 'application/json',
            'authorization': f'bearer {self.api_key}'
        }

    def _load_members_config(self, config_path: str = "configs/members_config.yaml") -> List[Dict[str, Any]]:
        """
        멤버 설정 파일을 로드합니다.
        
        Args:
            config_path: 멤버 설정 파일 경로
            
        Returns:
            멤버 설정 정보 리스트
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
                return config.get('members', [])
        except Exception as e:
            logger.error(f"멤버 설정 파일 로드 실패: {e}")
            raise

    async def get_character_info_async(self, character_name: str) -> List[Dict[str, Any]]:
        """
        캐릭터 이름으로 계정 내 캐릭터 목록을 비동기로 조회합니다.
        
        Args:
            character_name: 조회할 캐릭터 이름
            
        Returns:
            계정 내 캐릭터 정보
        """
        encoded_name = urllib.parse.quote(character_name)
        siblings_url = f'https://developer-lostark.game.onstove.com/characters/{encoded_name}/siblings'
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(siblings_url, headers=self.headers) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        error_msg = await response.text()
                        logger.error(f"API 요청 실패 - 상태 코드: {response.status}, 캐릭터: {character_name}, 오류: {error_msg}")
                        return []
            except Exception as e:
                logger.error(f"API 요청 중 오류 발생 - 캐릭터: {character_name}, 오류: {str(e)}")
                return []

    def get_character_info(self, character_name: str) -> List[Dict[str, Any]]:
        """
        캐릭터 이름으로 계정 내 캐릭터 목록을 동기적으로 조회합니다.
        
        Args:
            character_name: 조회할 캐릭터 이름
            
        Returns:
            계정 내 캐릭터 정보
        """
        try:
            siblings_url = f'https://developer-lostark.game.onstove.com/characters/{urllib.parse.quote(character_name)}/siblings'
            response = requests.get(siblings_url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API 요청 실패 - 상태 코드: {response.status_code}, 캐릭터: {character_name}, 오류: {response.text}")
                return []
        except Exception as e:
            logger.error(f"API 요청 중 오류 발생 - 캐릭터: {character_name}, 오류: {str(e)}")
            return []

    def filter_characters(self, characters: List[Dict[str, Any]], min_level: float = 1600.0) -> List[Dict[str, Any]]:
        """
        캐릭터 목록에서 지정된 레벨 이상인 캐릭터만 필터링합니다.
        
        Args:
            characters: 필터링할 캐릭터 목록
            min_level: 최소 아이템 레벨
            
        Returns:
            필터링된 캐릭터 목록
        """
        filtered_characters = []
        
        for character in characters:
            # ItemMaxLevel 문자열에서 숫자만 추출 (예: "1620.00" -> 1620.0)
            try:
                item_level_str = character.get('ItemMaxLevel', '0')
                # 쉼표 제거, 숫자만 추출
                item_level_str = item_level_str.replace(',', '')
                item_level = float(item_level_str)
                
                if item_level >= min_level:
                    filtered_characters.append(character)
            except (ValueError, TypeError) as e:
                logger.warning(f"아이템 레벨 파싱 오류 - 캐릭터: {character.get('CharacterName', 'Unknown')}, 값: {character.get('ItemMaxLevel', 'None')}, 오류: {str(e)}")
                continue
        
        return filtered_characters

    async def collect_all_members_characters_async(self, min_level: float = 1600.0) -> Dict[str, Any]:
        """
        모든 멤버의 캐릭터 정보를 비동기로 수집합니다.
        
        Args:
            min_level: 최소 아이템 레벨
            
        Returns:
            멤버별 캐릭터 정보 (discord_id를 키로 사용)
        """
        members = self._load_members_config()
        result = {}
        processed_character_set: Set[str] = set()  # 중복 처리 방지용 세트
        
        for member in members:
            # 비활성 멤버 건너뛰기
            if not member.get('active', False):
                continue
            
            # discord_id로 변경 (member_id 대신)
            discord_id = member.get('discord_id')
            main_characters = member.get('main_characters', [])
            
            if not main_characters:
                continue
            
            member_characters = []
            
            # 각 메인 캐릭터별로 정보 수집
            tasks = []
            for character_name in main_characters:
                if character_name not in processed_character_set:  # 이미 처리한 캐릭터는 건너뛰기
                    processed_character_set.add(character_name)
                    tasks.append(self.get_character_info_async(character_name))
            
            # 비동기 요청 실행
            results = await asyncio.gather(*tasks)
            
            # 결과 처리
            for characters in results:
                if characters:
                    filtered_characters = self.filter_characters(characters, min_level)
                    member_characters.extend(filtered_characters)
            
            if member_characters:
                # 캐릭터 목록에서 중복 제거 (CharacterName 기준)
                unique_characters = {}
                for char in member_characters:
                    char_name = char.get('CharacterName')
                    if char_name and char_name not in unique_characters:
                        unique_characters[char_name] = char
                
                result[discord_id] = list(unique_characters.values())
        
        return result

    def collect_all_members_characters(self, min_level: float = 1600.0) -> Dict[str, Any]:
        """
        모든 멤버의 캐릭터 정보를 동기적으로 수집합니다.
        
        Args:
            min_level: 최소 아이템 레벨
            
        Returns:
            멤버별 캐릭터 정보 (discord_id를 키로 사용)
        """
        members = self._load_members_config()
        result = {}
        processed_character_set: Set[str] = set()  # 중복 처리 방지용 세트
        
        for member in members:
            # 비활성 멤버 건너뛰기
            if not member.get('active', False):
                continue
            
            # discord_id로 변경 (member_id 대신)
            discord_id = member.get('discord_id')
            main_characters = member.get('main_characters', [])
            
            if not main_characters:
                continue
            
            member_characters = []
            
            # 각 메인 캐릭터별로 정보 수집
            for character_name in main_characters:
                if character_name not in processed_character_set:  # 이미 처리한 캐릭터는 건너뛰기
                    processed_character_set.add(character_name)
                    characters = self.get_character_info(character_name)
                    if characters:
                        filtered_characters = self.filter_characters(characters, min_level)
                        member_characters.extend(filtered_characters)
            
            if member_characters:
                # 캐릭터 목록에서 중복 제거 (CharacterName 기준)
                unique_characters = {}
                for char in member_characters:
                    char_name = char.get('CharacterName')
                    if char_name and char_name not in unique_characters:
                        unique_characters[char_name] = char
                
                result[discord_id] = list(unique_characters.values())
        
        return result

    def save_members_characters_info(self, data: Dict[str, Any], output_path: str = "data/members_character_info.yaml") -> None:
        """
        수집된 멤버 캐릭터 정보를 YAML 파일로 저장합니다.
        
        Args:
            data: 저장할 멤버 캐릭터 정보
            output_path: 출력 파일 경로
        """
        # 디렉토리가 없으면 생성
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as file:
                yaml.dump(data, file, allow_unicode=True, sort_keys=False)
            logger.info(f"멤버 캐릭터 정보가 성공적으로 저장되었습니다: {output_path}")
        except Exception as e:
            logger.error(f"멤버 캐릭터 정보 저장 실패: {str(e)}")
            raise


async def collect_and_save_character_info() -> None:
    """
    멤버 캐릭터 정보를 수집하고 저장하는 비동기 헬퍼 함수.
    """
    try:
        service = LostarkService()
        data = await service.collect_all_members_characters_async()
        service.save_members_characters_info(data)
        logger.info("캐릭터 정보 수집 및 저장 완료")
    except Exception as e:
        logger.error(f"캐릭터 정보 수집 및 저장 중 오류 발생: {str(e)}")


def collect_and_save_character_info_sync() -> None:
    """
    멤버 캐릭터 정보를 수집하고 저장하는 동기 헬퍼 함수.
    """
    try:
        service = LostarkService()
        data = service.collect_all_members_characters()
        service.save_members_characters_info(data)
        logger.info("캐릭터 정보 수집 및 저장 완료")
    except Exception as e:
        logger.error(f"캐릭터 정보 수집 및 저장 중 오류 발생: {str(e)}")


if __name__ == "__main__":
    # 직접 실행시 캐릭터 정보 수집 및 저장
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    asyncio.run(collect_and_save_character_info()) 