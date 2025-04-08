#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
설정 파일 및 메시지 포맷팅 관련 유틸리티 모듈.

이 모듈은 YAML 설정 파일 로드 및 메시지 포맷팅을 위한 유틸리티 함수를 제공합니다.
"""

import os
from typing import Dict, List, Any, Optional, Union

import yaml


def load_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    YAML 설정 파일을 로드합니다.
    
    Args:
        file_path: 설정 파일 경로
        
    Returns:
        설정 정보 딕셔너리
        
    Raises:
        FileNotFoundError: 파일을 찾을 수 없는 경우
        yaml.YAMLError: YAML 파싱 오류가 발생한 경우
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"YAML 파싱 오류: {str(e)}")


def format_raid_message(raid: Dict[str, Any]) -> str:
    """
    레이드 정보를 포맷팅된 메시지로 변환합니다.
    
    Args:
        raid: 레이드 정보 딕셔너리
        
    Returns:
        포맷팅된 레이드 메시지
    """
    name = raid.get('name', '알 수 없음')
    description = raid.get('description', '')
    min_level = raid.get('min_level', '알 수 없음')
    max_level = raid.get('max_level')
    
    # 헤더 생성
    message = f"## {name} ({description})\n"
    
    # 최소/최대 레벨 정보 추가
    message += f"- 최소 레벨: {min_level}\n"
    
    # 최대 레벨이 있을 경우만 추가
    if max_level:
        message += f"- 최대 레벨: {max_level}\n"
    else:
        message += "- 최대 레벨: 제한 없음\n"
    
    # 인원 수와 예상 소요 시간 정보 추가
    members = raid.get('members', 0)
    elapsed_time = raid.get('elapsed_time', 0)
    
    message += f"- 인원: {members}명\n"
    message += f"- 예상 소요 시간: {elapsed_time}분\n"
    
    return message


async def aload_yaml_config(file_path: str) -> Dict[str, Any]:
    """
    YAML 설정 파일을 비동기적으로 로드하는 래퍼 함수.
    
    Args:
        file_path: 설정 파일 경로
        
    Returns:
        설정 정보 딕셔너리
        
    Raises:
        FileNotFoundError: 파일을 찾을 수 없는 경우
        yaml.YAMLError: YAML 파싱 오류가 발생한 경우
    """
    return load_yaml_config(file_path) 