import discord
from discord.ext import commands
import asyncio
import datetime
import json
import re
import os
import aiohttp
import hashlib
import pathlib
import logging
import sys
from typing import List, Dict, Any, Optional

from .raid_scheduler_common import RaidSchedulerBase, logger
from utils.raid_queue import raid_queue_manager, RoundInfo

# 로깅 설정 변경: 표준 출력(stdout)으로 로그를 보내도록 설정
logger = logging.getLogger('thread_commands')
logger.setLevel(logging.INFO)

# 표준 출력으로 로그 보내기
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# root 로거 설정도 업데이트
root_logger = logging.getLogger()
if not root_logger.handlers:
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

class ThreadCommands(commands.Cog, RaidSchedulerBase):
    """스레드 내 일정 관리 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
        RaidSchedulerBase.__init__(self, bot)
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # 캐시 디렉토리 설정
        self.cache_dir = pathlib.Path('/tmp/discord_bot_llm_cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("ThreadCommands 초기화 완료")
    
    def cog_check(self, ctx):
        """모든 명령어가 이 검사를 통과해야 함
        
        스레드 내에서는 권한 체크를 우회하여 모든 사용자가 사용 가능
        """
        # 스레드 내에서만 명령 허용
        return isinstance(ctx.channel, discord.Thread)
    
    @commands.command(name="추가")
    async def add_schedule(self, ctx):
        """일정 추가 명령어"""
        # 스레드가 아니면 무시 (cog_check에서 이미 확인하지만 명확성을 위해 유지)
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 스레드에서만 사용할 수 있습니다.")
            return
            
        await self.process_schedule_command(ctx, "추가")
    
    @commands.command(name="제거")
    async def remove_schedule(self, ctx):
        """일정 제거 명령어"""
        # 스레드가 아니면 무시
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 스레드에서만 사용할 수 있습니다.")
            return
            
        await self.process_schedule_command(ctx, "제거")
    
    @commands.command(name="수정")
    async def update_schedule(self, ctx):
        """일정 수정 명령어"""
        # 스레드가 아니면 무시
        if not isinstance(ctx.channel, discord.Thread):
            await ctx.send("이 명령어는 스레드에서만 사용할 수 있습니다.")
            return
            
        await self.process_schedule_command(ctx, "수정")
    
    async def process_schedule_command(self, ctx, command_type):
        """일정 명령어 처리 함수"""
        # 메시지 전송
        logger.info(f"일정 {command_type} 명령어 처리 시작 - 사용자: {ctx.author.display_name}({ctx.author.id})")
        processing_msg = await ctx.send(f"일정 {command_type} 요청을 처리 중입니다...")
        
        try:
            # 1. 스레드 정보 가져오기
            thread = ctx.channel
            logger.info(f"스레드 정보 - ID: {thread.id}, 이름: {thread.name}")
            
            # 2. 스레드의 상위 채널과 시작 메시지 찾기
            parent_channel = thread.parent
            if not parent_channel:
                logger.error("스레드의 원본 채널을 찾을 수 없습니다.")
                await processing_msg.edit(content="스레드의 원본 채널을 찾을 수 없습니다.")
                return
                
            logger.info(f"부모 채널 정보 - ID: {parent_channel.id}, 이름: {parent_channel.name}")
            
            # 스레드 시작 메시지 찾기
            starter_message = None
            
            # 스레드가 메시지에서 시작된 경우
            if hasattr(thread, 'starter_message_id') and thread.starter_message_id:
                try:
                    starter_message = await parent_channel.fetch_message(thread.starter_message_id)
                    logger.info(f"스레드 시작 메시지 찾음 - ID: {starter_message.id}")
                except Exception as e:
                    logger.error(f"스레드 시작 메시지 조회 실패: {e}")
            
            # 시작 메시지를 찾지 못한 경우, 스레드 제목과 일치하는 메시지 검색
            if not starter_message:
                logger.info(f"스레드 시작 메시지를 찾지 못했습니다. 채널에서 관련 메시지 검색 중...")
                
                # 스레드 이름에서 레이드 이름 추출
                raid_name = thread.name
                if "(" in raid_name:
                    raid_name = raid_name.split("(")[0].strip()
                    
                logger.info(f"검색할 레이드 이름: {raid_name}")
                
                # 레이드 이름을 포함하는 메시지 검색
                async for message in parent_channel.history(limit=50):
                    if raid_name.lower() in message.content.lower():
                        starter_message = message
                        logger.info(f"레이드 이름으로 시작 메시지 찾음 - ID: {message.id}")
                        break
            
            # 여전히 시작 메시지를 찾지 못한 경우, 대체 메시지 생성
            if not starter_message:
                logger.warning("스레드 관련 메시지를 찾지 못했습니다. 대체 메시지 작성 필요.")
                
                # 스레드 내에서 이 봇이 작성한 일정 메시지 검색
                async for message in thread.history(limit=20):
                    if message.author.id == self.bot.user.id and "🔹" in message.content:
                        starter_message = message
                        logger.info(f"스레드 내 봇의 일정 메시지 찾음 - ID: {message.id}")
                        break
            
            # 3. 스레드 메시지 수집
            logger.info("스레드 메시지 수집 시작")
            thread_messages = []
            async for message in thread.history(limit=100):
                if not message.author.bot:  # 봇 메시지 제외
                    thread_messages.append({
                        'author': message.author.display_name,
                        'author_id': str(message.author.id),
                        'content': message.content,
                        'created_at': message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'author_mention': message.author.mention
                    })
            
            # 최신 메시지가 먼저 오기 때문에 순서 뒤집기
            thread_messages.reverse()
            logger.info(f"총 {len(thread_messages)}개의 메시지 수집 완료")
            
            # 4. 원본 콘텐츠 준비
            original_content = ""
            
            if starter_message:
                original_content = starter_message.content
                logger.info(f"시작 메시지 내용: {original_content[:50]}...")
            else:
                # 시작 메시지가 없는 경우 기본 템플릿
                raid_name = thread.name
                original_content = f"{raid_name}\n🔹 필요 레벨: 레벨 이상\n🔹 모집 인원: 8명\n\n1차\nwhen:\nwho:\n서포터(0/2):\n딜러(0/6):\nnote:"
                logger.info("시작 메시지가 없어 기본 템플릿 사용")
            
            # 5. LLM 요청 처리
            logger.info("LLM 요청 처리 시작")
            # 명령어 내용에서 역할 정보 추출
            command_content = ctx.message.content
            # 명령어 자체(!추가 등)를 제외한 내용
            if " " in command_content:
                command_params = command_content.split(" ", 1)[1]
            else:
                command_params = ""
                
            logger.info(f"명령어 파라미터: '{command_params}'")
            
            result = await self.analyze_schedule_with_llm(
                thread_messages,
                original_content,
                command_type,
                ctx.author.display_name,
                str(ctx.author.id),
                command_params,
                ctx.author.mention
            )
            
            # 유효성 검사 및 일정 자동 수정
            result = self.validate_and_fix_schedule(result)
            
            # 상태 확인
            if result.get("status") == "error":
                error_msg = result.get("error", "알 수 없는 오류가 발생했습니다.")
                logger.error(f"LLM 처리 오류: {error_msg}")
                await processing_msg.edit(content=f"오류가 발생했습니다: {error_msg}")
                return
                
            # 6. 메시지 업데이트 또는 생성
            if "updated_content" in result:
                updated_content = result["updated_content"]
                logger.info(f"업데이트된 내용: {updated_content[:50]}...")
                
                try:
                    if starter_message:
                        # 시작 메시지 또는 찾은 메시지 업데이트
                        logger.info(f"메시지 ID {starter_message.id} 업데이트 시도")
                        update_result = await self.update_message_safely(starter_message, updated_content)
                        
                        if update_result["status"] == "success":
                            logger.info("메시지 업데이트 성공")
                        else:
                            logger.error(f"메시지 업데이트 실패: {update_result['reason']}")
                            await processing_msg.edit(content=f"메시지 업데이트 실패: {update_result['reason']}")
                            return
                    else:
                        # 시작 메시지가 없는 경우 새 메시지 생성
                        logger.info("새 일정 메시지 생성")
                        starter_message = await thread.send(updated_content)
                        logger.info(f"새 일정 메시지 생성 성공 - ID: {starter_message.id}")
                    
                    # 결과 요약 준비
                    success_msg = f"일정이 {command_type}되었습니다"
                    
                    # 영향받은 차수 정보 추가
                    if "affected_rounds" in result and result["affected_rounds"]:
                        affected_rounds = ", ".join([str(r) for r in result["affected_rounds"]])
                        success_msg += f" ({affected_rounds}차)"
                    
                    # 역할 정보 추가
                    if "user_role" in result and result["user_role"]:
                        success_msg += f" - {result['user_role']}"
                    
                    # 변경 내용 추가
                    if "changes" in result and result["changes"]:
                        success_msg += f": {result['changes']}"
                    else:
                        success_msg += "!"
                        
                    await processing_msg.edit(content=success_msg)
                    
                except Exception as e:
                    logger.error(f"메시지 업데이트 중 오류: {e}")
                    await processing_msg.edit(content=f"메시지 업데이트 중 오류: {e}")
            else:
                logger.warning("updated_content 필드가 없습니다")
                await processing_msg.edit(content="일정 업데이트에 필요한 정보가 충분하지 않습니다.")
                
        except Exception as e:
            logger.error(f"처리 중 예외 발생: {e}", exc_info=True)
            await processing_msg.edit(content=f"처리 중 오류가 발생했습니다: {e}")
    
    def get_cache_key(self, data):
        """캐시 키 생성"""
        # 입력 데이터를 문자열로 직렬화
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        
        # SHA-256 해시 생성
        hash_obj = hashlib.sha256(data_str.encode('utf-8'))
        return hash_obj.hexdigest()
    
    def get_cached_result(self, cache_key):
        """캐시에서 결과 가져오기"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                # print() 대신 logger 사용
                logger.info(f"캐시에서 결과를 로드했습니다: {cache_key}")
                return cached_data
            except Exception as e:
                # print() 대신 logger 사용
                logger.error(f"캐시 로드 중 오류 발생: {e}")
        return None
    
    def save_to_cache(self, cache_key, result):
        """결과를 캐시에 저장"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            # print() 대신 logger 사용
            logger.info(f"결과를 캐시에 저장했습니다: {cache_key}")
        except Exception as e:
            # print() 대신 logger 사용
            logger.error(f"캐시 저장 중 오류 발생: {e}")
    
    async def analyze_schedule_with_llm(self, thread_messages, message_content, command_type, user_name, user_id, command_params, user_mention):
        """LLM을 사용하여 일정 변경 분석"""
        try:
            # 캐시 키 생성
            cache_data = {
                "thread_messages": thread_messages[-5:] if thread_messages else [],  # 최근 5개 메시지만 사용
                "message_content": message_content[:100],  # 처음 100자만 사용
                "command_type": command_type,
                "user_name": user_name,
                "command_params": command_params
            }
            cache_key = self.get_cache_key(cache_data)
            
            # 캐시 확인
            cached_result = self.get_cached_result(cache_key)
            if cached_result:
                return cached_result
            
            # 스레드 ID 가져오기
            thread_id = str(thread_messages[0]['author_id']) if thread_messages else "unknown"
            
            # 명령어 타입 확인 및 처리
            if command_type == "추가":
                # 추가 명령어 처리
                # 여러 역할과 횟수를 처리하기 위한 정규식 패턴
                dealer_pattern = re.compile(r'딜(\d+)|(\d+)딜러?|dealer(\d+)|(\d+)dealer')
                support_pattern = re.compile(r'폿(\d+)|(\d+)폿|서폿(\d+)|(\d+)서폿|서포터(\d+)|(\d+)서포터|support(\d+)|(\d+)support')
                
                # 역할별 추가 횟수 추출
                dealer_count = 0
                support_count = 0
                
                # 딜러 횟수 추출
                dealer_matches = dealer_pattern.findall(command_params.lower())
                for match_groups in dealer_matches:
                    for group in match_groups:
                        if group and group.isdigit():
                            dealer_count += int(group)
                            break
                
                # 서포터 횟수 추출
                support_matches = support_pattern.findall(command_params.lower())
                for match_groups in support_matches:
                    for group in match_groups:
                        if group and group.isdigit():
                            support_count += int(group)
                            break
                
                # 숫자 없이 역할만 언급된 경우 처리
                if dealer_count == 0 and (re.search(r'딜러?|dealer', command_params.lower()) and not re.search(r'\d+\s*딜러?|\d+\s*dealer', command_params.lower())):
                    dealer_count = 1
                
                if support_count == 0 and (re.search(r'폿|서폿|서포터|support', command_params.lower()) and not re.search(r'\d+\s*폿|\d+\s*서폿|\d+\s*서포터|\d+\s*support', command_params.lower())):
                    support_count = 1
                
                # 라운드 추출
                round_num = 0  # 기본값
                round_match = re.search(r'(\d+)\s*차', command_params)
                if round_match:
                    round_num = int(round_match.group(1))
                
                # 큐 객체 가져오기
                queue = raid_queue_manager.get_queue(thread_id)
                
                # 사용자의 멘션 형태 참조 (Discord에 표시되는 방식)
                user_mention_format = f"<@{user_id}>"
                logger.info(f"사용자 멘션 형태: {user_mention_format}")
                logger.info(f"추가 명령어 차수 정보: {round_num}차")
                
                # 기존에 큐에 있던 사용자 데이터 확인
                user_elements = queue.get_elements_by_user(user_name)
                if not user_elements:
                    # 멘션 형태로도 확인
                    user_elements = queue.get_elements_by_user(user_mention_format)
                    if user_elements:
                        logger.info(f"사용자 {user_name}은 멘션 형태({user_mention_format})로 큐에 있음")
                
                # 딜러 추가
                for _ in range(dealer_count):
                    queue_element = raid_queue_manager.process_add_command(
                        thread_id, 
                        user_id, 
                        user_mention_format,  # 멘션 형태로 통일
                        "dealer", 
                        round_num  # 실제 차수 정보 전달
                    )
                    logger.info(f"딜러 추가됨: {queue_element} (차수: {round_num})")
                
                # 서포터 추가
                for _ in range(support_count):
                    queue_element = raid_queue_manager.process_add_command(
                        thread_id, 
                        user_id, 
                        user_mention_format,  # 멘션 형태로 통일
                        "support", 
                        round_num  # 실제 차수 정보 전달
                    )
                    logger.info(f"서포터 추가됨: {queue_element} (차수: {round_num})")
                
                # 적어도 하나의 역할이 추가되었는지 확인
                if dealer_count == 0 and support_count == 0:
                    # 역할 패턴이 없는 경우 기본 처리(기존 방식)
                    role_match = re.search(r'(서포터|서폿|support|딜러|딜|dealer)', command_params.lower())
                    role = "dealer"  # 기본값
                    if role_match:
                        role_text = role_match.group(1)
                        if role_text in ["서포터", "서폿", "support"]:
                            role = "support"
                    
                    queue_element = raid_queue_manager.process_add_command(
                        thread_id, 
                        user_id, 
                        user_mention_format,  # 멘션 형태로 통일
                        role, 
                        round_num  # 실제 차수 정보 전달
                    )
                    logger.info(f"기본 역할({role}) 추가됨: {queue_element} (차수: {round_num})")
                
                # 원본 메시지 파싱
                raid_data = await self.parse_message_to_data(message_content)
                
                # 메시지에서 "없음" 텍스트가 있는지 확인하고 제거
                message_content = message_content.replace("없음", "")
                
                # 큐에서 일정 메시지 생성
                schedule_message, round_infos = queue.generate_schedule_message()
                
                # 원본 헤더 정보 유지
                header_lines = []
                for line in message_content.split("\n"):
                    if line.strip() and not re.match(r'^\d+차', line) and "서포터" not in line and "딜러" not in line:
                        header_lines.append(line)
                    else:
                        break
                
                header = "\n".join(header_lines)
                updated_content = f"{header}\n\n{schedule_message}"
                
                # 영향받은 차수 확인
                affected_rounds = [ri.round_index for ri in round_infos if (
                    (user_name in [s[0] for s in ri.support]) or
                    (user_name in [d[0] for d in ri.dealer])
                )]
                
                # 역할 텍스트 생성
                roles_text = []
                if dealer_count > 0:
                    roles_text.append(f"딜러 {dealer_count}회")
                if support_count > 0:
                    roles_text.append(f"서포터 {support_count}회")
                role_description = " + ".join(roles_text) if roles_text else "딜러 1회"
                
                result = {
                    "status": "success",
                    "updated_content": updated_content,
                    "affected_rounds": affected_rounds,
                    "user_role": role_description,
                    "changes": f"{user_name}님이 {', '.join([str(r) + '차' for r in affected_rounds])}에 참여"
                }
                
                # 캐시에 저장
                self.save_to_cache(cache_key, result)
                return result
                
            elif command_type == "제거":
                # 제거 명령어 처리
                # 1. 명령어 파라미터 파싱
                dealer_count = 0
                support_count = 0
                round_num = None
                
                # 정규식으로 "{숫자}딜 {숫자}폿" 패턴과 차수 파싱
                dealer_match = re.search(r'(\d+)\s*딜러?', command_params) or re.search(r'(\d+)\s*딜?', command_params)
                support_match = re.search(r'(\d+)\s*서포?터?', command_params) or re.search(r'(\d+)\s*폿', command_params)
                round_match = re.search(r'(\d+)\s*차', command_params)
                
                if dealer_match:
                    dealer_count = int(dealer_match.group(1))
                
                if support_match:
                    support_count = int(support_match.group(1))
                
                if round_match:
                    round_num = int(round_match.group(1))
                
                logger.info(f"[DEBUG] 제거 요청 파싱 결과: dealer_count={dealer_count}, support_count={support_count}, round={round_num}")
                
                # 스레드 ID 가져오기
                thread_id = thread_messages[0]['author_id'] if thread_messages else "unknown"
                
                # 큐 객체 가져오기
                queue = raid_queue_manager.get_queue(thread_id)
                
                # 2. 사용자 참여 상태 확인 (메시지 파싱)
                raid_data = await self.parse_message_to_data(message_content)
                
                # 메시지에서 현재 사용자가 어떤 차수와 역할로 참여하고 있는지 확인
                user_status = []  # (round, role) 형식으로 저장
                
                for round_info in raid_data.rounds:
                    # 서포터로 참여 중인지 확인
                    for supporter in round_info.confirmed_supporters:
                        if supporter[0].lower() == user_name.lower() or (f"<@{user_id}>" in supporter[0]):
                            user_status.append((round_info.round_index, "support"))
                            logger.info(f"사용자 {user_name}가 {round_info.round_index}차에 서포터로 참여 중")
                    
                    # 딜러로 참여 중인지 확인
                    for dealer in round_info.confirmed_dealers:
                        if dealer[0].lower() == user_name.lower() or (f"<@{user_id}>" in dealer[0]):
                            user_status.append((round_info.round_index, "dealer"))
                            logger.info(f"사용자 {user_name}가 {round_info.round_index}차에 딜러로 참여 중")
                
                # 3. 역할별 제거 처리
                removed_elements = []
                
                # 3.1 딜러 제거
                dealers_removed = 0
                if dealer_count > 0:
                    logger.info(f"[DEBUG] {dealer_count}명의 딜러 제거 시도 중...")
                    
                    # 여러 형태의 사용자 식별자로 시도
                    identifiers = [user_name]
                    if user_id:
                        identifiers.append(f"<@{user_id}>")  # 멘션 형식 추가
                    
                    # 각 차수별로 시도할 차수 목록 생성
                    round_numbers = [round_num] if round_num else [None]  # None은 모든 차수에서 제거
                    
                    # 지정한 숫자만큼 딜러 제거 시도
                    attempts = 0
                    max_attempts = dealer_count * 2  # 시도 횟수 제한 (무한 루프 방지)
                    
                    while dealers_removed < dealer_count and attempts < max_attempts:
                        removed = None
                        
                        # 각 식별자와 차수 조합으로 시도
                        for identifier in identifiers:
                            for r_num in round_numbers:
                                if not removed:  # 아직 제거 안된 경우만 시도
                                    removed = raid_queue_manager.process_remove_command(
                                        thread_id, 
                                        identifier, 
                                        "dealer", 
                                        r_num
                                    )
                                    if removed:
                                        logger.info(f"[DEBUG] 딜러 제거 성공 ({dealers_removed+1}/{dealer_count}): {removed} (식별자: {identifier}, 차수: {r_num})")
                                        break
                        
                        # 제거 성공 여부에 따른 처리
                        if removed:
                            removed_elements.append(removed)
                            dealers_removed += 1
                        else:
                            # 모든 시도 실패 시 중단
                            logger.warning(f"[DEBUG] 딜러 제거 실패: 더 이상 제거할 딜러가 없음 ({dealers_removed}/{dealer_count} 완료)")
                            break
                        
                        attempts += 1
                    
                    logger.info(f"[DEBUG] 딜러 제거 완료: {dealers_removed}/{dealer_count} 성공")
                
                # 3.2 서포터 제거
                supporters_removed = 0
                if support_count > 0:
                    logger.info(f"[DEBUG] {support_count}명의 서포터 제거 시도 중...")
                    
                    # 여러 형태의 사용자 식별자로 시도
                    identifiers = [user_name]
                    if user_id:
                        identifiers.append(f"<@{user_id}>")  # 멘션 형식 추가
                    
                    # 각 차수별로 시도할 차수 목록 생성
                    round_numbers = [round_num] if round_num else [None]  # None은 모든 차수에서 제거
                    
                    # 지정한 숫자만큼 서포터 제거 시도
                    attempts = 0
                    max_attempts = support_count * 2  # 시도 횟수 제한 (무한 루프 방지)
                    
                    while supporters_removed < support_count and attempts < max_attempts:
                        removed = None
                        
                        # 각 식별자와 차수 조합으로 시도
                        for identifier in identifiers:
                            for r_num in round_numbers:
                                if not removed:  # 아직 제거 안된 경우만 시도
                                    removed = raid_queue_manager.process_remove_command(
                                        thread_id, 
                                        identifier, 
                                        "support", 
                                        r_num
                                    )
                                    if removed:
                                        logger.info(f"[DEBUG] 서포터 제거 성공 ({supporters_removed+1}/{support_count}): {removed} (식별자: {identifier}, 차수: {r_num})")
                                        break
                        
                        # 제거 성공 여부에 따른 처리
                        if removed:
                            removed_elements.append(removed)
                            supporters_removed += 1
                        else:
                            # 모든 시도 실패 시 중단
                            logger.warning(f"[DEBUG] 서포터 제거 실패: 더 이상 제거할 서포터가 없음 ({supporters_removed}/{support_count} 완료)")
                            break
                        
                        attempts += 1
                    
                    logger.info(f"[DEBUG] 서포터 제거 완료: {supporters_removed}/{support_count} 성공")
                
                # 3.3 역할 지정이 없는 경우 기본 제거 로직
                if dealer_count == 0 and support_count == 0:
                    # 차수가 지정된 경우, 해당 차수에서 제거
                    if round_num:
                        # 참여 중인 역할에 따라 제거
                        for user_round, user_role in user_status:
                            if user_round == round_num:
                                removed = raid_queue_manager.process_remove_command(
                                    thread_id, 
                                    user_name, 
                                    "dealer" if user_role == "dealer" else "support", 
                                    round_num
                                )
                                
                                # 멘션 형식으로 재시도
                                if not removed and user_id:
                                    removed = raid_queue_manager.process_remove_command(
                                        thread_id, 
                                        f"<@{user_id}>", 
                                        "dealer" if user_role == "dealer" else "support", 
                                        round_num
                                    )
                                
                                if removed:
                                    removed_elements.append(removed)
                                    if user_role == "dealer":
                                        dealers_removed += 1
                                    else:
                                        supporters_removed += 1
                                    logger.info(f"[DEBUG] {user_role} 제거 성공 (차수 {round_num}): {removed}")
                                    break
                    else:
                        # 차수 지정이 없는 경우, 모든 역할 시도
                        for role in ["dealer", "support"]:
                            removed = raid_queue_manager.process_remove_command(
                                thread_id, 
                                user_name, 
                                role, 
                                None
                            )
                            
                            # 멘션 형식으로 재시도
                            if not removed and user_id:
                                removed = raid_queue_manager.process_remove_command(
                                    thread_id, 
                                    f"<@{user_id}>", 
                                    role, 
                                    None
                                )
                            
                            if removed:
                                removed_elements.append(removed)
                                if role == "dealer":
                                    dealers_removed += 1
                                else:
                                    supporters_removed += 1
                                logger.info(f"[DEBUG] {role} 제거 성공: {removed}")
                                break
                
                # 4. 제거 결과 처리
                if removed_elements:
                    # 4.1 메시지에서 "없음" 텍스트가 있는지 확인하고 제거
                    message_content = message_content.replace("없음", "")
                    
                    # 4.2 큐에서 일정 메시지 생성
                    schedule_message, round_infos = queue.generate_schedule_message()
                    
                    # 4.3 원본 헤더 정보 유지
                    header_lines = []
                    for line in message_content.split("\n"):
                        if line.strip() and not re.match(r'^\d+차', line) and "서포터" not in line and "딜러" not in line:
                            header_lines.append(line)
                        else:
                            break
                    
                    header = "\n".join(header_lines)
                    updated_content = f"{header}\n\n{schedule_message}"
                    
                    # 4.4 제거된 역할 및 차수 정보 집계
                    dealer_removed = len([elem for elem in removed_elements if elem.role.lower() == "dealer"])
                    support_removed = len([elem for elem in removed_elements if elem.role.lower() == "support"])
                    affected_rounds = list(set([elem.round for elem in removed_elements if elem.round > 0]))
                    
                    # 기본 차수 (메시지에서 파싱된 차수)
                    if not affected_rounds and round_num:
                        affected_rounds = [round_num]
                    
                    # 4.5 역할 텍스트 생성
                    roles_text = []
                    if dealer_removed > 0:
                        roles_text.append(f"딜러 {dealer_removed}회")
                    if support_removed > 0:
                        roles_text.append(f"서포터 {support_removed}회")
                    role_description = " + ".join(roles_text) if roles_text else "참여"
                    
                    result = {
                        "status": "success",
                        "updated_content": updated_content,
                        "affected_rounds": affected_rounds,
                        "user_role": role_description,
                        "changes": f"{user_name}님의 {role_description} 참여가 제거됨"
                    }
                    
                    # 캐시에 저장
                    self.save_to_cache(cache_key, result)
                    return result
                else:
                    # 4.6 제거 실패 처리
                    # 메시지에서 멘션 형태로 사용자 검색
                    mention_pattern = f"<@{user_id}>"
                    if mention_pattern in message_content:
                        logger.info(f"메시지에서 멘션 형태 발견: {mention_pattern}, 다시 시도합니다")
                        
                        # 멘션 형태로 다시 시도 (지정된 차수와 역할 사용)
                        role_to_try = "support" if support_count > 0 else ("dealer" if dealer_count > 0 else None)
                        
                        removed = raid_queue_manager.process_remove_command(
                            thread_id, 
                            mention_pattern, 
                            role_to_try, 
                            round_num
                        )
                        
                        if removed:
                            # 제거 성공 시 결과 처리 (큐 업데이트 및 메시지 생성)
                            message_content = message_content.replace("없음", "")
                            schedule_message, round_infos = queue.generate_schedule_message()
                            
                            header_lines = []
                            for line in message_content.split("\n"):
                                if line.strip() and not re.match(r'^\d+차', line) and "서포터" not in line and "딜러" not in line:
                                    header_lines.append(line)
                                else:
                                    break
                            
                            header = "\n".join(header_lines)
                            updated_content = f"{header}\n\n{schedule_message}"
                            
                            role_text = "서포터" if removed.role.lower() == "support" else "딜러"
                            
                            result = {
                                "status": "success",
                                "updated_content": updated_content,
                                "affected_rounds": [removed.round] if removed.round > 0 else (
                                    [round_num] if round_num else []
                                ),
                                "user_role": role_text,
                                "changes": f"{user_name}님의 {role_text} 참여가 제거됨"
                            }
                            
                            # 캐시에 저장
                            self.save_to_cache(cache_key, result)
                            return result
                    
                    # 제거 실패
                    return {
                        "status": "error",
                        "error": f"{user_name}님의 참여 정보를 찾을 수 없습니다. (역할: {'서포터' if support_count > 0 else '딜러' if dealer_count > 0 else '미지정'}, 차수: {round_num if round_num else '모든 차수'})"
                    }
            else:
                # 수정 명령어는 기존 방식으로 처리
                # 프롬프트 구성
                messages = [
                    {"role": "system", "content": """너는 레이드 참여 일정을 관리해주는 전문 비서야. 
사용자들이 명령어를 통해 레이드 일정에 참여 의사를 밝히면, 그에 맞게 일정표를 업데이트해줘야 해.
최대한 간결하게 응답하고, 정확한 결과만 보여줘."""},
                    {"role": "user", "content": f"""
현재 레이드 일정 메시지:
```
{message_content}
```

최근 스레드 대화:
```
{json.dumps(thread_messages, ensure_ascii=False, indent=2)}
```

명령어: {command_type} {command_params}
명령을 내린 사용자: {user_name} ({user_mention})

위 정보를 바탕으로 레이드 일정을 적절히 수정해줘. 
레이드 일정 파싱 규칙:
1. '차수'로 구분 (1차, 2차 등)
2. 각 차수 내부:
   - when: 일시
   - 서포터(n/2): 서포터 목록
   - 딜러(n/6): 딜러 목록
   - note: 기타 참고사항

응답 형식:
```json
{
  "status": "success",
  "updated_content": "수정된 전체 메시지 내용",
  "affected_rounds": [영향 받은 차수 번호들],
  "user_role": "사용자 역할(서포터 또는 딜러)",
  "changes": "간략한 변경 내용 설명"
}
```

어떤 오류가 있으면:
```json
{
  "status": "error",
  "error": "오류 메시지"
}
```"""}
                ]
                
                # LLM 호출
                llm_response = await self.call_openai_api(
                    messages=messages,
                    model="gpt-4-0125-preview",
                    temperature=0.1,
                    response_format={"type": "json_object"}
                )
                
                if llm_response and "content" in llm_response:
                    try:
                        result = json.loads(llm_response["content"])
                        # 캐시에 저장
                        self.save_to_cache(cache_key, result)
                        return result
                    except json.JSONDecodeError:
                        logger.error(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {llm_response['content']}")
                        return {"status": "error", "error": "응답 분석 중 오류가 발생했습니다."}
                else:
                    logger.error("LLM 응답이 올바르지 않습니다.")
                    return {"status": "error", "error": "AI 응답이 올바르지 않습니다."}
                    
        except Exception as e:
            logger.error(f"일정 분석 중 오류: {e}")
            return {"status": "error", "error": f"처리 중 오류가 발생했습니다: {str(e)}"}

    def validate_and_fix_schedule(self, result):
        """
        LLM 출력을 기반으로 일정 유효성 검사 및 수정
        
        Args:
            result (dict): LLM의 응답 결과
            
        Returns:
            dict: 유효성 검사 및 수정이 적용된 결과
        """
        # 에러 상태인 경우 그대로 반환
        if result.get("status") == "error":
            return result
            
        # updated_content가 없으면 처리 불가
        if "updated_content" not in result:
            result["status"] = "error"
            result["error"] = "일정 내용이 없습니다."
            return result
            
        # 원본 내용 복사 (디버깅 및 비교용)
        original_content = result["updated_content"]
        logger.info("일정 유효성 검사 및 수정 시작")
        
        # 메시지를 줄 단위로 분리
        lines = original_content.split("\n")
        
        # 차수 정보 추출
        rounds = []
        current_round = None
        
        # 일정 메시지 파싱하여 차수 정보 추출
        for i, line in enumerate(lines):
            # 차수 시작 패턴 (숫자+차 패턴)
            round_match = re.match(r'(\d+)차', line.strip())
            if round_match:
                # 새로운 차수 시작
                if current_round:
                    rounds.append(current_round)
                
                round_num = int(round_match.group(1))
                current_round = {
                    "number": round_num,
                    "start_line": i,
                    "supporters": [],
                    "dealers": [],
                    "when": "",
                    "who": "",
                    "note": "",
                    "supporter_count": 0,
                    "dealer_count": 0
                }
            elif current_round is not None:
                # 현재 차수의 정보 파싱
                if "서포터" in line and "(" in line and ")" in line:
                    # 서포터 정보 (예: 서포터(1/2): 사용자1)
                    support_line = line.split(":", 1)
                    if len(support_line) > 1:
                        count_match = re.search(r'\((\d+)/\d+\)', support_line[0])
                        if count_match:
                            current_round["supporter_count"] = int(count_match.group(1))
                        
                        if support_line[1].strip() and support_line[1].strip() != "없음":
                            supporters = [s.strip() for s in support_line[1].strip().split(",")]
                            current_round["supporters"] = supporters
                            # 실제 서포터 수를 기준으로 카운트 재설정
                            current_round["supporter_count"] = len(supporters)
                        else:
                            current_round["supporters"] = []
                            current_round["supporter_count"] = 0
                elif "딜러" in line and "(" in line and ")" in line:
                    # 딜러 정보 (예: 딜러(3/6): 사용자1, 사용자2, 사용자3)
                    dealer_line = line.split(":", 1)
                    if len(dealer_line) > 1:
                        count_match = re.search(r'\((\d+)/\d+\)', dealer_line[0])
                        if count_match:
                            current_round["dealer_count"] = int(count_match.group(1))
                        
                        if dealer_line[1].strip() and dealer_line[1].strip() != "없음":
                            dealers = [d.strip() for d in dealer_line[1].strip().split(",")]
                            current_round["dealers"] = dealers
                            # 실제 딜러 수를 기준으로 카운트 재설정
                            current_round["dealer_count"] = len(dealers)
                        else:
                            current_round["dealers"] = []
                            current_round["dealer_count"] = 0
                elif line.startswith("when:"):
                    current_round["when"] = line[5:].strip()
                elif line.startswith("who:"):
                    current_round["who"] = line[4:].strip()
                elif line.startswith("note:"):
                    current_round["note"] = line[5:].strip()
        
        # 마지막 차수 추가
        if current_round:
            rounds.append(current_round)
        
        # 디버깅 정보
        logger.info(f"총 {len(rounds)}개 차수 정보 추출 완료")
        
        if not rounds:
            # 차수 정보가 없으면 원본 그대로 반환
            logger.warning("차수 정보를 추출할 수 없습니다")
            return result
        
        # 1. 각 차수별 인원 조정 (서포터 최대 2명, 딜러 최대 6명)
        # 2. 중복 참가자 다음 차수로 이동
        
        # 사용자별 참여 차수 추적
        user_rounds = {}
        
        # 초과 인원 보관
        overflow_supporters = []
        overflow_dealers = []
        
        # 차수별 수정
        modified_rounds = []
        
        for r_idx, round_info in enumerate(rounds):
            # 현재 차수의 참가자 목록
            modified_supporters = []
            modified_dealers = []
            
            # 서포터 처리 (기존 서포터 + 이전 차수 초과분)
            for supporter in round_info["supporters"] + overflow_supporters:
                if supporter and supporter not in user_rounds:
                    # 새 참가자 추가
                    modified_supporters.append(supporter)
                    user_rounds[supporter] = round_info["number"]
                elif supporter and user_rounds.get(supporter) != round_info["number"]:
                    # 다른 차수에 이미 참가 중이면 추가
                    modified_supporters.append(supporter)
                    user_rounds[supporter] = round_info["number"]
                else:
                    # 같은 차수에 이미 참가 중이면 건너뜀
                    logger.info(f"사용자 {supporter}는 이미 {round_info['number']}차에 참가 중. 건너뜀")
            
            # 서포터 정원 초과 확인
            if len(modified_supporters) > 2:
                overflow_supporters = modified_supporters[2:]
                modified_supporters = modified_supporters[:2]
                logger.info(f"{round_info['number']}차 서포터 정원 초과: {len(overflow_supporters)}명 다음 차수로 이동")
            else:
                overflow_supporters = []
            
            # 딜러 처리 (기존 딜러 + 이전 차수 초과분)
            for dealer in round_info["dealers"] + overflow_dealers:
                if dealer and dealer not in user_rounds:
                    # 새 참가자 추가
                    modified_dealers.append(dealer)
                    user_rounds[dealer] = round_info["number"]
                elif dealer and user_rounds.get(dealer) != round_info["number"]:
                    # 다른 차수에 이미 참가 중이면 추가
                    modified_dealers.append(dealer)
                    user_rounds[dealer] = round_info["number"]
                else:
                    # 같은 차수에 이미 참가 중이면 건너뜀
                    logger.info(f"사용자 {dealer}는 이미 {round_info['number']}차에 참가 중. 건너뜀")
            
            # 딜러 정원 초과 확인
            if len(modified_dealers) > 6:
                overflow_dealers = modified_dealers[6:]
                modified_dealers = modified_dealers[:6]
                logger.info(f"{round_info['number']}차 딜러 정원 초과: {len(overflow_dealers)}명 다음 차수로 이동")
            else:
                overflow_dealers = []
            
            # 수정된 차수 정보 저장
            round_info["supporters"] = modified_supporters
            round_info["dealers"] = modified_dealers
            round_info["supporter_count"] = len(modified_supporters)
            round_info["dealer_count"] = len(modified_dealers)
            
            # 차수에 참가자가 있는 경우만 추가
            if modified_supporters or modified_dealers:
                modified_rounds.append(round_info)
        
        # 초과 인원 처리 (마지막 차수 이후)
        extra_round_number = modified_rounds[-1]["number"] + 1 if modified_rounds else 1
        
        while overflow_supporters or overflow_dealers:
            extra_round = {
                "number": extra_round_number,
                "start_line": -1,  # 새 차수는 라인 정보 없음
                "supporters": overflow_supporters[:2],  # 최대 2명
                "dealers": overflow_dealers[:6],  # 최대 6명
                "when": "",
                "who": "",
                "note": "",
                "supporter_count": min(len(overflow_supporters), 2),
                "dealer_count": min(len(overflow_dealers), 6)
            }
            
            # 초과 인원 업데이트
            overflow_supporters = overflow_supporters[2:] if len(overflow_supporters) > 2 else []
            overflow_dealers = overflow_dealers[6:] if len(overflow_dealers) > 6 else []
            
            modified_rounds.append(extra_round)
            extra_round_number += 1
            
            logger.info(f"초과 인원을 위한 {extra_round['number']}차 생성: 서포터 {extra_round['supporter_count']}명, 딜러 {extra_round['dealer_count']}명")
        
        # 라인별로 메시지 재구성
        new_lines = []
        
        # 헤더 부분 (첫 번째 차수 시작 전)
        if rounds[0]["start_line"] > 0:
            new_lines.extend(lines[:rounds[0]["start_line"]])
        
        # 각 차수 정보 추가
        for r_idx, round_info in enumerate(modified_rounds):
            # 차수 번호
            new_lines.append(f"{round_info['number']}차")
            
            # 기존 정보 유지
            new_lines.append(f"when:{round_info['when']}")
            
            # who 필드는 사용하지 않는 경우도 있어 조건부로 추가
            if 'who' in round_info:
                new_lines.append(f"who:{round_info['who']}")
            
            # 서포터 정보
            supporters_str = ""
            if round_info["supporters"]:
                supporters_str = ", ".join(round_info["supporters"])
                new_lines.append(f"서포터({round_info['supporter_count']}/2): {supporters_str}")
            else:
                new_lines.append(f"서포터(0/2):")
            
            # 딜러 정보
            dealers_str = ""
            if round_info["dealers"]:
                dealers_str = ", ".join(round_info["dealers"])
                new_lines.append(f"딜러({round_info['dealer_count']}/6): {dealers_str}")
            else:
                new_lines.append(f"딜러(0/6):")
            
            # 메모
            new_lines.append(f"note:{round_info['note']}")
            
            # 차수 구분선 (마지막 차수가 아닌 경우)
            if r_idx < len(modified_rounds) - 1:
                new_lines.append("")
        
        # 수정된 내용
        updated_content = "\n".join(new_lines)
        
        # 변경사항 요약
        changes_summary = f"일정 자동 조정: {len(rounds)}개 차수 → {len(modified_rounds)}개 차수"
        
        # 수정된 내용으로 결과 업데이트
        if original_content != updated_content:
            result["updated_content"] = updated_content
            
            # 원래 변경 내용에 자동 조정 정보 추가
            original_changes = result.get("changes", "")
            result["changes"] = f"{original_changes} [{changes_summary}]" if original_changes else changes_summary
            
            # 영향받은 차수 목록 업데이트
            result["affected_rounds"] = [r["number"] for r in modified_rounds]
            
            logger.info(f"일정 자동 조정 완료: {changes_summary}")
        
        return result

async def setup(bot):
    """확장 설정"""
    await bot.add_cog(ThreadCommands(bot)) 