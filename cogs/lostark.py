#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
로스트아크 관련 기능을 제공하는 Cog 모듈.

이 모듈은 로스트아크 캐릭터 정보 수집, 조회 등의 명령어를 제공합니다.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional

import discord
import yaml
from discord.ext import commands

from services.lostark_service import LostarkService, collect_and_save_character_info

# 로깅 설정
logger = logging.getLogger("lostark_cog")


class Lostark(commands.Cog):
    """
    로스트아크 관련 기능을 제공하는 Cog.
    
    이 클래스는 로스트아크 캐릭터 정보 수집, 조회 등의 명령어를 제공합니다.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        로스트아크 Cog 초기화.
        
        Args:
            bot: 봇 인스턴스
        """
        self.bot = bot
        self.lostark_service = LostarkService()
        
        # 봇 시작시 자동으로 멤버 정보 수집하지 않음
        # self.bot.loop.create_task(self._init_character_data())
    
    async def _init_character_data(self) -> None:
        """
        봇 시작시 백그라운드로 캐릭터 정보를 초기화합니다.
        """
        logger.info("캐릭터 정보 초기화 중...")
        try:
            await collect_and_save_character_info()
            logger.info("캐릭터 정보 초기화 완료")
        except Exception as e:
            logger.error(f"캐릭터 정보 초기화 실패: {str(e)}")
    
    @commands.command(name="캐릭터갱신", aliases=["캐릭터업데이트", "캐릭터수집"])
    @commands.is_owner()  # 봇 소유자만 실행 가능
    async def update_characters(self, ctx: commands.Context) -> None:
        """
        모든 멤버의 캐릭터 정보를 수집하고 저장합니다.
        """
        # 명령어 실행 메시지
        message = await ctx.send("캐릭터 정보 수집 중... 잠시만 기다려주세요.")
        
        try:
            # 비동기적으로 캐릭터 정보 수집 실행
            data = await self.lostark_service.collect_all_members_characters_async()
            
            # 데이터 저장
            self.lostark_service.save_members_characters_info(data)
            
            # 결과 요약
            total_members = len(data)
            total_characters = sum(len(chars) for chars in data.values())
            
            # 결과 메시지 업데이트
            await message.edit(content=f"캐릭터 정보 수집 완료! {total_members}명의 멤버, 총 {total_characters}개의 캐릭터 정보를 갱신했습니다.")
            
        except Exception as e:
            logger.error(f"캐릭터 정보 수집 중 오류: {str(e)}", exc_info=True)
            await message.edit(content=f"캐릭터 정보 수집 중 오류가 발생했습니다: {str(e)}")
    
    @commands.command(name="캐릭터목록", aliases=["캐릭터리스트", "캐릭터"])
    async def list_characters(self, ctx: commands.Context, member_id: Optional[str] = None) -> None:
        """
        멤버의 캐릭터 목록을 표시합니다.
        
        Args:
            member_id: 조회할 멤버 ID. 지정하지 않으면 모든 멤버의 캐릭터 요약 정보를 표시합니다.
        """
        # 캐릭터 정보 파일이 존재하는지 확인
        character_file_path = "data/members_character_info.yaml"
        if not os.path.exists(character_file_path):
            await ctx.send("캐릭터 정보 파일이 존재하지 않습니다. `!캐릭터갱신` 명령어를 사용하여 정보를 수집해주세요.")
            return
        
        try:
            # 캐릭터 정보 로드
            with open(character_file_path, 'r', encoding='utf-8') as file:
                character_data = self.lostark_service._load_members_config()
                data = {}
                
                # 멤버 설정 파일에서 멤버 정보 가져오기 (discord_name 등)
                member_info = {}
                # discord_id를 키로 하는 매핑 생성
                discord_id_to_member = {}
                for member in character_data:
                    member_id = member.get('id')
                    discord_id = member.get('discord_id', '')
                    
                    member_info[discord_id] = {
                        'id': member_id,
                        'discord_name': member.get('discord_name', '알 수 없음'),
                        'active': member.get('active', False)
                    }
                    
                    discord_id_to_member[member_id] = discord_id
            
            # 캐릭터 정보 파일 로드
            with open(character_file_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file) or {}
            
            # 특정 멤버 지정된 경우
            if member_id:
                # member_id로 discord_id 찾기 시도
                discord_id = discord_id_to_member.get(member_id)
                
                # 직접 지정된 ID가 discord_id인지 확인
                if member_id in data:
                    discord_id = member_id
                # member_id로 변환된 discord_id로 찾기
                elif discord_id in data:
                    pass
                else:
                    await ctx.send(f"'{member_id}' 멤버의 캐릭터 정보를 찾을 수 없습니다.")
                    return
                
                # 해당 멤버의 캐릭터 정보로 임베드 생성
                member_characters = data[discord_id]
                member_display_id = member_info.get(discord_id, {}).get('id', 'Unknown')
                discord_name = member_info.get(discord_id, {}).get('discord_name', '알 수 없음')
                
                embed = discord.Embed(
                    title=f"{discord_name}({member_display_id})의 캐릭터 정보",
                    description=f"총 {len(member_characters)}개의 캐릭터",
                    color=discord.Color.blue()
                )
                
                # 캐릭터 정보를 아이템 레벨 내림차순으로 정렬
                sorted_characters = sorted(
                    member_characters,
                    key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
                    reverse=True
                )
                
                # 임베드에 캐릭터 정보 추가
                for character in sorted_characters:
                    char_name = character.get('CharacterName', '알 수 없음')
                    server_name = character.get('ServerName', '알 수 없음')
                    char_class = character.get('CharacterClassName', '알 수 없음')
                    item_level = character.get('ItemMaxLevel', '0')
                    
                    embed.add_field(
                        name=f"{char_name} ({server_name})",
                        value=f"클래스: {char_class}\n레벨: {item_level}",
                        inline=True
                    )
                
                await ctx.send(embed=embed)
            
            # 멤버 ID가 지정되지 않은 경우 전체 요약 정보 표시
            else:
                embed = discord.Embed(
                    title="멤버 캐릭터 정보 요약",
                    description=f"총 {len(data)}명의 멤버 정보",
                    color=discord.Color.green()
                )
                
                # 각 멤버별 캐릭터 수와 최고 레벨 캐릭터 정보
                for discord_id, characters in data.items():
                    if not characters:
                        continue
                    
                    # 멤버 정보 가져오기
                    member_display_id = member_info.get(discord_id, {}).get('id', 'Unknown')
                    discord_name = member_info.get(discord_id, {}).get('discord_name', '알 수 없음')
                    
                    # 최고 레벨 캐릭터 찾기
                    highest_character = max(
                        characters,
                        key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', ''))
                    )
                    
                    highest_level = highest_character.get('ItemMaxLevel', '0')
                    highest_name = highest_character.get('CharacterName', '알 수 없음')
                    highest_class = highest_character.get('CharacterClassName', '알 수 없음')
                    
                    embed.add_field(
                        name=f"{discord_name}({member_display_id})",
                        value=f"캐릭터 수: {len(characters)}개\n최고 레벨: {highest_name} ({highest_class}) - {highest_level}",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
        except Exception as e:
            logger.error(f"캐릭터 정보 조회 중 오류: {str(e)}", exc_info=True)
            await ctx.send(f"캐릭터 정보 조회 중 오류가 발생했습니다: {str(e)}")
    
    @update_characters.error
    async def update_characters_error(self, ctx: commands.Context, error: commands.CommandError) -> None:
        """
        캐릭터 갱신 명령어 오류 처리.
        
        Args:
            ctx: 명령어 컨텍스트
            error: 발생한 오류
        """
        if isinstance(error, commands.NotOwner):
            await ctx.send("이 명령어는 봇 소유자만 사용할 수 있습니다.")
        else:
            logger.error(f"캐릭터 갱신 명령어 오류: {str(error)}", exc_info=True)
            await ctx.send(f"명령어 실행 중 오류가 발생했습니다: {str(error)}")


async def setup(bot: commands.Bot) -> None:
    """
    Cog를 봇에 추가합니다.
    
    Args:
        bot: 봇 인스턴스
    """
    await bot.add_cog(Lostark(bot)) 