import discord
from discord.ext import commands
import requests
import urllib.parse
import asyncio
import yaml

class LostarkCommands(commands.Cog):
    """로스트아크 API 관련 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = bot.config.get("LOSTARK_API_KEY")
    
    @commands.command(name='get_account_characters')
    async def get_account_characters(self, ctx, character_name: str):
        """
        로스트아크 API를 사용하여 계정 내 모든 캐릭터 정보 검색
        사용법: !get_account_characters 캐릭터이름
        """
        if not self.api_key:
            await ctx.send('로스트아크 API 키가 설정되어 있지 않습니다. .env.secret 파일에서 LOSTARK_API_KEY를 설정해주세요.')
            return
        
        try:
            await ctx.send(f'"{character_name}" 캐릭터의 계정 내 모든 캐릭터 정보를 검색 중입니다...')
            
            # API 호출에 필요한 헤더 설정
            headers = {
                'accept': 'application/json',
                'authorization': f'bearer {self.api_key}'
            }
            
            # 계정 내 캐릭터 목록 조회
            siblings_url = f'https://developer-lostark.game.onstove.com/characters/{urllib.parse.quote(character_name)}/siblings'
            siblings_response = requests.get(siblings_url, headers=headers)
            
            # 응답 코드 확인
            if siblings_response.status_code == 200:
                siblings_data = siblings_response.json()
                
                # 응답 헤더에서 API 요청 제한 정보 확인
                remaining_requests = siblings_response.headers.get('X-RateLimit-Remaining', 'N/A')
                
                # 캐릭터 목록 임베드 생성
                embed = discord.Embed(
                    title=f'{character_name}의 계정 캐릭터 목록',
                    color=discord.Color.blue(),
                    description=f'총 {len(siblings_data)}개의 캐릭터가 있습니다.'
                )
                
                # 캐릭터 정보 정렬 (아이템 레벨 기준 내림차순)
                sorted_characters = sorted(
                    siblings_data,
                    key=lambda x: float(x.get('ItemMaxLevel', '0').replace(',', '')),
                    reverse=True
                )
                
                # 캐릭터 정보를 임베드에 추가
                for idx, char in enumerate(sorted_characters[:25]):  # 최대 25개만 표시 (디스코드 임베드 제한)
                    char_name = char.get('CharacterName', '알 수 없음')
                    server = char.get('ServerName', '')
                    char_class = char.get('CharacterClassName', '알 수 없음')
                    item_level = char.get('ItemMaxLevel', '0')
                    
                    # 탱커 역할 판별
                    tank_classes = ['워로드', '건슬링어', '디스트로이어', '블래스터', '홀리나이트']
                    role = "탱커" if char_class in tank_classes else "딜러"
                    
                    # 인덱스 번호와 함께 캐릭터 정보 추가
                    embed.add_field(
                        name=f"{idx+1}. {char_name} ({server})",
                        value=f"클래스: {char_class}\n아이템 레벨: {item_level}\n역할: {role}",
                        inline=True
                    )
                
                # 푸터에 API 요청 정보 추가
                embed.set_footer(text=f'API 요청 남은 횟수: {remaining_requests}')
                
                # 정보를 디스코드에 출력
                await ctx.send(embed=embed)
                
                # members.yaml 파일에 저장할 내용 준비
                character_list = []
                for char in siblings_data:
                    char_name = char.get('CharacterName', '')
                    char_class = char.get('CharacterClassName', '')
                    item_level = char.get('ItemMaxLevel', '0').replace(',', '')
                    
                    # 탱커 역할 판별
                    tank_classes = ['워로드', '건슬링어', '디스트로이어', '블래스터', '홀리나이트']
                    role = "탱커" if char_class in tank_classes else "딜러"
                    
                    character_list.append({
                        "name": char_name,
                        "class": char_class,
                        "level": item_level,
                        "role": role
                    })
                
                # 메인 캐릭터 (가장 높은 레벨)
                main_character = sorted_characters[0].get('CharacterName') if sorted_characters else character_name
                
                # 캐릭터 데이터 구성
                character_data = {
                    "discord_name": character_name,  # 디스코드 이름은 입력한 캐릭터 이름으로 설정
                    "main_character": main_character,
                    "characters": character_list
                }
                
                # 추가 정보 저장 여부 물어보기
                await ctx.send(f'이 계정의 캐릭터 정보를 members.yaml에 추가할까요? 추가하려면 "예"를 입력해주세요.')
                
                def check(m):
                    return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['예', '네', 'yes', 'y']
                
                try:
                    # 30초 동안 응답 대기
                    await self.bot.wait_for('message', check=check, timeout=30.0)
                    
                    # members.yaml 파일 업데이트
                    try:
                        # YAML 파일 로드
                        with open('members.yaml', 'r', encoding='utf-8') as file:
                            member_data = yaml.safe_load(file)
                        
                        # 이미 존재하는지 확인
                        existing_member = next((m for m in member_data['members'] if m['discord_name'] == character_name), None)
                        if existing_member:
                            # 기존 멤버 정보 업데이트
                            existing_member.update(character_data)
                            await ctx.send(f'기존 멤버 "{character_name}"의 정보를 업데이트했습니다.')
                        else:
                            # 새로운 멤버 추가
                            # 역할 목록 생성 (중복 제거)
                            roles = list(set([char["role"] for char in character_list]))
                            
                            member_data['members'].append({
                                "id": character_name,
                                **character_data,
                                "roles": roles
                            })
                            await ctx.send(f'새 멤버 "{character_name}"를 추가했습니다.')
                        
                        # 파일 저장
                        with open('members.yaml', 'w', encoding='utf-8') as file:
                            yaml.dump(member_data, file, allow_unicode=True, sort_keys=False)
                    
                    except Exception as e:
                        await ctx.send(f'members.yaml 파일 처리 중 오류: {e}')
                
                except asyncio.TimeoutError:
                    await ctx.send('응답 시간이 초과되었습니다. 캐릭터 정보는 저장되지 않았습니다.')
            
            elif siblings_response.status_code == 401:
                await ctx.send('로스트아크 API 키가 유효하지 않습니다.')
            elif siblings_response.status_code == 404:
                await ctx.send(f'"{character_name}" 캐릭터를 찾을 수 없습니다.')
            elif siblings_response.status_code == 429:
                await ctx.send('API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.')
            else:
                await ctx.send(f'API 요청 중 오류가 발생했습니다. 상태 코드: {siblings_response.status_code}')
        
        except Exception as e:
            await ctx.send(f'캐릭터 정보 검색 중 오류가 발생했습니다: {e}')
    
    @commands.command(name='search_lostark_character')
    async def search_lostark_character(self, ctx, character_name: str):
        """
        로스트아크 API를 사용하여 캐릭터 정보 검색
        사용법: !search_lostark_character 캐릭터이름
        """
        if not self.api_key:
            await ctx.send('로스트아크 API 키가 설정되어 있지 않습니다. .env.secret 파일에서 LOSTARK_API_KEY를 설정해주세요.')
            return
        
        try:
            await ctx.send(f'"{character_name}" 캐릭터 정보를 검색 중입니다...')
            
            # API 호출에 필요한 헤더 설정
            headers = {
                'accept': 'application/json',
                'authorization': f'bearer {self.api_key}'
            }
            
            # 캐릭터 기본 정보 조회
            profile_url = f'https://developer-lostark.game.onstove.com/armories/characters/{urllib.parse.quote(character_name)}/profiles'
            profile_response = requests.get(profile_url, headers=headers)
            
            # 응답 코드 확인
            if profile_response.status_code == 200:
                profile_data = profile_response.json()
                
                # 응답 헤더에서 API 요청 제한 정보 확인
                remaining_requests = profile_response.headers.get('X-RateLimit-Remaining', 'N/A')
                
                # 캐릭터 정보 구성
                character_info = discord.Embed(
                    title=f'{profile_data.get("CharacterName", "알 수 없음")} 캐릭터 정보',
                    color=discord.Color.blue()
                )
                
                # 기본 정보 추가
                character_info.add_field(name='서버', value=profile_data.get('ServerName', '알 수 없음'), inline=True)
                character_info.add_field(name='클래스', value=profile_data.get('CharacterClassName', '알 수 없음'), inline=True)
                character_info.add_field(name='전투 레벨', value=profile_data.get('CharacterLevel', '알 수 없음'), inline=True)
                character_info.add_field(name='아이템 레벨', value=profile_data.get('ItemAvgLevel', '알 수 없음'), inline=True)
                
                # 특성 정보 추가
                if 'Stats' in profile_data:
                    stats = profile_data['Stats']
                    stats_text = ''
                    for stat in stats:
                        stats_text += f"{stat.get('Type', '')}: {stat.get('Value', 0)}\n"
                    character_info.add_field(name='특성', value=stats_text or '정보 없음', inline=False)
                
                # 각인 정보
                if 'Engravings' in profile_data and profile_data['Engravings']:
                    engravings_text = ''
                    for engraving in profile_data['Engravings']:
                        engravings_text += f"{engraving.get('Name', '')} Lv.{engraving.get('Level', 0)}\n"
                    character_info.add_field(name='각인', value=engravings_text or '정보 없음', inline=False)
                
                # 푸터에 API 요청 정보 추가
                character_info.set_footer(text=f'API 요청 남은 횟수: {remaining_requests}')
                
                # members.yaml 파일에 저장할 내용 준비
                character_data = {
                    "discord_name": character_name,  # 실제로는 디스코드 이름과 캐릭터 이름이 다를 수 있음
                    "main_character": character_name,
                    "characters": [{
                        "name": character_name,
                        "class": profile_data.get('CharacterClassName', '알 수 없음'),
                        "level": profile_data.get('ItemAvgLevel', '0').replace(',', ''),
                        "role": "탱커" if profile_data.get('CharacterClassName') in ['워로드', '건슬링어', '디스트로이어', '홀리나이트'] else "딜러"
                    }]
                }
                
                # 정보를 디스코드에 출력
                await ctx.send(embed=character_info)
                
                # 추가 정보 저장 여부 물어보기
                await ctx.send(f'이 캐릭터 정보를 members.yaml에 추가할까요? 추가하려면 "예"를 입력해주세요.')
                
                def check(m):
                    return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['예', '네', 'yes', 'y']
                
                try:
                    # 30초 동안 응답 대기
                    await self.bot.wait_for('message', check=check, timeout=30.0)
                    
                    # members.yaml 파일 업데이트
                    try:
                        # YAML 파일 로드
                        with open('members.yaml', 'r', encoding='utf-8') as file:
                            member_data = yaml.safe_load(file)
                        
                        # 이미 존재하는지 확인
                        existing_member = next((m for m in member_data['members'] if m['discord_name'] == character_name), None)
                        if existing_member:
                            # 기존 멤버 정보 업데이트
                            existing_member.update(character_data)
                            await ctx.send(f'기존 멤버 "{character_name}"의 정보를 업데이트했습니다.')
                        else:
                            # 새로운 멤버 추가
                            member_data['members'].append({
                                "id": character_name,
                                **character_data,
                                "roles": [character_data["characters"][0]["role"]]
                            })
                            await ctx.send(f'새 멤버 "{character_name}"를 추가했습니다.')
                        
                        # 파일 저장
                        with open('members.yaml', 'w', encoding='utf-8') as file:
                            yaml.dump(member_data, file, allow_unicode=True, sort_keys=False)
                    
                    except Exception as e:
                        await ctx.send(f'members.yaml 파일 처리 중 오류: {e}')
                
                except asyncio.TimeoutError:
                    await ctx.send('응답 시간이 초과되었습니다. 캐릭터 정보는 저장되지 않았습니다.')
            
            elif profile_response.status_code == 401:
                await ctx.send('로스트아크 API 키가 유효하지 않습니다.')
            elif profile_response.status_code == 404:
                await ctx.send(f'"{character_name}" 캐릭터를 찾을 수 없습니다.')
            elif profile_response.status_code == 429:
                await ctx.send('API 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요.')
            else:
                await ctx.send(f'API 요청 중 오류가 발생했습니다. 상태 코드: {profile_response.status_code}')
        
        except Exception as e:
            await ctx.send(f'캐릭터 정보 검색 중 오류가 발생했습니다: {e}')

async def setup(bot):
    await bot.add_cog(LostarkCommands(bot)) 