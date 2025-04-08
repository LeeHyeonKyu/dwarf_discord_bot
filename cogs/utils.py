#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
유틸리티 명령어를 제공하는 Cog 모듈.

이 모듈은 서버 정보, 사용자 정보 등의 기본적인 유틸리티 명령어를 제공합니다.
"""

import platform
import time
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands


class Utils(commands.Cog):
    """
    유틸리티 기능을 제공하는 Cog.
    
    이 클래스는 서버 정보, 사용자 정보, 봇 상태 등을 확인하는 명령어를 제공합니다.
    """

    def __init__(self, bot: commands.Bot) -> None:
        """
        유틸리티 Cog 초기화.
        
        Args:
            bot: 봇 인스턴스
        """
        self.bot = bot
        self.start_time = time.time()
    
    @commands.command(name="서버정보", aliases=["서버", "server"])
    async def server_info(self, ctx: commands.Context) -> None:
        """
        현재 서버의 정보를 표시합니다.
        """
        guild = ctx.guild
        if not guild:
            await ctx.send("이 명령어는 서버 내에서만 사용 가능합니다.")
            return
        
        # 서버 생성 시간을 한국 시간으로 변환
        created_at_kr = guild.created_at.strftime("%Y년 %m월 %d일 %H시 %M분")
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"{guild.name} 서버 정보",
            description=f"ID: {guild.id}",
            color=discord.Color.blue()
        )
        
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        embed.add_field(name="소유자", value=f"{guild.owner}", inline=True)
        embed.add_field(name="생성일", value=created_at_kr, inline=True)
        embed.add_field(name="멤버 수", value=f"{guild.member_count}명", inline=True)
        
        # 역할 수 (관리자 역할, @everyone 등)
        roles = ", ".join([role.name for role in guild.roles if role.name != "@everyone"][:10])
        if len(guild.roles) > 11:  # @everyone 포함
            roles += f" 외 {len(guild.roles) - 11}개"
        
        embed.add_field(name=f"역할 ({len(guild.roles) - 1}개)", value=roles or "없음", inline=False)
        
        # 채널 정보
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        embed.add_field(
            name="채널",
            value=f"텍스트: {text_channels}개, 음성: {voice_channels}개, 카테고리: {categories}개",
            inline=False
        )
        
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="사용자정보", aliases=["유저", "user"])
    async def user_info(self, ctx: commands.Context, member: Optional[discord.Member] = None) -> None:
        """
        사용자 정보를 표시합니다.
        
        Args:
            member: 정보를 확인할 멤버. 지정하지 않으면 명령어를 사용한 사용자의 정보를 표시합니다.
        """
        # 멤버가 지정되지 않은 경우 명령어 사용자로 설정
        target = member or ctx.author
        
        # 계정 생성 시간 한국 시간으로 변환
        created_at_kr = target.created_at.strftime("%Y년 %m월 %d일 %H시 %M분")
        
        # 임베드 생성
        embed = discord.Embed(
            title=f"{target.name} 사용자 정보",
            description=f"ID: {target.id}",
            color=target.color
        )
        
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        
        embed.add_field(name="별명", value=target.display_name, inline=True)
        embed.add_field(name="계정 생성일", value=created_at_kr, inline=True)
        
        # Member 객체인 경우에만 서버 참가일과 역할 정보 표시
        if isinstance(target, discord.Member):
            joined_at_kr = target.joined_at.strftime("%Y년 %m월 %d일 %H시 %M분") if target.joined_at else "알 수 없음"
            embed.add_field(name="서버 참가일", value=joined_at_kr, inline=True)
            
            # 역할 정보
            roles = ", ".join([role.name for role in target.roles if role.name != "@everyone"][:10])
            if len(target.roles) > 11:  # @everyone 포함
                roles += f" 외 {len(target.roles) - 11}개"
            
            embed.add_field(name=f"역할 ({len(target.roles) - 1}개)", value=roles or "없음", inline=False)
        
        embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        
        await ctx.send(embed=embed)
    
    @commands.command(name="봇정보", aliases=["봇", "bot"])
    async def show_bot_info(self, ctx: commands.Context) -> None:
        """
        봇의 정보와 상태를 표시합니다.
        """
        # 가동 시간 계산
        uptime_seconds = int(time.time() - self.start_time)
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}일 "
        if hours > 0 or days > 0:
            uptime_str += f"{hours}시간 "
        if minutes > 0 or hours > 0 or days > 0:
            uptime_str += f"{minutes}분 "
        uptime_str += f"{seconds}초"
        
        # 임베드 생성
        if self.bot.user:
            embed = discord.Embed(
                title=f"{self.bot.user.name} 정보",
                description=f"ID: {self.bot.user.id}",
                color=discord.Color.green()
            )
            
            if self.bot.user.avatar:
                embed.set_thumbnail(url=self.bot.user.avatar.url)
            
            embed.add_field(name="가동 시간", value=uptime_str, inline=True)
            embed.add_field(name="지연 시간", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
            embed.add_field(name="서버 수", value=f"{len(self.bot.guilds)}개", inline=True)
            
            embed.add_field(name="Python 버전", value=platform.python_version(), inline=True)
            embed.add_field(name="discord.py 버전", value=discord.__version__, inline=True)
            embed.add_field(name="플랫폼", value=platform.system(), inline=True)
            
            # 명령어 수 계산
            command_count = len(self.bot.commands)
            embed.add_field(name="명령어 수", value=f"{command_count}개", inline=True)
            
            embed.set_footer(text=f"요청자: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("봇 정보를 가져올 수 없습니다.")


async def setup(bot: commands.Bot) -> None:
    """
    Cog를 봇에 추가합니다.
    
    Args:
        bot: 봇 인스턴스
    """
    await bot.add_cog(Utils(bot)) 