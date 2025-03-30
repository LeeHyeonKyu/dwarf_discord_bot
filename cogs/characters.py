import discord
from discord.ext import commands
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import yaml

class CharacterCommands(commands.Cog):
    """캐릭터 정보 관련 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name='update_characters')
    async def update_characters(self, ctx, member_id=None):
        """
        멤버의 캐릭터 정보를 kloa.gg에서 가져와 업데이트
        사용법: !update_characters [멤버ID]
        """
        try:
            await ctx.send('캐릭터 정보 업데이트를 시작합니다. 잠시만 기다려주세요...')
            
            # YAML 파일 로드
            with open('members.yaml', 'r', encoding='utf-8') as file:
                member_data = yaml.safe_load(file)
            
            # 업데이트할 멤버 선택
            members_to_update = []
            if member_id:
                # 특정 멤버만 업데이트
                member = next((m for m in member_data['members'] if m['id'] == member_id), None)
                if not member:
                    await ctx.send(f'멤버 ID를 찾을 수 없습니다: {member_id}')
                    return
                members_to_update.append(member)
            else:
                # 모든 멤버 업데이트
                members_to_update = member_data['members']
                
            update_count = 0
            error_count = 0
            
            for member in members_to_update:
                try:
                    await ctx.send(f'{member["discord_name"]} 캐릭터 정보 가져오는 중...')
                    
                    # kloa.gg URL 생성
                    encoded_name = urllib.parse.quote(member['discord_name'])
                    url = f'https://kloa.gg/characters/{encoded_name}'
                    
                    # 웹 페이지 요청
                    response = requests.get(url)
                    if response.status_code != 200:
                        await ctx.send(f'kloa.gg에서 {member["discord_name"]} 정보를 가져올 수 없습니다.')
                        error_count += 1
                        continue
                    
                    # HTML 파싱
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # 대표 캐릭터 정보 추출
                    main_character_element = soup.select_one('.lv-wrapper')
                    if main_character_element:
                        level_match = re.search(r'Lv\.(\d+)', main_character_element.text)
                        level = level_match.group(1) if level_match else ""
                        
                        character_name_element = soup.select_one('h2.character-name')
                        character_name = character_name_element.text.strip() if character_name_element else ""
                        
                        item_level_element = soup.select_one('.il-gauge-wrapper')
                        item_level = ""
                        if item_level_element:
                            item_level_match = re.search(r'([\d,.]+)', item_level_element.text)
                            item_level = item_level_match.group(1) if item_level_match else ""
                        
                        # 대표 캐릭터 정보 업데이트
                        member['main_character'] = character_name
                        
                        # 보유 캐릭터 정보 추출
                        character_list = []
                        character_elements = soup.select('.character-list .character-card')
                        
                        for char_element in character_elements:
                            char_name_element = char_element.select_one('.character-name')
                            char_level_element = char_element.select_one('.il-wrapper')
                            
                            if char_name_element and char_level_element:
                                char_name = char_name_element.text.strip()
                                
                                # 아이템 레벨에서 숫자만 추출
                                level_text = char_level_element.text.strip()
                                level_match = re.search(r'([\d,.]+)', level_text)
                                char_level = level_match.group(1) if level_match else "0"
                                
                                # 캐릭터 역할 (탱커/딜러) 결정 - 여기서는 클래스별로 간단하게 구분
                                # 실제로는 더 정확한 클래스 판별 로직이 필요할 수 있음
                                char_class_element = char_element.select_one('.character-class')
                                char_class = char_class_element.text.strip() if char_class_element else ""
                                
                                # 간단하게 탱커 클래스 구분 (워로드, 건슬링어, 디스트로이어 등)
                                tank_classes = ['워로드', '건슬링어', '디스트로이어', '블래스터', '홀리나이트']
                                role = "탱커" if any(tank in char_class for tank in tank_classes) else "딜러"
                                
                                character_list.append({
                                    "name": char_name,
                                    "class": char_class,
                                    "level": char_level,
                                    "role": role
                                })
                        
                        # 캐릭터 목록 업데이트
                        member['characters'] = character_list
                        
                        update_count += 1
                    else:
                        await ctx.send(f'{member["discord_name"]}의 캐릭터 정보를 찾을 수 없습니다.')
                        error_count += 1
                
                except Exception as e:
                    await ctx.send(f'{member["discord_name"]} 정보 처리 중 오류: {e}')
                    error_count += 1
            
            # 업데이트된 정보 저장
            with open('members.yaml', 'w', encoding='utf-8') as file:
                yaml.dump(member_data, file, allow_unicode=True, sort_keys=False)
                
            await ctx.send(f'캐릭터 정보 업데이트 완료! 성공: {update_count}, 실패: {error_count}')
            
        except Exception as e:
            await ctx.send(f'캐릭터 정보 업데이트 중 오류가 발생했습니다: {e}')

async def setup(bot):
    await bot.add_cog(CharacterCommands(bot)) 