#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
동기 방식으로 로스트아크 캐릭터 정보를 수집하는 스크립트.
"""

import logging
from services.lostark_service import collect_and_save_character_info_sync

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

if __name__ == "__main__":
    print("동기 방식으로 캐릭터 정보 수집을 시작합니다...")
    collect_and_save_character_info_sync()
    print("캐릭터 정보 수집 완료!") 