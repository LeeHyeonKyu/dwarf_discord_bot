import discord
import yaml
import json
import os
import asyncio
from dotenv import load_dotenv

# .env.secret 파일 로드
load_dotenv('.env.secret')
TOKEN = os.getenv('DISCORD_TOKEN')
TEST_CHANNEL_ID = int(os.getenv('TEST_CHANNEL_ID', '0'))

# 파일 경로 설정
RAIDS_CONFIG_PATH = 'configs/raids_config.yaml'
MEMBER_CHARACTERS_PATH = 'data/member_characters.json'

# 인텐트 설정
intents = discord.Intents.default()
intents.message_content = True

# 클라이언트 초기화
client = discord.Client(intents=intents)

async def load_raids_config():
    """레이드 구성 정보 로드"""
    try:
        with open(RAIDS_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config.get('raids', [])
    except Exception as e:
        print(f"레이드 구성 정보 로드 중 오류: {e}")
        return []

async def load_member_characters():
    """멤버별 캐릭터 정보 로드"""
    try:
        with open(MEMBER_CHARACTERS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
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

@client.event
async def on_ready():
    print(f'{client.user}로 로그인했습니다!')
    
    try:
        # 테스트 채널 가져오기
        channel = client.get_channel(TEST_CHANNEL_ID)
        if not channel:
            print(f"채널 ID {TEST_CHANNEL_ID}를 찾을 수 없습니다.")
            await client.close()
            return
        
        # 채널 타입 확인
        if not isinstance(channel, discord.TextChannel):
            print(f"채널 ID {TEST_CHANNEL_ID}는 텍스트 채널이 아닙니다. 텍스트 채널만 지원됩니다.")
            await client.close()
            return
        
        print(f"'{channel.name}' 채널에 레이드 스레드를 생성합니다...")
        
        # 레이드 구성 정보 로드
        raids = await load_raids_config()
        if not raids:
            print("레이드 구성 정보가 없습니다.")
            await client.close()
            return
        
        # 최소 레벨 기준으로 정렬 (낮은 순서부터)
        raids.sort(key=lambda x: x.get('min_level', 0))
        
        # 멤버 캐릭터 정보 로드
        member_characters = await load_member_characters()
        if not member_characters:
            print("멤버 캐릭터 정보가 없습니다.")
            await client.close()
            return
        
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
                    thread_message = f"# {raid_name} 참가 가능 멤버\n\n"
                    
                    # 모든 멤버 정보를 하나의 목록으로 표시
                    for member in members_data:
                        support_count = member['support_count']
                        dealer_count = member['dealer_count']
                        
                        # 멤버 기본 정보 (아이디, 디스코드 이름, 캐릭터 수)
                        thread_message += f"### {member['member_id']} (<@{member['discord_id']}>)\n"
                        thread_message += f"- 총 {member['total_count']}개 캐릭터 (서포터: {support_count}개, 딜러: {dealer_count}개)\n\n"
                        
                        # 서포터 캐릭터 목록
                        if support_count > 0:
                            thread_message += "**서포터**:\n"
                            # 아이템 레벨 기준으로 정렬
                            sorted_supports = sorted(member['support_chars'], key=lambda x: float(x['level'].replace(',', '')), reverse=True)
                            for char in sorted_supports:
                                thread_message += f"- 🔹 **{char['name']}** ({char['class']}, {char['level']})\n"
                            thread_message += "\n"
                        
                        # 딜러 캐릭터 목록
                        if dealer_count > 0:
                            thread_message += "**딜러**:\n"
                            # 아이템 레벨 기준으로 정렬
                            sorted_dealers = sorted(member['dealer_chars'], key=lambda x: float(x['level'].replace(',', '')), reverse=True)
                            for char in sorted_dealers:
                                thread_message += f"- 🔸 **{char['name']}** ({char['class']}, {char['level']})\n"
                        
                        thread_message += "\n\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    
                    # 총합 정보
                    total_support_chars = sum(member['support_count'] for member in members_data)
                    total_dealer_chars = sum(member['dealer_count'] for member in members_data)
                    total_chars = total_support_chars + total_dealer_chars
                    
                    thread_message += f"## 통계 정보\n"
                    thread_message += f"- 총 참가 가능 멤버: **{len(members_data)}명**\n"
                    thread_message += f"- 총 캐릭터: **{total_chars}개** (서포터: **{total_support_chars}개**, 딜러: **{total_dealer_chars}개**)\n"
                    thread_message += f"- 서포터 비율: **{total_support_chars / total_chars * 100:.1f}%**\n"
                    
                    await thread.send(thread_message)
                else:
                    await thread.send(f"현재 {raid_name} 레이드에 참가 가능한 멤버가 없습니다.")
            
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
        
    except Exception as e:
        print(f"오류 발생: {e}")
    
    # 작업 완료 후 봇 종료
    await client.close()

# 봇 실행
if __name__ == "__main__":
    if not TOKEN:
        print("DISCORD_TOKEN이 설정되어 있지 않습니다. .env.secret 파일을 확인해주세요.")
    elif TEST_CHANNEL_ID == 0:
        print("TEST_CHANNEL_ID가 .env.secret 파일에 설정되어 있지 않습니다.")
    else:
        asyncio.run(client.start(TOKEN)) 