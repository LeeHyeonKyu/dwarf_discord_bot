import os
import discord
from discord.ext import commands, tasks
import yaml
import requests
import urllib.parse
import json
import datetime
import asyncio
from typing import Dict, List, Any, Optional

class CharacterUpdateScheduler(commands.Cog):
    """캐릭터 정보 주기적 업데이트 스케줄러"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = bot.config.get("LOSTARK_API_KEY")
        self.channel_id = int(bot.config.get("UPDATES_CHANNEL_ID", 0))
        self.levelup_channel_id = int(bot.config.get("LEVELUP_CHANNEL_ID", 0))
        self.members_config_path = 'configs/members_config.yaml'
        self.character_data_path = 'data/character_data.json'
        
        # data 디렉토리 생성
        os.makedirs('data', exist_ok=True)
        
        # 초기 데이터 파일이 없는 경우 빈 데이터로 생성
        if not os.path.exists(self.character_data_path):
            with open(self.character_data_path, 'w', encoding='utf-8') as f:
                json.dump({}, f, ensure_ascii=False, indent=2)
        
        # 스케줄러 시작
        self.character_update_job.start()
    
    async def cog_unload(self):
        """Cog가 언로드될 때 작업 중지"""
        self.character_update_job.cancel()
    
    @tasks.loop(minutes=30)
    async def character_update_job(self):
        """30분마다 캐릭터 정보를 업데이트하는 작업"""
        if not self.api_key:
            print("로스트아크 API 키가 설정되어 있지 않습니다.")
            return
        
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            print(f"채널을 찾을 수 없습니다: {self.channel_id}")
            return
        
        await self.update_all_members_data(channel)
    
    @character_update_job.before_loop
    async def before_character_update_job(self):
        """봇이 준비될 때까지 대기"""
        await self.bot.wait_until_ready()
        # 시작 시 5초 대기 (API 요청 부하 방지)
        await asyncio.sleep(5)
    
    async def update_all_members_data(self, channel):
        """모든 멤버의 캐릭터 정보를 업데이트하고 변경사항 보고"""
        print(f"{datetime.datetime.now()} - 멤버 정보 업데이트 시작")
        
        try:
            # 멤버 설정 로드
            with open(self.members_config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
                all_members = config_data.get('members', [])
                
                # active 상태인 멤버만 필터링
                members = [member for member in all_members if member.get('active', False)]
            
            # 이전 데이터 로드
            with open(self.character_data_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # 새 데이터 컨테이너
            new_data = {}
            changes_detected = False
            
            # 레벨업 채널 가져오기
            levelup_channel = self.bot.get_channel(self.levelup_channel_id)
            if not levelup_channel:
                print(f"레벨업 축하 채널을 찾을 수 없습니다: {self.levelup_channel_id}")
            
            # 각 멤버별로 처리 (active 멤버만)
            for member in members:
                member_id = member.get('id')
                discord_name = member.get('discord_name')
                discord_id = member.get('discord_id', '')
                main_characters = member.get('main_characters', [])
                
                if not main_characters:
                    continue
                
                # 주 캐릭터로 API 요청
                main_character = main_characters[0] if main_characters else ""
                member_changes = []
                level_changes = []  # 모든 레벨업 정보
                
                try:
                    # API 호출로 캐릭터 데이터 가져오기
                    sibling_data = await self.fetch_character_siblings(main_character)
                    
                    if sibling_data:
                        # 아이템 레벨 기준 내림차순 정렬
                        sorted_characters = sorted(
                            sibling_data,
                            key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
                            reverse=True
                        )
                        
                        # 처리된 캐릭터 목록
                        processed_characters = []
                        
                        for char in sorted_characters:
                            char_name = char.get('CharacterName', '')
                            char_class = char.get('CharacterClassName', '')
                            char_server = char.get('ServerName', '')
                            item_level = char.get('ItemMaxLevel', '0')
                            
                            # 캐릭터 정보 구성
                            character_info = {
                                'name': char_name,
                                'class': char_class,
                                'server': char_server,
                                'item_level': item_level,
                                'last_updated': datetime.datetime.now().isoformat()
                            }
                            
                            processed_characters.append(character_info)
                            
                            # 변경 사항 확인
                            if member_id in old_data:
                                old_char_info = next(
                                    (c for c in old_data[member_id].get('characters', []) if c.get('name') == char_name),
                                    None
                                )
                                
                                if old_char_info:
                                    # 아이템 레벨 변경 확인
                                    old_level = old_char_info.get('item_level', '0')
                                    if old_level != item_level:
                                        # 아이템 레벨 숫자로 변환하여 비교
                                        old_level_num = float(old_level.replace(',', ''))
                                        new_level_num = float(item_level.replace(',', ''))
                                        
                                        # 상승했을 경우만 기록
                                        if new_level_num > old_level_num:
                                            level_increase = new_level_num - old_level_num
                                            change = {
                                                'character': char_name,
                                                'class': char_class,
                                                'old_level': old_level,
                                                'new_level': item_level,
                                                'difference': level_increase
                                            }
                                            member_changes.append(change)
                                            level_changes.append(change)
                                            changes_detected = True
                        
                        # 새 데이터 저장
                        new_data[member_id] = {
                            'discord_name': discord_name,
                            'discord_id': discord_id if discord_id else "",
                            'main_character': sorted_characters[0].get('CharacterName', '') if sorted_characters else (main_character or ''),
                            'characters': processed_characters,
                            'last_updated': datetime.datetime.now().isoformat()
                        }
                        
                        # 변경 사항이 있으면 디스코드에 메시지 전송
                        if member_changes:
                            embed = discord.Embed(
                                title=f"{discord_name}의 캐릭터 정보 변경",
                                color=discord.Color.green(),
                                timestamp=datetime.datetime.now()
                            )
                            
                            for change in member_changes:
                                embed.add_field(
                                    name=f"{change['character']} ({change['class']})",
                                    value=f"아이템 레벨: {change['old_level']} → {change['new_level']} (+{change['difference']:.2f})",
                                    inline=False
                                )
                            
                            await channel.send(embed=embed)
                            
                            # 레벨업 축하 메시지 전송 (모든 레벨업)
                            if level_changes and levelup_channel and discord_id:
                                for change in level_changes:
                                    level_embed = discord.Embed(
                                        title=f"🎉 레벨업 축하합니다! 🎉",
                                        description=f"<@{discord_id}>님의 {change['character']} ({change['class']}) 캐릭터가 {change['old_level']}에서 {change['new_level']}로 성장했습니다! (+{change['difference']:.2f})",
                                        color=discord.Color.gold(),
                                        timestamp=datetime.datetime.now()
                                    )
                                    
                                    level_embed.add_field(
                                        name=f"{change['character']} ({change['class']})",
                                        value=f"아이템 레벨: {change['old_level']} → {change['new_level']} (+{change['difference']:.2f})",
                                        inline=False
                                    )
                                    
                                    gif_urls = [
                                        "https://media.giphy.com/media/l4JySAWfMaY7w88sU/giphy.gif",
                                        "https://media.giphy.com/media/3oz8xAFtqoOUUrsh7W/giphy.gif",
                                        "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",
                                        "https://media.giphy.com/media/YTbZzCkRQCEJa/giphy.gif",
                                        "https://media.giphy.com/media/xT0xezQGU5xCDJuCPe/giphy.gif"
                                    ]
                                    
                                    # 랜덤 GIF 선택
                                    random_gif = gif_urls[hash(change['character']) % len(gif_urls)]
                                    level_embed.set_image(url=random_gif)
                                    
                                    await levelup_channel.send(embed=level_embed)
                
                except Exception as e:
                    print(f"멤버 {member_id} 정보 업데이트 중 오류: {e}")
            
            # 새 데이터 저장
            with open(self.character_data_path, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            
            # 업데이트 완료 메시지
            if changes_detected:
                print(f"{datetime.datetime.now()} - 멤버 정보 업데이트 완료: 변경 사항 있음")
            else:
                print(f"{datetime.datetime.now()} - 멤버 정보 업데이트 완료: 변경 사항 없음")
                
        except Exception as e:
            print(f"멤버 정보 업데이트 중 오류 발생: {e}")
    
    async def fetch_character_siblings(self, character_name: Optional[str]) -> Optional[List[Dict[str, Any]]]:
        """
        로스트아크 API를 사용하여 캐릭터의 계정 내 캐릭터 목록 가져오기
        """
        if not character_name:
            print("캐릭터 이름이 제공되지 않았습니다.")
            return None
        
        try:
            # API 호출에 필요한 헤더 설정
            headers = {
                'accept': 'application/json',
                'authorization': f'bearer {self.api_key}'
            }
            
            # 계정 내 캐릭터 목록 조회
            siblings_url = f'https://developer-lostark.game.onstove.com/characters/{urllib.parse.quote(character_name)}/siblings'
            response = requests.get(siblings_url, headers=headers)
            
            # 응답 코드 확인
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                print(f"API 요청 한도 초과: {response.headers.get('X-RateLimit-Remaining', 'N/A')}")
                return None
            else:
                print(f"API 요청 실패: 상태 코드 {response.status_code}")
                return None
                
        except Exception as e:
            print(f"캐릭터 정보 조회 중 오류: {e}")
            return None
    
    @commands.command(name='force_update')
    @commands.has_permissions(administrator=True)
    async def force_update(self, ctx):
        """
        관리자 명령어: 강제로 모든 멤버 정보 업데이트
        사용법: !force_update
        """
        await ctx.send("모든 멤버 정보 강제 업데이트를 시작합니다...")
        await self.update_all_members_data(ctx.channel)
        await ctx.send("멤버 정보 업데이트가 완료되었습니다.")
    
    @commands.command(name='show_character')
    async def show_character(self, ctx, member_id: Optional[str] = None):
        """
        멤버의 캐릭터 정보 조회
        사용법: !show_character [멤버ID]
        """
        try:
            with open(self.character_data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not member_id:
                # 모든 멤버 ID 출력
                member_list = list(data.keys())
                
                if not member_list:
                    await ctx.send("저장된 멤버 정보가 없습니다.")
                    return
                
                await ctx.send(f"저장된 멤버 목록: {', '.join(member_list)}\n특정 멤버의 정보를 보려면 `!show_character 멤버ID`를 입력하세요.")
                return
            
            if member_id not in data:
                await ctx.send(f"'{member_id}' 멤버의 정보를 찾을 수 없습니다.")
                return
            
            member_data = data[member_id]
            discord_name = member_data.get('discord_name', member_id)
            characters = member_data.get('characters', [])
            last_updated = member_data.get('last_updated', '알 수 없음')
            
            if not characters:
                await ctx.send(f"{discord_name}의 캐릭터 정보가 없습니다.")
                return
            
            # 임베드 생성
            embed = discord.Embed(
                title=f"{discord_name}의 캐릭터 정보",
                color=discord.Color.blue(),
                description=f"마지막 업데이트: {last_updated}"
            )
            
            # 최대 25개 캐릭터만 출력 (디스코드 제한)
            for idx, char in enumerate(characters[:25]):
                char_name = char.get('name', '알 수 없음')
                char_class = char.get('class', '알 수 없음')
                char_server = char.get('server', '알 수 없음')
                item_level = char.get('item_level', '0')
                
                embed.add_field(
                    name=f"{idx+1}. {char_name} ({char_server})",
                    value=f"클래스: {char_class}\n아이템 레벨: {item_level}",
                    inline=True
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"캐릭터 정보 조회 중 오류가 발생했습니다: {e}")

async def setup(bot):
    await bot.add_cog(CharacterUpdateScheduler(bot)) 