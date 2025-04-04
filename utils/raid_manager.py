import discord
import yaml
import json
import os
import asyncio
import requests
import urllib.parse

# 파일 경로 설정
RAIDS_CONFIG_PATH = 'configs/raids_config.yaml'
MEMBERS_CONFIG_PATH = 'configs/members_config.yaml'
MEMBER_CHARACTERS_PATH = 'data/member_characters.json'

async def load_raids_config():
    """레이드 구성 정보 로드"""
    try:
        with open(RAIDS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('raids', [])
    except Exception as e:
        print(f"레이드 구성 정보 로드 중 오류: {e}")
        return []

async def load_members_config():
    """멤버 구성 정보 로드 - 활성 상태 확인용"""
    try:
        with open(MEMBERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            # 활성화된 멤버만 필터링
            all_members = config.get('members', [])
            active_members = [member for member in all_members if member.get('active', False)]
            return active_members
    except Exception as e:
        print(f"멤버 구성 정보 로드 중 오류: {e}")
        return []

async def fetch_character_siblings(character_name, api_key):
    """로스트아크 API를 사용하여 캐릭터의 계정 내 캐릭터 목록 가져오기"""
    if not character_name:
        print("캐릭터 이름이 제공되지 않았습니다.")
        return None
    
    try:
        # API 호출에 필요한 헤더 설정
        headers = {
            'accept': 'application/json',
            'authorization': f'bearer {api_key}'
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
        print(f"캐릭터 원정대 정보 조회 중 오류: {e}")
        return None

async def load_member_characters(active_only=True, api_key=None):
    """멤버별 캐릭터 정보 로드 (API 호출로 모든 대표 캐릭터의 원정대 정보 통합)"""
    try:
        with open(MEMBER_CHARACTERS_PATH, 'r', encoding='utf-8') as f:
            member_data = json.load(f)
            
            if active_only:
                # 활성화된 멤버 로드
                active_members = await load_members_config()
                
                # discord_id와 main_characters 매핑
                active_member_info = {}
                for member in active_members:
                    discord_id = member.get('discord_id', '')
                    main_characters = member.get('main_characters', [])
                    if discord_id:
                        active_member_info[discord_id] = {
                            'id': member.get('id', ''),
                            'main_characters': main_characters
                        }
                
                # 로스트아크 API 키가 없으면 API 조회를 건너뜀
                if not api_key:
                    print("로스트아크 API 키가 없어 추가 원정대 정보를 가져오지 않습니다.")
                    
                    # 활성화된 멤버만 필터링
                    filtered_data = {}
                    for discord_id, data in member_data.items():
                        if discord_id in active_member_info:
                            # 레벨 1600 미만 캐릭터 필터링
                            filtered_characters = []
                            for char in data.get('characters', []):
                                item_level_str = char.get('ItemAvgLevel', '0')
                                item_level = float(item_level_str.replace(',', ''))
                                if item_level >= 1600:
                                    filtered_characters.append(char)
                            
                            # 기존 데이터 사용하되 필터링된 캐릭터만 포함
                            filtered_data[discord_id] = data.copy()
                            filtered_data[discord_id]['characters'] = filtered_characters
                            
                            # 로그 출력
                            member_id = active_member_info[discord_id]['id']
                            main_characters = active_member_info[discord_id]['main_characters']
                            original_count = len(data.get('characters', []))
                            filtered_count = len(filtered_characters)
                            print(f"멤버 {member_id}({discord_id})의 대표 캐릭터: {main_characters}")
                            print(f"  - API 조회 없이 기존 데이터 사용: 총 {original_count}개 중 레벨 1600 이상 {filtered_count}개 캐릭터")
                    
                    return filtered_data
                
                # 활성화된 멤버만 필터링하고 모든 대표 캐릭터의 원정대 통합
                filtered_data = {}
                for discord_id, data in member_data.items():
                    if discord_id in active_member_info:
                        member_id = active_member_info[discord_id]['id']
                        main_characters = active_member_info[discord_id]['main_characters']
                        
                        # 기본 정보 복사 (나중에 characters 필드를 업데이트함)
                        filtered_data[discord_id] = data.copy()
                        
                        # 로그 출력
                        print(f"멤버 {member_id}({discord_id})의 대표 캐릭터: {main_characters}")
                        
                        # 대표 캐릭터가 없는 경우 기존 데이터 사용
                        if not main_characters:
                            # 레벨 1600 미만 캐릭터 필터링
                            filtered_characters = []
                            for char in data.get('characters', []):
                                item_level_str = char.get('ItemAvgLevel', '0')
                                item_level = float(item_level_str.replace(',', ''))
                                if item_level >= 1600:
                                    filtered_characters.append(char)
                            
                            filtered_data[discord_id]['characters'] = filtered_characters
                            original_count = len(data.get('characters', []))
                            filtered_count = len(filtered_characters)
                            print(f"  - 대표 캐릭터가 없어 기존 데이터 사용: 총 {original_count}개 중 레벨 1600 이상 {filtered_count}개 캐릭터")
                            continue
                        
                        # 모든 대표 캐릭터의 원정대 정보를 통합
                        all_characters = set()  # 중복 방지를 위해 집합 사용
                        character_objects = []
                        
                        for main_char in main_characters:
                            print(f"  - 대표 캐릭터 '{main_char}'의 원정대 정보 조회 중...")
                            
                            # API를 통해 원정대 정보 가져오기
                            siblings = await fetch_character_siblings(main_char, api_key)
                            
                            if siblings:
                                # 원정대 캐릭터 추가 (중복 없이, 1600 레벨 이상만)
                                for char in siblings:
                                    char_name = char.get('CharacterName', '')
                                    item_level_str = char.get('ItemMaxLevel', '0')
                                    item_level = float(item_level_str.replace(',', ''))
                                    
                                    if char_name and char_name not in all_characters and item_level >= 1600:
                                        all_characters.add(char_name)
                                        character_objects.append(char)
                                        print(f"    - 캐릭터 '{char_name}' 추가됨 (레벨: {item_level_str})")
                                    elif char_name and char_name not in all_characters:
                                        print(f"    - 캐릭터 '{char_name}' 제외됨 (레벨: {item_level_str} < 1600)")
                            else:
                                print(f"    ! 원정대 정보를 가져오지 못했습니다. API 오류 또는 제한")
                        
                        # 통합된 캐릭터 정보로 업데이트
                        filtered_data[discord_id]['characters'] = character_objects
                        print(f"  - 최종 통합된 캐릭터 수: {len(character_objects)}개 (모두 레벨 1600 이상)")
                        
                        # API 요청 제한 방지를 위한 지연
                        await asyncio.sleep(0.5)
                
                return filtered_data
            else:
                # 레벨 1600 미만 캐릭터 필터링
                filtered_data = {}
                for discord_id, data in member_data.items():
                    filtered_characters = []
                    for char in data.get('characters', []):
                        item_level_str = char.get('ItemAvgLevel', '0')
                        item_level = float(item_level_str.replace(',', ''))
                        if item_level >= 1600:
                            filtered_characters.append(char)
                    
                    filtered_data[discord_id] = data.copy()
                    filtered_data[discord_id]['characters'] = filtered_characters
                
                return filtered_data
    except Exception as e:
        print(f"멤버 캐릭터 정보 로드 중 오류: {e}")
        return {}

def get_eligible_members(member_characters, min_level, max_level=None):
    """특정 레벨 범위에 속하는 캐릭터를 가진 멤버 목록 및 캐릭터 수 반환"""
    eligible_members = {}
    
    for discord_id, member_data in member_characters.items():
        member_id = member_data.get('id', '')
        discord_name = member_data.get('discord_name', 'Unknown')
        characters = member_data.get('characters', [])
        
        # 해당 레벨 범위에 속하는 캐릭터 계산
        eligible_chars = []
        for char in characters:
            item_level_str = char.get('ItemMaxLevel', '0')
            item_level = float(item_level_str.replace(',', ''))
            
            if max_level is None:
                # 최소 레벨 이상인 경우
                if item_level >= min_level:
                    eligible_chars.append(char)
            else:
                # 레벨 범위 내인 경우 (max_level 미만으로 수정)
                if min_level <= item_level < max_level:
                    eligible_chars.append(char)
        
        # 적합한 캐릭터가 있는 경우만 추가
        if eligible_chars:
            eligible_members[discord_id] = {
                'id': member_id,
                'discord_name': discord_name,
                'eligible_characters': eligible_chars,
                'count': len(eligible_chars)
            }
    
    return eligible_members

async def create_raid_threads(client, channel_id, active_only=True, is_test=False, api_key=None):
    """레이드 스레드 생성 함수"""
    try:
        # 채널 가져오기
        channel = client.get_channel(channel_id)
        if not channel:
            print(f"채널 ID {channel_id}를 찾을 수 없습니다.")
            return False
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            print(f"채널 ID {channel_id}는 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            return False
        
        channel_type = "테스트" if is_test else "스케줄"
        print(f"'{channel.name}' {channel_type} 채널에 레이드 스레드를 생성합니다...")
        
        # 레이드 구성 정보 로드
        raids = await load_raids_config()
        if not raids:
            print("레이드 구성 정보가 없습니다.")
            return False
        
        # 정렬 기준 변경
        # 1. min_level 기준 오름차순
        # 2. min_level이 같으면 max_level이 있는 레이드 우선
        # 3. max_level이 있는 경우 max_level 기준 오름차순
        def raid_sort_key(raid):
            min_level = raid.get('min_level', 0)
            max_level = raid.get('max_level')
            # max_level이 있으면 해당 값 사용, 없으면 float('inf')(무한대) 사용
            max_level_value = max_level if max_level is not None else float('inf')
            return (min_level, max_level_value)
        
        raids.sort(key=raid_sort_key)
        
        # 멤버 캐릭터 정보 로드 (API 키 전달)
        member_characters = await load_member_characters(active_only=active_only, api_key=api_key)
        if not member_characters:
            member_status = "활성화된 " if active_only else ""
            print(f"{member_status}멤버의 캐릭터 정보가 없습니다.")
            return False
        
        member_status = "활성화된 " if active_only else ""
        print(f"{member_status}멤버 수: {len(member_characters)}명")
        
        # 테스트 모드인 경우 첫 번째 레이드만 처리
        if is_test:
            print("테스트 모드: 첫 번째 레이드만 스레드를 생성합니다.")
            if raids:
                raids = [raids[0]]
        
        # 각 레이드별로 메시지 및 스레드 생성
        for raid in raids:
            raid_name = raid.get('name', 'Unknown')
            min_level = raid.get('min_level', 0)
            max_level = raid.get('max_level')
            description = raid.get('description', '')
            members_count = raid.get('members', 8)
            
            # 레이드 템플릿 메시지 생성
            message_content = f"# {raid_name} ({description})\n"
            if max_level:
                message_content += f"🔹 필요 레벨: {min_level} ~ {max_level}\n"
            else:
                message_content += f"🔹 필요 레벨: {min_level} 이상\n"
            message_content += f"🔹 모집 인원: {members_count}명\n\n"
            
            try:
                # 메시지 전송
                raid_message = await channel.send(message_content)
                
                # 메시지로부터 스레드 생성
                thread_name = f"{raid_name} ({min_level}" + " ~ " + (f"{max_level}" if max_level else "") + ")"
                thread = await raid_message.create_thread(
                    name=thread_name,
                    auto_archive_duration=10080  # 7일 (분 단위)
                )
                
                # 해당 레벨 범위에 속하는 멤버 찾기
                eligible_members = get_eligible_members(member_characters, min_level, max_level)
                
                # 적합한 멤버 정보를 스레드에 메시지로 전송
                if eligible_members:
                    # 멤버별 캐릭터 정보 정리
                    members_data = []
                    
                    for discord_id, member_info in eligible_members.items():
                        discord_name = member_info['discord_name']
                        member_id = member_info['id']
                        eligible_chars = member_info['eligible_characters']
                        
                        # 서포터/딜러 캐릭터 분류
                        support_chars = []
                        dealer_chars = []
                        
                        for char in eligible_chars:
                            class_name = char.get('CharacterClassName', '')
                            char_name = char.get('CharacterName', '')
                            item_level = char.get('ItemMaxLevel', '0')
                            
                            # 서포터 클래스 확인 (홀리나이트, 바드, 도화가만 서포터로 분류)
                            if class_name in ['바드', '홀리나이트', '도화가']:
                                support_chars.append({
                                    'name': char_name,
                                    'class': class_name,
                                    'level': item_level
                                })
                            else:
                                dealer_chars.append({
                                    'name': char_name,
                                    'class': class_name,
                                    'level': item_level
                                })
                        
                        # 멤버 정보 저장
                        members_data.append({
                            'member_id': member_id,
                            'discord_name': discord_name,
                            'discord_id': discord_id,
                            'support_chars': support_chars,
                            'dealer_chars': dealer_chars,
                            'support_count': len(support_chars),
                            'dealer_count': len(dealer_chars),
                            'total_count': len(support_chars) + len(dealer_chars)
                        })
                    
                    # 총 캐릭터 수 기준으로 멤버 정렬
                    members_data.sort(key=lambda x: (x['support_count'] > 0, x['total_count']), reverse=True)
                    
                    # 스레드에 멤버 정보 메시지 전송
                    # 메시지 분할을 위한 설정
                    MAX_MESSAGE_LENGTH = 1900  # 여유 있게 2000보다 작게 설정
                    
                    # 헤더 메시지 전송
                    header_message = f"# {raid_name} 참가 가능 멤버"
                    if active_only:
                        header_message += " (활성 멤버만)"
                    header_message += "\n\n"
                    
                    await thread.send(header_message)
                    
                    # 멤버 정보를 개별 메시지로 분할
                    for member in members_data:
                        member_message = ""
                        support_count = member['support_count']
                        dealer_count = member['dealer_count']
                        
                        # 멤버 기본 정보 (아이디, 디스코드 이름, 캐릭터 수)
                        member_message += f"### {member['member_id']} (<@{member['discord_id']}>)\n"
                        member_message += f"- 총 {member['total_count']}개 캐릭터 (서포터: {support_count}개, 딜러: {dealer_count}개)\n\n"
                        
                        # 서포터 캐릭터 목록
                        if support_count > 0:
                            member_message += "**서포터**:\n"
                            # 아이템 레벨 기준으로 정렬
                            sorted_supports = sorted(member['support_chars'], key=lambda x: float(x['level'].replace(',', '')), reverse=True)
                            for char in sorted_supports:
                                member_message += f"- 🔹 **{char['name']}** ({char['class']}, {char['level']})\n"
                            member_message += "\n"
                        
                        # 딜러 캐릭터 목록
                        if dealer_count > 0:
                            member_message += "**딜러**:\n"
                            # 아이템 레벨 기준으로 정렬
                            sorted_dealers = sorted(member['dealer_chars'], key=lambda x: float(x['level'].replace(',', '')), reverse=True)
                            for char in sorted_dealers:
                                member_message += f"- 🔸 **{char['name']}** ({char['class']}, {char['level']})\n"
                        
                        member_message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        
                        # 멤버 메시지가 너무 길면 분할
                        if len(member_message) > MAX_MESSAGE_LENGTH:
                            parts = []
                            current_part = ""
                            lines = member_message.split('\n')
                            
                            for line in lines:
                                if len(current_part) + len(line) + 1 > MAX_MESSAGE_LENGTH:
                                    parts.append(current_part)
                                    current_part = line + '\n'
                                else:
                                    current_part += line + '\n'
                            
                            if current_part:
                                parts.append(current_part)
                            
                            for part in parts:
                                await thread.send(part)
                        else:
                            await thread.send(member_message)
                    
                    # 통계 정보는 별도 메시지로 전송
                    stats_message = "## 통계 정보\n"
                    total_support_chars = sum(member['support_count'] for member in members_data)
                    total_dealer_chars = sum(member['dealer_count'] for member in members_data)
                    total_chars = total_support_chars + total_dealer_chars
                    
                    stats_message += f"- 총 참가 가능 멤버: **{len(members_data)}명**\n"
                    stats_message += f"- 총 캐릭터: **{total_chars}개** (서포터: **{total_support_chars}개**, 딜러: **{total_dealer_chars}개**)\n"
                    
                    if total_chars > 0:
                        stats_message += f"- 서포터 비율: **{total_support_chars / total_chars * 100:.1f}%**\n"
                    
                    await thread.send(stats_message)
                else:
                    member_status = "활성화된 " if active_only else ""
                    await thread.send(f"현재 {raid_name} 레이드에 참가 가능한 {member_status}멤버가 없습니다.")
            
            except discord.Forbidden as e:
                print(f"{raid_name} 레이드 메시지 생성 중 권한 오류: {e}")
                continue
            except discord.HTTPException as e:
                print(f"{raid_name} 레이드 메시지 생성 중 HTTP 오류: {e}")
                continue
            except Exception as e:
                print(f"{raid_name} 레이드 메시지 생성 중 오류: {e}")
                continue
        
        print("모든 레이드 스레드 생성이 완료되었습니다.")
        return True
        
    except Exception as e:
        print(f"레이드 스레드 생성 중 오류 발생: {e}")
        return False

async def reset_channel(client, channel_id, is_test=False):
    """채널의 모든 메시지와 스레드를 초기화하는 함수"""
    try:
        # 채널 가져오기
        channel = client.get_channel(channel_id)
        if not channel:
            print(f"채널 ID {channel_id}를 찾을 수 없습니다.")
            return False
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            print(f"채널 ID {channel_id}는 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            return False
        
        channel_type = "테스트" if is_test else "스케줄"
        print(f"'{channel.name}' {channel_type} 채널의 모든 메시지와 스레드를 초기화합니다...")
        
        # 채널의 모든 스레드 가져오기
        threads = []
        async for thread in channel.archived_threads(limit=None):
            threads.append(thread)
        
        active_threads = channel.threads
        for thread in active_threads:
            threads.append(thread)
        
        # 스레드 삭제
        thread_count = len(threads)
        if thread_count > 0:
            print(f"스레드 {thread_count}개 삭제 중...")
            
            for thread in threads:
                try:
                    await thread.delete()
                    print(f"- 스레드 '{thread.name}' 삭제됨")
                except discord.Forbidden:
                    print(f"- 스레드 '{thread.name}' 삭제 권한이 없습니다.")
                except discord.HTTPException as e:
                    print(f"- 스레드 '{thread.name}' 삭제 중 오류 발생: {e}")
        
        # 메시지 삭제
        print("메시지 삭제 중... 이 작업은 시간이 걸릴 수 있습니다.")
        
        deleted_count = 0
        async for message in channel.history(limit=None):
            try:
                await message.delete()
                deleted_count += 1
                
                # 10개 메시지마다 상태 업데이트 (API 속도 제한 방지)
                if deleted_count % 10 == 0:
                    print(f"메시지 삭제 중... {deleted_count}개 완료")
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.5)
                    
            except discord.Forbidden:
                print("메시지 삭제 권한이 없습니다.")
                break
            except discord.HTTPException:
                continue
        
        # 완료 메시지
        print(f"채널 초기화 완료: {deleted_count}개의 메시지와 {thread_count}개의 스레드가 삭제되었습니다.")
        
        # 테스트 모드인 경우 메시지 추가
        if is_test:
            await channel.send("채널이 초기화되었습니다. 테스트 준비 완료!")
            
        return True
        
    except Exception as e:
        print(f"채널 초기화 중 오류 발생: {e}")
        return False 