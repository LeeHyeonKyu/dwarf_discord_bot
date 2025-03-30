import discord
from discord.ext import commands
import yaml
import os
import json
from typing import Optional

class RaidCommands(commands.Cog):
    """레이드 관련 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        self.raids_config_path = 'configs/raids_config.yaml'
    
    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} Cog가 준비되었습니다.')
    
    @commands.command(name='create_raid')
    @commands.has_permissions(manage_messages=True)
    async def create_raid(self, ctx, raid_name: str, channel_id: Optional[int] = None):
        """
        레이드 모집 메시지 생성 및 스레드 생성
        사용법: !create_raid 하기르 [채널ID]
        """
        # 채널 결정 (지정된 채널 또는 현재 채널)
        if channel_id:
            channel = self.bot.get_channel(channel_id)
            if not channel:
                await ctx.send(f"채널 ID {channel_id}를 찾을 수 없습니다.")
                return
        else:
            channel = ctx.channel
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            await ctx.send(f"채널 '{channel.name}'은(는) 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            return
        
        try:
            # 레이드 구성 정보 로드
            with open(self.raids_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                raids = config.get('raids', [])
            
            # 레이드 검색
            raid_info = None
            for raid in raids:
                if raid.get('name', '').lower() == raid_name.lower():
                    raid_info = raid
                    break
            
            if not raid_info:
                raid_list = ', '.join([r.get('name', '') for r in raids])
                await ctx.send(f"'{raid_name}' 레이드를 찾을 수 없습니다. 가능한 레이드: {raid_list}")
                return
            
            # 레이드 정보 추출
            raid_name = raid_info.get('name', 'Unknown')
            min_level = raid_info.get('min_level', 0)
            max_level = raid_info.get('max_level')
            description = raid_info.get('description', '')
            members_count = raid_info.get('members', 8)
            
            # 레이드 템플릿 메시지 생성
            message_content = f"# {raid_name} ({description})\n"
            if max_level:
                message_content += f"🔹 필요 레벨: {min_level} ~ {max_level}\n"
            else:
                message_content += f"🔹 필요 레벨: {min_level} 이상\n"
            message_content += f"🔹 모집 인원: {members_count}명\n\n"
            
            # 레이드 구성 템플릿 추가 (1차만 생성)
            message_content += "## 1차\n"
            message_content += "- when: \n"
            message_content += "- who: \n"
            if members_count == 4:
                message_content += "  - 서포터(0/1): \n"
                message_content += "  - 딜러(0/3): \n"
            else:  # 8인 레이드
                message_content += "  - 서포터(0/2): \n"
                message_content += "  - 딜러(0/6): \n"
            message_content += "- note: \n"
            
            # 메시지 전송
            raid_message = await channel.send(message_content)
            
            # 메시지로부터 스레드 생성
            thread = await raid_message.create_thread(
                name=f"{raid_name} 모집 스레드",
                auto_archive_duration=10080  # 7일 (분 단위)
            )
            
            await thread.send(f"'{raid_name}' 레이드 모집이 시작되었습니다. 참가를 원하시면 이 스레드에 댓글을 남겨주세요.")
            await ctx.send(f"'{raid_name}' 레이드 모집 메시지가 생성되었습니다.")
            
        except FileNotFoundError:
            await ctx.send(f"레이드 구성 파일({self.raids_config_path})를 찾을 수 없습니다.")
        except Exception as e:
            await ctx.send(f"레이드 생성 중 오류 발생: {e}")
    
    @commands.command(name='list_raids')
    async def list_raids(self, ctx):
        """
        사용 가능한 레이드 목록 표시
        사용법: !list_raids
        """
        try:
            with open(self.raids_config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                raids = config.get('raids', [])
            
            if not raids:
                await ctx.send("등록된 레이드가 없습니다.")
                return
            
            embed = discord.Embed(title="레이드 목록", color=discord.Color.blue())
            
            for raid in raids:
                name = raid.get('name', 'Unknown')
                min_level = raid.get('min_level', 0)
                max_level = raid.get('max_level', '무제한')
                description = raid.get('description', '')
                members = raid.get('members', 8)
                
                level_range = f"{min_level} ~ {max_level}" if max_level else f"{min_level} 이상"
                value = f"레벨: {level_range}\n인원: {members}명\n설명: {description}"
                
                embed.add_field(name=name, value=value, inline=False)
            
            await ctx.send(embed=embed)
            
        except FileNotFoundError:
            await ctx.send(f"레이드 구성 파일({self.raids_config_path})를 찾을 수 없습니다.")
        except Exception as e:
            await ctx.send(f"레이드 목록 조회 중 오류 발생: {e}")

# Cog 설정 함수
async def setup(bot):
    await bot.add_cog(RaidCommands(bot)) 