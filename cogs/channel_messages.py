#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
채널 및 스레드 관련 기능을 제공하는 Cog 모듈.

이 모듈은 Discord 채널에 메시지 전송, 스레드 관리, 채팅 기록 조회 등의 기능을 제공합니다.
"""

import asyncio
import logging
import os
from typing import Dict, List, Optional, Union, Any, cast, Tuple, Callable

import discord
from discord.ext import commands
from dotenv import load_dotenv

# 로깅 설정
logger = logging.getLogger("channel_messages")

# 환경 변수 로드
load_dotenv(".env.secret")
AUTHORIZED_USERS = os.getenv("AUTHORIZED_USERS", "").split(",")


class ChannelMessages(commands.Cog):
    """
    채널 및 스레드 관련 기능을 제공하는 Cog.
    
    이 클래스는 Discord 채널에 메시지 전송, 스레드 관리, 채팅 기록 조회 등의 기능을 제공합니다.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        ChannelMessages Cog 초기화.
        
        Args:
            bot: 봇 인스턴스
        """
        self.bot = bot
    
    # ============= 동기 헬퍼 함수 =============
    
    def is_authorized(self, user_id: Union[str, int]) -> bool:
        """
        사용자가 권한이 있는지 확인하는 동기 함수.
        
        Args:
            user_id: 사용자 Discord ID
            
        Returns:
            권한 여부
        """
        # Discord ID를 문자열로 변환
        user_id_str = str(user_id)
        
        # 권한 있는 사용자 ID 목록 확인
        return not AUTHORIZED_USERS or user_id_str in AUTHORIZED_USERS
    
    def get_channel_by_id(self, channel_id: Union[str, int]) -> Optional[Any]:
        """
        채널 ID로 채널을 찾는 동기 함수.
        
        Args:
            channel_id: 찾을 채널 ID
            
        Returns:
            찾은 채널 객체 또는 None
        """
        try:
            # 채널 ID를 정수로 변환
            channel_id_int = int(channel_id) if isinstance(channel_id, str) else channel_id
            
            # 채널 가져오기
            return self.bot.get_channel(channel_id_int)
        except (ValueError, TypeError):
            return None
    
    def can_send_to_channel(self, channel: Any) -> bool:
        """
        채널에 메시지를 보낼 수 있는지 확인하는 동기 함수.
        
        Args:
            channel: 확인할 채널 객체
            
        Returns:
            메시지 전송 가능 여부
        """
        return isinstance(channel, discord.abc.Messageable)
    
    def get_channel_mention(self, channel: Any, default_id: str = '') -> str:
        """
        채널 멘션 문자열을 생성하는 동기 함수.
        
        Args:
            channel: 채널 객체
            default_id: 기본 ID 값(채널 ID를 가져올 수 없을 때 사용)
            
        Returns:
            채널 멘션 문자열
        """
        try:
            channel_id = getattr(channel, 'id', default_id)
            return f"<#{channel_id}>"
        except (AttributeError, TypeError):
            return "DM 채널"
    
    def is_bot_message(self, message: discord.Message) -> bool:
        """
        메시지가 봇이 보낸 것인지 확인하는 동기 함수.
        
        Args:
            message: 확인할 메시지
            
        Returns:
            봇이 보낸 메시지 여부
        """
        return self.bot.user is not None and message.author.id == self.bot.user.id
    
    def format_messages_content(self, messages: List[discord.Message]) -> List[str]:
        """
        메시지 목록을 표시 형식으로 변환하는 동기 함수.
        
        Args:
            messages: 형식을 변환할 메시지 목록
            
        Returns:
            형식이 변환된 메시지 내용 목록
        """
        return [f"**{msg.author.display_name}**: {msg.content}" for msg in messages]
    
    def chunk_messages(self, messages: List[str], header: str, chunk_size: int = 1900) -> List[str]:
        """
        메시지를 여러 청크로 나누는 동기 함수.
        
        Args:
            messages: 나눌 메시지 내용 목록
            header: 각 청크의 시작 부분에 추가할 헤더
            chunk_size: 각 청크의 최대 크기
            
        Returns:
            청크 목록
        """
        chunks = []
        current_chunk = header
        
        for message in messages:
            if len(current_chunk) + len(message) + 2 > chunk_size:
                chunks.append(current_chunk)
                current_chunk = header
            
            current_chunk += message + "\n\n"
        
        if current_chunk != header:
            chunks.append(current_chunk)
            
        return chunks
    
    def create_search_result_embed(self, keyword: str, found_messages: List[Dict[str, Any]], 
                                   max_results: int = 10) -> discord.Embed:
        """
        검색 결과 임베드를 생성하는 동기 함수.
        
        Args:
            keyword: 검색 키워드
            found_messages: 검색된 메시지 목록
            max_results: 표시할 최대 결과 수
            
        Returns:
            검색 결과 임베드
        """
        result_embed = discord.Embed(
            title=f"'{keyword}' 검색 결과",
            description=f"총 {len(found_messages)}개의 메시지를 찾았습니다.",
            color=discord.Color.green()
        )
        
        # 최대 지정된 개수까지만 표시
        count = 0
        for item in found_messages[:max_results]:
            count += 1
            message = item['message']
            channel = item['channel']
            
            # 내용이 길면 자르기
            content = message.content
            if len(content) > 100:
                content = content[:97] + "..."
            
            # 날짜 형식
            timestamp = message.created_at.strftime("%Y-%m-%d %H:%M")
            
            # 필드 추가
            result_embed.add_field(
                name=f"{count}. {message.author.display_name} ({timestamp})",
                value=f"채널: {channel.mention}\n내용: {content}\n[메시지 링크]({message.jump_url})",
                inline=False
            )
        
        return result_embed
    
    def create_help_embed(self) -> discord.Embed:
        """
        도움말 임베드를 생성하는 동기 함수.
        
        Returns:
            도움말 임베드
        """
        help_embed = discord.Embed(
            title="채널 및 스레드 관련 명령어 도움말",
            description="디스코드의 채널과 스레드를 관리하기 위한 명령어 목록입니다.",
            color=discord.Color.blue()
        )
        
        # 메시지 전송 명령어
        help_embed.add_field(
            name="!메시지전송 [채널ID] [메시지]",
            value="특정 채널에 메시지를 전송합니다.",
            inline=False
        )
        
        # 스레드 시작 명령어
        help_embed.add_field(
            name="!스레드시작 [메시지ID] [스레드이름]",
            value="특정 메시지에 대한 스레드를 시작합니다.",
            inline=False
        )
        
        # 스레드 기록 명령어
        help_embed.add_field(
            name="!스레드기록 [스레드ID] [개수(선택)]",
            value="특정 스레드의 채팅 기록을 가져옵니다. 개수를 지정하지 않으면 기본값은 20개입니다.",
            inline=False
        )
        
        # 스레드 메시지 명령어
        help_embed.add_field(
            name="!스레드메시지 [스레드ID] [메시지]",
            value="특정 스레드에 메시지를 전송합니다.",
            inline=False
        )
        
        # 메시지 수정 명령어
        help_embed.add_field(
            name="!메시지수정 [메시지ID] [새로운내용]",
            value="봇이 이미 발송한 메시지의 내용을 수정합니다.",
            inline=False
        )
        
        # 메시지 삭제 명령어
        help_embed.add_field(
            name="!메시지삭제 [메시지ID]",
            value="봇이 발송한 메시지를 삭제합니다.",
            inline=False
        )
        
        # 메시지 검색 명령어
        help_embed.add_field(
            name="!메시지검색 [키워드] [검색범위(선택)]",
            value="특정 키워드를 포함하는 메시지를 최대 20개까지 검색합니다. 검색범위는 기본값 100, 최대 500개 메시지입니다.",
            inline=False
        )
        
        # 채널 정리 명령어
        help_embed.add_field(
            name="!채널정리 [채널ID] [메시지개수(선택)]",
            value="특정 채널의 모든 스레드와 지정한 개수의 메시지를 삭제합니다. 메시지 개수 기본값은 100개, 최대 1000개입니다.",
            inline=False
        )
        
        # ID 찾는 방법 안내
        help_embed.add_field(
            name="채널/메시지/스레드 ID 찾기",
            value=(
                "1. 디스코드 설정에서 개발자 모드를 활성화하세요.\n"
                "2. 채널/메시지/스레드에서 우클릭하여 'ID 복사'를 선택하세요."
            ),
            inline=False
        )
        
        return help_embed
    
    def is_text_channel(self, channel: Any) -> bool:
        """
        채널이 텍스트 채널인지 확인하는 동기 함수.
        
        Args:
            channel: 확인할 채널 객체
            
        Returns:
            텍스트 채널 여부
        """
        return isinstance(channel, discord.TextChannel)
    
    def count_active_threads(self, channel: discord.TextChannel) -> int:
        """
        채널의 활성 스레드 수를 계산하는 동기 함수.
        
        Args:
            channel: 스레드를 확인할 채널
            
        Returns:
            활성 스레드 수
        """
        if not self.is_text_channel(channel):
            return 0
            
        return len(channel.threads)
    
    # ============= 비동기 헬퍼 함수 =============
    
    async def check_authorized(self, ctx: commands.Context) -> bool:
        """
        명령어 사용자가 권한이 있는지 확인하는 비동기 함수.
        
        Args:
            ctx: 명령어 컨텍스트
            
        Returns:
            권한 여부
        """
        # 동기 함수 사용
        is_authorized = self.is_authorized(ctx.author.id)
        
        if not is_authorized:
            await ctx.send("이 명령어를 사용할 권한이 없습니다.")
        
        return is_authorized
    
    async def find_channel(self, channel_id: Union[str, int]) -> Optional[Any]:
        """
        채널 ID로 채널을 찾는 비동기 함수.
        
        Args:
            channel_id: 찾을 채널 ID
            
        Returns:
            찾은 채널 객체 또는 None
        """
        # 동기 함수 사용
        return self.get_channel_by_id(channel_id)
    
    async def find_message(self, ctx: commands.Context, message_id: Union[str, int]) -> Optional[discord.Message]:
        """
        메시지 ID로 메시지를 찾는 비동기 함수.
        
        Args:
            ctx: 명령어 컨텍스트
            message_id: 찾을 메시지 ID
            
        Returns:
            찾은 메시지 객체 또는 None
        """
        try:
            # 메시지 ID를 정수로 변환
            message_id_int = int(message_id) if isinstance(message_id, str) else message_id
            
            # 메시지 가져오기
            message = None
            
            # 현재 채널에서 메시지 찾기
            try:
                message = await ctx.channel.fetch_message(message_id_int)
                return message
            except discord.NotFound:
                # 다른 채널에서 메시지 찾기
                if ctx.guild:
                    for channel in ctx.guild.text_channels:
                        try:
                            message = await channel.fetch_message(message_id_int)
                            return message
                        except (discord.NotFound, discord.Forbidden):
                            continue
            
            return None
        except (ValueError, TypeError):
            return None
    
    # ============= 명령어 핸들러 =============
    
    @commands.command(name="메시지전송", aliases=["메세지전송", "채널메시지"])
    async def send_channel_message(self, ctx: commands.Context, channel_id: str, *, message: str) -> None:
        """
        특정 채널에 메시지를 전송합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            channel_id: 메시지를 전송할 채널 ID
            message: 전송할 메시지 내용
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        try:
            # 채널 찾기 (동기 함수 사용)
            channel = self.get_channel_by_id(channel_id)
            if not channel:
                await ctx.send(f"채널을 찾을 수 없습니다: {channel_id}")
                return
            
            # 메시지를 보낼 수 있는 채널인지 확인 (동기 함수 사용)
            if not self.can_send_to_channel(channel):
                await ctx.send(f"해당 채널에 메시지를 보낼 수 없습니다: {channel_id}")
                return
            
            # 메시지 전송
            await channel.send(message)
            
            # 채널 타입에 따라 다른 메시지 표시 (동기 함수 사용)
            channel_mention = self.get_channel_mention(channel, channel_id)
            
            await ctx.send(f"채널 {channel_mention}에 메시지를 전송했습니다.")
            
        except discord.Forbidden:
            await ctx.send("해당 채널에 메시지를 보낼 권한이 없습니다.")
        except Exception as e:
            logger.error(f"메시지 전송 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"메시지 전송 중 오류가 발생했습니다: {str(e)}")
    
    @commands.command(name="스레드시작", aliases=["스레드만들기", "스레드생성"])
    async def create_thread(self, ctx: commands.Context, message_id: str, *, thread_name: str) -> None:
        """
        특정 메시지에 대한 스레드를 시작합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            message_id: 스레드를 시작할 메시지 ID
            thread_name: 생성할 스레드의 이름
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        try:
            # 메시지 찾기
            message = await self.find_message(ctx, message_id)
            if not message:
                await ctx.send(f"메시지를 찾을 수 없습니다: {message_id}")
                return
            
            # 스레드 생성
            thread = await message.create_thread(
                name=thread_name,
                auto_archive_duration=1440  # 24시간(1440분) 후 자동 보관
            )
            
            await ctx.send(f"스레드가 생성되었습니다: {thread.mention}")
            
        except discord.Forbidden:
            await ctx.send("스레드를 생성할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"스레드 생성 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"스레드 생성 중 오류가 발생했습니다: {str(e)}")
    
    @commands.command(name="스레드기록", aliases=["스레드채팅", "채팅기록"])
    async def get_thread_messages(self, ctx: commands.Context, thread_id: str, limit: Optional[int] = 20) -> None:
        """
        특정 스레드의 채팅 기록을 가져옵니다.
        
        Args:
            ctx: 명령어 컨텍스트
            thread_id: 채팅 기록을 가져올 스레드 ID
            limit: 가져올 메시지의 최대 개수 (기본값: 20)
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        try:
            # 스레드 ID를 정수로 변환
            thread_id_int = int(thread_id)
            
            # 스레드 가져오기 (동기 함수 사용)
            thread = self.get_channel_by_id(thread_id_int)
            if not thread or not isinstance(thread, discord.Thread):
                await ctx.send(f"스레드를 찾을 수 없습니다: {thread_id}")
                return
            
            # 메시지 개수 제한
            if limit and limit > 100:
                limit = 100
                await ctx.send("메시지 개수는 최대 100개로 제한됩니다.")
            
            # 채팅 기록 가져오기
            messages = []
            async for msg in thread.history(limit=limit):
                messages.append(msg)
            messages.reverse()  # 시간순으로 정렬
            
            # 메시지 내용 구성
            if not messages:
                await ctx.send(f"스레드 <#{thread_id_int}>에 메시지가 없습니다.")
                return
            
            # 메시지 내용을 하나의 문자열로 합침 (동기 함수 사용)
            messages_content = self.format_messages_content(messages)
            
            # 여러 메시지로 나누어 보내기 (동기 함수 사용)
            header = f"스레드 <#{thread_id_int}> 채팅 기록 (최근 {len(messages)}개):\n\n"
            chunks = self.chunk_messages(messages_content, header)
            
            # 메시지 전송
            for chunk in chunks:
                await ctx.send(chunk)
            
        except ValueError:
            await ctx.send("올바른 스레드 ID를 입력해주세요.")
        except discord.Forbidden:
            await ctx.send("해당 스레드의 채팅 기록을 볼 권한이 없습니다.")
        except Exception as e:
            logger.error(f"채팅 기록 조회 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"채팅 기록 조회 중 오류가 발생했습니다: {str(e)}")
    
    @commands.command(name="스레드메시지", aliases=["스레드채팅전송", "스레드전송"])
    async def send_thread_message(self, ctx: commands.Context, thread_id: str, *, message: str) -> None:
        """
        특정 스레드에 메시지를 전송합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            thread_id: 메시지를 전송할 스레드 ID
            message: 전송할 메시지 내용
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        try:
            # 스레드 ID를 정수로 변환
            thread_id_int = int(thread_id)
            
            # 스레드 가져오기 (동기 함수 사용)
            thread = self.get_channel_by_id(thread_id_int)
            if not thread or not isinstance(thread, discord.Thread):
                await ctx.send(f"스레드를 찾을 수 없습니다: {thread_id}")
                return
            
            # 메시지 전송
            await thread.send(message)
            await ctx.send(f"스레드 <#{thread_id_int}>에 메시지를 전송했습니다.")
            
        except ValueError:
            await ctx.send("올바른 스레드 ID를 입력해주세요.")
        except discord.Forbidden:
            await ctx.send("해당 스레드에 메시지를 보낼 권한이 없습니다.")
        except Exception as e:
            logger.error(f"스레드 메시지 전송 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"스레드 메시지 전송 중 오류가 발생했습니다: {str(e)}")

    @commands.command(name="메시지수정", aliases=["메세지수정", "메시지편집"])
    async def edit_message(self, ctx: commands.Context, message_id: str, *, new_content: str) -> None:
        """
        이미 발송한 메시지를 수정합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            message_id: 수정할 메시지 ID
            new_content: 새로운 메시지 내용
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        try:
            # 메시지 찾기
            message = await self.find_message(ctx, message_id)
            if not message:
                await ctx.send(f"메시지를 찾을 수 없습니다: {message_id}")
                return
            
            # 봇이 보낸 메시지인지 확인 (동기 함수 사용)
            if not self.is_bot_message(message):
                await ctx.send("봇이 보낸 메시지만 수정할 수 있습니다.")
                return
            
            # 메시지 수정
            await message.edit(content=new_content)
            
            # 채널 정보 가져오기 (동기 함수 사용)
            channel_mention = self.get_channel_mention(message.channel)
            
            await ctx.send(f"{channel_mention} 채널의 메시지를 수정했습니다.")
            
        except discord.Forbidden:
            await ctx.send("해당 메시지를 수정할 권한이 없습니다.")
        except discord.HTTPException as e:
            logger.error(f"메시지 수정 중 HTTP 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"메시지 수정 중 오류가 발생했습니다: {str(e)}")
        except Exception as e:
            logger.error(f"메시지 수정 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"메시지 수정 중 오류가 발생했습니다: {str(e)}")

    @commands.command(name="메시지삭제", aliases=["메세지삭제", "메시지제거"])
    async def delete_message(self, ctx: commands.Context, message_id: str) -> None:
        """
        봇이 발송한 메시지를 삭제합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            message_id: 삭제할 메시지 ID
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        try:
            # 메시지 찾기
            message = await self.find_message(ctx, message_id)
            if not message:
                await ctx.send(f"메시지를 찾을 수 없습니다: {message_id}")
                return
            
            # 봇이 보낸 메시지인지 확인 (동기 함수 사용)
            if not self.is_bot_message(message):
                await ctx.send("봇이 보낸 메시지만 삭제할 수 있습니다.")
                return
            
            # 메시지가 있던 채널 정보 저장 (동기 함수 사용)
            channel_mention = self.get_channel_mention(message.channel)
            
            # 메시지 삭제
            await message.delete()
            
            await ctx.send(f"{channel_mention} 채널의 메시지를 삭제했습니다.")
            
        except discord.Forbidden:
            await ctx.send("해당 메시지를 삭제할 권한이 없습니다.")
        except discord.NotFound:
            await ctx.send("이미 삭제된 메시지입니다.")
        except Exception as e:
            logger.error(f"메시지 삭제 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"메시지 삭제 중 오류가 발생했습니다: {str(e)}")

    @commands.command(name="메시지검색", aliases=["메세지검색", "채팅검색"])
    async def search_messages(self, ctx: commands.Context, keyword: str, limit: Optional[int] = 100) -> None:
        """
        특정 키워드를 포함하는 메시지를 검색합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            keyword: 검색할 키워드
            limit: 검색할 최대 메시지 수 (기본값: 100)
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        # 안내 메시지
        searching_msg = await ctx.send(f"키워드 `{keyword}`를 포함하는 메시지를 검색 중입니다...")
        
        try:
            # 검색 결과 저장 리스트
            found_messages = []
            
            # 검색 범위 제한
            if limit is not None and limit > 500:
                limit = 500
                await ctx.send("검색 범위는 최대 500개 메시지로 제한됩니다.")
            
            # 서버가 존재하는 경우에만 검색
            if not ctx.guild:
                await ctx.send("이 명령어는 서버 내에서만 사용 가능합니다.")
                return
            
            # 진행 상황 표시 횟수 제한
            progress_counter = 0
            progress_interval = 5
            
            # 모든 텍스트 채널에서 검색
            for channel in ctx.guild.text_channels:
                try:
                    # 권한 확인
                    if not channel.permissions_for(ctx.guild.me).read_message_history:
                        continue
                    
                    # 진행 상황 표시
                    progress_counter += 1
                    if progress_counter % progress_interval == 0:
                        await searching_msg.edit(content=f"키워드 `{keyword}`를 포함하는 메시지를 검색 중입니다... ({progress_counter}/{len(ctx.guild.text_channels)} 채널 확인 중)")
                    
                    # 채널 메시지 검색
                    async for message in channel.history(limit=limit):
                        if keyword.lower() in message.content.lower():
                            found_messages.append({
                                'channel': channel,
                                'message': message,
                                'timestamp': message.created_at
                            })
                            
                            # 최대 20개까지만 저장
                            if len(found_messages) >= 20:
                                break
                    
                    # 최대 20개를 넘어가면 검색 중단
                    if len(found_messages) >= 20:
                        break
                        
                except discord.Forbidden:
                    pass
                except Exception as e:
                    logger.error(f"채널 {channel.name} 검색 중 오류: {str(e)}", exc_info=True)
            
            # 검색 완료 메시지
            await searching_msg.edit(content=f"검색이 완료되었습니다. 키워드 `{keyword}`를 포함하는 메시지를 {len(found_messages)}개 찾았습니다.")
            
            # 결과가 없는 경우
            if not found_messages:
                await ctx.send(f"키워드 `{keyword}`를 포함하는 메시지를 찾을 수 없습니다.")
                return
            
            # 결과 정렬 (최신 메시지부터)
            found_messages.sort(key=lambda x: x['timestamp'], reverse=True)
            
            # 결과 표시 (동기 함수 사용)
            result_embed = self.create_search_result_embed(keyword, found_messages)
            
            # 결과 전송
            await ctx.send(embed=result_embed)
            
        except Exception as e:
            logger.error(f"메시지 검색 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"메시지 검색 중 오류가 발생했습니다: {str(e)}")
            await searching_msg.edit(content="검색 중 오류가 발생했습니다.")

    @commands.command(name="채널기능", aliases=["채널명령어", "채널도움말"])
    async def channel_commands_help(self, ctx: commands.Context) -> None:
        """
        채널 및 스레드 관련 명령어 도움말을 표시합니다.
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        # 도움말 임베드 생성 (동기 함수 사용)
        help_embed = self.create_help_embed()
        
        await ctx.send(embed=help_embed)

    @commands.command(name="채널정리", aliases=["채널청소", "채널초기화"])
    async def clean_channel(self, ctx: commands.Context, channel_id: str, limit: Optional[int] = 100) -> None:
        """
        특정 채널의 모든 스레드와 메시지를 삭제합니다.
        
        Args:
            ctx: 명령어 컨텍스트
            channel_id: 정리할 채널 ID
            limit: 삭제할 메시지 개수 (기본값: 100)
        """
        # 권한 체크
        if not await self.check_authorized(ctx):
            return
        
        # 서버 확인
        if not ctx.guild:
            await ctx.send("이 명령어는 서버 내에서만 사용 가능합니다.")
            return
            
        # 메시지 삭제 제한 설정
        if limit is not None and limit > 1000:
            limit = 1000
            await ctx.send("안전을 위해 메시지 삭제는 최대 1000개로 제한됩니다.")
        
        try:
            # 채널 찾기 (동기 함수 사용)
            channel = self.get_channel_by_id(channel_id)
            if not channel:
                await ctx.send(f"채널을 찾을 수 없습니다: {channel_id}")
                return
            
            # 텍스트 채널 확인 (동기 함수 사용)
            if not self.is_text_channel(channel):
                await ctx.send(f"해당 ID({channel_id})는 텍스트 채널이 아닙니다.")
                return
            
            # 채널에 대한 권한 확인 - 좀 더 명확하게 타입 처리
            channel_typed = discord.utils.get(ctx.guild.text_channels, id=int(channel_id))
            if not channel_typed:
                await ctx.send(f"채널을 찾을 수 없습니다: {channel_id}")
                return
                
            # 권한 체크를 위한 me 객체 안전하게 획득
            me = ctx.guild.me if ctx.guild else None
            if not me:
                await ctx.send("서버 정보를 가져올 수 없습니다.")
                return
                
            if not channel_typed.permissions_for(me).manage_threads:
                await ctx.send("해당 채널의 스레드를 관리할 권한이 없습니다.")
                return
            
            if not channel_typed.permissions_for(me).manage_messages:
                await ctx.send("해당 채널의 메시지를 관리할 권한이 없습니다.")
                return
            
            # 진행 상황 메시지
            progress_msg = await ctx.send(f"채널 {channel_typed.mention} 정리 시작... 스레드를 확인 중입니다.")
            
            # 스레드 수 확인 (동기 함수 사용)
            thread_count = self.count_active_threads(channel_typed)
            
            # 메시지 업데이트 실패 시 대비 안전 장치
            async def safe_edit(message, content):
                try:
                    if message:
                        await message.edit(content=content)
                    else:
                        logger.warning("메시지 객체가 None입니다.")
                except Exception as e:
                    logger.warning(f"메시지 편집 중 오류 발생: {str(e)}")
                    # 실패하면 새 메시지 전송
                    try:
                        await ctx.send(content)
                    except:
                        logger.error("메시지 전송도 실패했습니다.")
            
            # 스레드 삭제 진행
            deleted_threads = 0
            for thread in channel_typed.threads:
                try:
                    await thread.delete()
                    deleted_threads += 1
                    # 진행 상황 업데이트 (5개 단위)
                    if deleted_threads % 5 == 0 or deleted_threads == thread_count:
                        await safe_edit(progress_msg, f"채널 {channel_typed.mention} 정리 중... {deleted_threads}/{thread_count} 스레드 삭제 완료")
                except Exception as e:
                    logger.error(f"스레드 삭제 중 오류 발생: {str(e)}", exc_info=True)
            
            # 스레드 삭제 완료 메시지
            if thread_count > 0:
                await safe_edit(progress_msg, f"채널 {channel_typed.mention}의 모든 스레드({deleted_threads}개) 삭제 완료. 메시지 삭제를 시작합니다...")
            else:
                await safe_edit(progress_msg, f"채널 {channel_typed.mention}에 삭제할 스레드가 없습니다. 메시지 삭제를 시작합니다...")
            
            # 메시지 삭제
            try:
                deleted_count = await channel_typed.purge(limit=limit)
                await ctx.send(f"채널 {channel_typed.mention} 정리 완료! {deleted_threads}개의 스레드와 {len(deleted_count)}개의 메시지를 삭제했습니다.")
            except discord.errors.HTTPException as e:
                logger.error(f"메시지 삭제 중 HTTP 오류 발생: {str(e)}", exc_info=True)
                await ctx.send(f"메시지 삭제 중 오류가 발생했습니다. 일부 메시지는 너무 오래되어 일괄 삭제할 수 없을 수 있습니다.")
                await safe_edit(progress_msg, f"채널 {channel_typed.mention} 정리 부분 완료. {deleted_threads}개의 스레드는 삭제되었으나, 메시지 삭제 중 오류가 발생했습니다.")
        
        except discord.Forbidden:
            await ctx.send("해당 채널을 정리할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"채널 정리 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send(f"채널 정리 중 오류가 발생했습니다: {str(e)}")


async def setup(bot: commands.Bot) -> None:
    """
    Cog를 봇에 추가합니다.
    
    Args:
        bot: 봇 인스턴스
    """
    await bot.add_cog(ChannelMessages(bot)) 