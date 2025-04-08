#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
레이드 관련 기능을 제공하는 Cog 모듈.

이 모듈은 레이드 정보 조회 및 레이드 관련 스레드 생성 기능을 제공합니다.
"""

import logging
import os
from typing import Dict, List, Any, Optional

import discord
from discord.ext import commands

from utils.config_utils import load_yaml_config, format_raid_message
from utils.discord_utils import (
    send_raid_info, 
    add_command_to_raid_history, 
    get_raid_command_history,
    process_raid_commands_and_update_schedule,
    get_raid_schedule_for_thread,
    update_thread_start_message_with_schedule,
    load_raid_data
)
from services.openai_service import OpenAIService

# 로깅 설정
logger = logging.getLogger("raids")


class Raids(commands.Cog):
    """
    레이드 관련 기능을 제공하는 Cog.
    
    이 클래스는 레이드 정보 조회 및 레이드 관련 스레드 생성 기능을 제공합니다.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        Raids Cog 초기화.
        
        Args:
            bot: 봇 인스턴스
        """
        self.bot = bot
        self.raids_config_path = "configs/raids_config.yaml"
        self.openai_service = OpenAIService()
    
    def get_raids_config(self) -> List[Dict[str, Any]]:
        """
        레이드 설정 정보를 로드합니다.
        
        Returns:
            레이드 정보 리스트
        """
        try:
            config = load_yaml_config(self.raids_config_path)
            return config.get("raids", [])
        except Exception as e:
            logger.error(f"레이드 설정 파일 로드 실패: {str(e)}")
            return []
    
    @commands.command(name="레이드목록", aliases=["레이드리스트", "레이드정보"])
    async def list_raids(self, ctx: commands.Context) -> None:
        """
        레이드 목록을 조회하고 표시합니다.
        """
        raids = self.get_raids_config()
        
        if not raids:
            await ctx.send("레이드 정보를 찾을 수 없습니다.")
            return
        
        embed = discord.Embed(
            title="레이드 목록",
            description="사용 가능한 레이드 목록입니다.",
            color=discord.Color.blue()
        )
        
        for raid in raids:
            name = raid.get("name", "알 수 없음")
            description = raid.get("description", "")
            min_level = raid.get("min_level", "알 수 없음")
            max_level = raid.get("max_level", "")
            
            value = f"최소 레벨: {min_level}\n"
            value += f"최대 레벨: {max_level if max_level else ''}\n"
            value += f"인원: {raid.get('members', 0)}명\n"
            value += f"예상 시간: {raid.get('elapsed_time', 0)}분"
            
            embed.add_field(
                name=f"{name} ({description})",
                value=value,
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.command(name="레이드생성", aliases=["레이드스레드"])
    async def create_raid_thread(self, ctx: commands.Context, *, raid_name: Optional[str] = None) -> None:
        """
        특정 레이드 또는 모든 레이드에 대한 정보 메시지를 생성하고 스레드를 시작합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            raid_name: 레이드 이름 (지정하지 않으면 모든 레이드 정보 생성)
        """
        raids = self.get_raids_config()
        
        if not raids:
            await ctx.send("레이드 정보를 찾을 수 없습니다.")
            return
        
        # 레이드 이름이 지정된 경우 해당 레이드만 필터링
        if raid_name:
            filtered_raids = [raid for raid in raids if raid.get("name", "").lower() == raid_name.lower()]
            if not filtered_raids:
                await ctx.send(f"'{raid_name}' 레이드를 찾을 수 없습니다.")
                return
            raids = filtered_raids
        
        # min_level 기준으로 레이드를 오름차순 정렬
        sorted_raids = sorted(raids, key=lambda x: x.get("min_level", 0))
        
        # 각 레이드에 대한 메시지 생성 및 스레드 생성
        for raid in sorted_raids:
            # 공통 유틸리티 함수 사용
            await send_raid_info(self.bot, ctx.channel.id, raid)
    
    async def get_raid_info_async(self, raid_name: str) -> Optional[Dict[str, Any]]:
        """
        레이드 이름으로 레이드 정보를 비동기적으로 조회합니다.
        
        Args:
            raid_name: 레이드 이름
            
        Returns:
            레이드 정보 딕셔너리 또는 None
        """
        raids = self.get_raids_config()
        for raid in raids:
            if raid.get("name", "").lower() == raid_name.lower():
                return raid
        return None

    @commands.command(name="스케줄", aliases=["일정", "레이드일정", "레이드스케줄"])
    async def show_raid_schedule(self, ctx: commands.Context) -> None:
        """
        현재 채널의 레이드 스케줄을 조회하고 표시합니다.
        """
        # 스레드인지 확인
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 레이드 스레드에서만 사용할 수 있습니다.")
            return
            
        # 스레드 ID
        thread_id = ctx.channel.id
        thread_name = ctx.channel.name
        
        # 스케줄 데이터 가져오기
        schedule = get_raid_schedule_for_thread(thread_id)
        
        # 스케줄이 없는 경우
        if not schedule or not schedule.get("rounds"):
            await ctx.send("아직 레이드 스케줄이 없습니다.")
            return
            
        # 임베드 생성
        embed = discord.Embed(
            title=f"레이드 스케줄: {schedule.get('raid_name', '알 수 없음')}",
            description=f"스레드: {thread_name}",
            color=discord.Color.blue()
        )
        
        # 각 라운드 정보 추가
        for round_data in schedule.get("rounds", []):
            round_idx = round_data.get("idx", 0)
            round_time = round_data.get("time", "미정")
            dps_list = round_data.get("dps", [])
            sup_list = round_data.get("sup", [])
            
            # 필드 값 생성
            value = f"시간: {round_time if round_time else '미정'}\n"
            
            # DPS 목록
            value += "**DPS**:\n"
            if dps_list:
                for i, dps_id in enumerate(dps_list):
                    value += f"{i+1}. <@{dps_id}>\n"
            else:
                value += "- 없음\n"
                
            # 서포터 목록
            value += "**서포터**:\n"
            if sup_list:
                for i, sup_id in enumerate(sup_list):
                    value += f"{i+1}. <@{sup_id}>\n"
            else:
                value += "- 없음\n"
            
            embed.add_field(
                name=f"{round_idx}차",
                value=value,
                inline=False
            )
        
        # 마지막 업데이트 시간
        updated_at = schedule.get("updated_at", "")
        if updated_at:
            embed.set_footer(text=f"마지막 업데이트: {updated_at}")
        
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """
        메시지 이벤트 리스너. 레이드 명령어를 감지하고 처리합니다.
        
        Args:
            message: 메시지 객체
        """
        # 봇 메시지 무시
        if message.author.bot:
            return
            
        # 스레드인지 확인
        if not isinstance(message.channel, discord.Thread):
            return
            
        # 명령어 접두사 확인
        content = message.content.strip()
        
        command_map = {
            "!추가": "add",
            "!제거": "remove",
            "!수정": "edit"
        }
        
        command_prefix = None
        command_type = None
        
        for prefix, cmd_type in command_map.items():
            if content.startswith(prefix):
                command_prefix = prefix
                command_type = cmd_type
                break
                
        if not command_prefix:
            return
            
        # 명령어 텍스트 추출
        command_text = content[len(command_prefix):].strip()
        if not command_text:
            return
            
        # 스레드 ID
        thread_id = message.channel.id
        thread_name = message.channel.name
        user_id = str(message.author.id)
        
        # 기존 로그 외에 추가
        if message.content.startswith("!"):
            logger.info(f"[DEBUG] 받은 명령어: {message.content} - 사용자: {message.author.id}")
            # 명령어 타입도 명확하게 로깅
            logger.info(f"[DEBUG] 명령어 타입: {command_type}, 명령어 내용: {command_text}")
        
        # 처리 중 메시지
        processing_msg = await message.channel.send("명령어를 처리 중입니다...")
        
        try:
            # 명령어 타입 정보 추가
            # OpenAI 서비스로 명령어 파싱
            commands = await self.openai_service.parse_raid_command(user_id, command_text, command_type)
            logger.info(f"[DEBUG] OpenAI에서 반환된 명령어 개수: {len(commands)}")
            
            if not commands:
                await message.channel.send("명령어를 처리할 수 없습니다. 올바른 형식으로 입력해주세요.")
                return
                
            # 명령어 검증 및 포맷팅
            valid_commands = await self.openai_service.validate_and_format_commands(commands, user_id)
            logger.info(f"[DEBUG] 검증된 명령어 개수: {len(valid_commands)}")
            
            if not valid_commands:
                await message.channel.send("유효한 명령어가 없습니다. 올바른 형식으로 입력해주세요.")
                return
                
            # 레이드 히스토리에 명령어 추가
            success_count = 0
            for idx, command in enumerate(valid_commands):
                logger.info(f"[DEBUG] 처리 중인 명령어 [{idx+1}/{len(valid_commands)}]: {command}")
                if add_command_to_raid_history(thread_id, command):
                    success_count += 1
                    logger.info(f"[DEBUG] 명령어 히스토리 추가 성공: {command}")
                else:
                    logger.error(f"[DEBUG] 명령어 히스토리 추가 실패: {command}")
                    
            # 레이드 스케줄 업데이트
            schedule_updated = process_raid_commands_and_update_schedule(thread_id, thread_name)
            
            # 스레드 시작 메시지 업데이트
            if schedule_updated:
                # 레이드 정보 가져오기
                raid_data = await self._get_raid_data_for_thread(message.channel)
                if raid_data:
                    # 스레드 시작 메시지 업데이트
                    message_updated = await update_thread_start_message_with_schedule(message.channel, raid_data)
                    if not message_updated:
                        logger.warning(f"스레드 {thread_id}의 시작 메시지 업데이트 실패")
                    
            # 응답 메시지 생성
            response = f"{success_count}개의 명령어가 처리되었습니다."
            
            if schedule_updated:
                response += "\n스케줄이 업데이트되었습니다. !스케줄 명령어로 확인하세요."
            else:
                response += "\n스케줄 업데이트에 실패했습니다."
            
            # 처리된 명령어 요약
            if success_count > 0:
                commands_summary = []
                for cmd in valid_commands:
                    cmd_type = cmd.get("command", "")
                    role = cmd.get("role")
                    round_num = cmd.get("round")
                    
                    summary = f"- {cmd_type.upper() if cmd_type else 'UNKNOWN'}"
                    
                    if role:
                        summary += f" / {role}"
                        
                    if round_num is not None:
                        summary += f" / {round_num}차"
                        
                    round_edit = cmd.get("round_edit")
                    if round_edit:
                        round_idx = round_edit.get("round_index")
                        start_time = round_edit.get("start_time")
                        
                        if round_idx is not None and start_time:
                            summary += f" / {round_idx}차 → {start_time}"
                            
                    commands_summary.append(summary)
                    
                response += "\n\n" + "\n".join(commands_summary)
                
            # 처리 중 메시지 삭제 후 새 메시지 전송
            await processing_msg.delete()
            await message.channel.send(response)
            
        except Exception as e:
            logger.error(f"레이드 명령어 처리 중 오류 발생: {str(e)}")
            # 처리 중 메시지 삭제 후 새 메시지 전송
            await processing_msg.delete()
            await message.channel.send(f"명령어 처리 중 오류가 발생했습니다: {str(e)}")

    async def _get_raid_data_for_thread(self, thread: discord.Thread) -> Optional[Dict[str, Any]]:
        """
        스레드에 해당하는 레이드 정보를 가져옵니다.
        
        Args:
            thread: 디스코드 스레드
            
        Returns:
            레이드 정보 또는 None
        """
        try:
            # 스레드 ID로 레이드 데이터 로드
            raid_data = load_raid_data(thread.id)
            if not raid_data:
                return None
                
            return raid_data.get("raid_info", {})
            
        except Exception as e:
            logger.error(f"레이드 정보 조회 중 오류 발생: {str(e)}")
            return None

    def _create_system_prompt(self) -> str:
        """시스템 프롬프트를 생성합니다."""
        prompt = """
        # 레이드 명령어 파싱
        
        당신은 Lost Ark 게임의 레이드 일정 관리를 위한 명령어 파싱 서비스입니다.
        사용자의 메시지에서 레이드 참가, 일정 수정, 참가 취소 등의 명령어를 파싱해야 합니다.
        
        ## 응답 형식
        JSON 배열 형태로 응답하며, 각 명령어는 하나의 객체입니다.
        [
            {
                "command": "add/remove/edit",  // 명령어 유형
                "role": "dps/sup",             // 역할 (add/remove일 때만)
                "round": 1,                    // 라운드 번호 (없으면 null)
                "round_edit": {                // 라운드 수정 정보 (edit일 때만)
                    "round_index": 1,
                    "start_time": "토 21시"
                }
            }
        ]
        """
        logging.info(f"[DEBUG] 시스템 프롬프트: {prompt}")
        return prompt


async def setup(bot: commands.Bot) -> None:
    """
    Cog를 봇에 추가합니다.
    
    Args:
        bot: 봇 인스턴스
    """
    await bot.add_cog(Raids(bot)) 