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

class ThreadCommands(commands.Cog):
    """스레드 내 일정 관리 명령어"""
    
    def __init__(self, bot):
        self.bot = bot
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
                        await starter_message.edit(content=updated_content)
                        logger.info("메시지 업데이트 성공")
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
                    
                except discord.Forbidden as e:
                    logger.error(f"메시지 수정 권한 없음: {e}")
                    await processing_msg.edit(content="메시지 수정 권한이 없습니다.")
                except discord.HTTPException as e:
                    logger.error(f"메시지 업데이트 HTTP 오류: {e}")
                    await processing_msg.edit(content=f"메시지 업데이트 중 오류: {e}")
            else:
                logger.warning("updated_content 필드가 없습니다")
                await processing_msg.edit(content="일정 업데이트에 필요한 정보가 충분하지 않습니다.")
                
        except Exception as e:
            logger.error(f"처리 중 예외 발생: {e}", exc_info=True)
            await processing_msg.edit(content=f"처리 중 오류가 발생했습니다: {e}")
    
    def get_cache_key(self, thread_messages, message_content, command_type, user_name, user_id, command_message):
        """캐시 키 생성"""
        # 입력 데이터를 문자열로 직렬화
        data_str = json.dumps({
            'thread_messages': thread_messages,
            'message_content': message_content,
            'command_type': command_type,
            'user_name': user_name,
            'user_id': user_id,
            'command_message': command_message
        }, sort_keys=True, ensure_ascii=False)
        
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
        """OpenAI API를 사용하여 일정 정보 분석"""
        if not self.openai_api_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다."}
        
        # 캐시 키 생성
        cache_key = self.get_cache_key(thread_messages, message_content, command_type, user_name, user_id, command_params)
        
        # 캐시 확인
        cached_result = self.get_cached_result(cache_key)
        if cached_result:
            return cached_result
        
        # 메시지 포맷팅
        formatted_messages = []
        for msg in thread_messages:
            formatted_messages.append(f"{msg['author']} ({msg['created_at']}): {msg['content']}")
        
        messages_text = "\n".join(formatted_messages)
        
        # 분석하려는 대상 스레드의 레이드 이름 추출 시도
        raid_name = "레이드"
        if "\n" in message_content:
            first_line = message_content.split("\n")[0]
            raid_name = first_line.strip()
        
        # 명령어 파라미터 분석
        role_type = "알 수 없음"
        
        # 딜러/서포터 역할이 반복되는지 확인
        dps_matches = list(re.finditer(r'(\d+)\s*딜(?:러)?', command_params.lower()))
        supp_matches = list(re.finditer(r'(\d+)\s*(?:폿|서폿|서포터)', command_params.lower()))
        
        # 명령 유형 분석: '차수 지정' vs '인원 지정'
        # - 같은 역할이 반복(예: "1딜 2딜")되면 차수 지정으로 해석
        # - 다른 역할이 함께 있으면(예: "1폿 3딜") 인원수로 해석
        
        is_round_specification = False  # 기본값은 인원 지정 모드
        round_role_map = []  # 기본 빈 리스트로 초기화
        
        if len(dps_matches) > 1 and len(supp_matches) == 0:
            # 딜러 역할만 여러 번 반복됨 -> 차수 지정
            is_round_specification = True
            logger.info("차수 지정 모드 감지: 여러 차수의 딜러 지정 (예: 1딜 2딜)")
        elif len(supp_matches) > 1 and len(dps_matches) == 0:
            # 서포터 역할만 여러 번 반복됨 -> 차수 지정
            is_round_specification = True
            logger.info("차수 지정 모드 감지: 여러 차수의 서포터 지정 (예: 1폿 2폿)")
        else:
            # 역할이 섞여 있거나 각각 하나씩만 있음 -> 인원 지정
            logger.info("인원 지정 모드 감지 (예: 1폿 3딜)")
        
        # 처리 모드에 따라 필요한 정보 준비
        if is_round_specification:
            # 차수 지정 모드: 각 차수별 역할 매핑 준비
            # round_role_map = [] -- 위로 이동됨
            
            # 딜러 차수 매핑
            for match in dps_matches:
                round_num = int(match.group(1))
                round_role_map.append({"round": round_num, "role": "딜러"})
                logger.info(f"{round_num}차에 딜러 역할 지정")
            
            # 서포터 차수 매핑
            for match in supp_matches:
                round_num = int(match.group(1))
                round_role_map.append({"round": round_num, "role": "서포터"})
                logger.info(f"{round_num}차에 서포터 역할 지정")
            
            # 정렬: 차수 번호 기준
            round_role_map.sort(key=lambda x: x["round"])
            
            # 기본 역할 (첫 번째 지정된 역할)
            if round_role_map:
                role_type = round_role_map[0]["role"]
            
            dps_count = 0
            support_count = 0
            total_rounds_needed = 0
        else:
            # 인원 지정 모드: 딜러/서포터 인원수 계산
            dps_count = 0
            support_count = 0
            
            # "X딜"에서 X는 인원 수를 의미함
            if dps_matches:
                dps_count = int(dps_matches[0].group(1))
                logger.info(f"딜러 {dps_count}명 감지")
                role_type = "딜러"
            
            # "X폿"에서 X는 인원 수를 의미함
            if supp_matches:
                support_count = int(supp_matches[0].group(1))
                logger.info(f"서포터 {support_count}명 감지")
                if not role_type or role_type == "알 수 없음":
                    role_type = "서포터"
            
            # 역할 키워드만 있는 경우 (숫자 없이)
            if dps_count == 0 and "딜" in command_params.lower():
                dps_count = 1
                logger.info("숫자 없는 딜러 감지, 기본값 1명 설정")
                role_type = "딜러"
                
            if support_count == 0 and ("폿" in command_params.lower() or "서폿" in command_params.lower() or "서포터" in command_params.lower()):
                support_count = 1
                logger.info("숫자 없는 서포터 감지, 기본값 1명 설정")
                if not role_type or role_type == "알 수 없음":
                    role_type = "서포터"
            
            # 총 필요한 차수 계산
            total_rounds_needed = dps_count + support_count
            logger.info(f"총 필요 차수: {total_rounds_needed} (딜러: {dps_count}명, 서포터: {support_count}명)")
        
        # 차수 지정 확인 (차수를 명시적으로 지정한 경우 해당 차수에만 추가)
        target_round = None
        round_match = re.search(r'(\d+)\s*차', command_params)
        if round_match:
            target_round = int(round_match.group(1))
            logger.info(f"특정 차수 지정됨: {target_round}차")
        
        # 출력 JSON 구조 정의
        output_schema = {
            "type": "object",
            "required": ["updated_content", "changes", "status", "action"],
            "properties": {
                "updated_content": {"type": "string", "description": "업데이트된 메시지 내용"},
                "changes": {"type": "string", "description": "변경된 내용 요약"},
                "status": {"type": "string", "enum": ["success", "error"], "description": "성공/실패 여부"},
                "action": {"type": "string", "enum": ["add", "remove", "update"], "description": "수행된 작업 유형"},
                "error": {"type": "string", "description": "오류 메시지 (오류 발생시)"},
                "affected_rounds": {
                    "type": "array", 
                    "items": {"type": "integer"}, 
                    "description": "영향받은 차수 목록"
                },
                "user_role": {"type": "string", "description": "사용자 역할 (딜러/서포터)"}
            }
        }
        
        # OpenAI에 보낼 프롬프트
        prompt = f"""
{user_name}(ID: {user_id})님이 '{raid_name}' 레이드 스레드에서 일정 {command_type} 명령어를 사용했습니다.

## 원본 일정 메시지:
{message_content}

## 스레드 대화 내용:
{messages_text}

## 명령어 파라미터:
{command_params}

## 명령 해석 모드:
{'차수 지정 모드' if is_round_specification else '인원 지정 모드'}

## 사용자 정보:
- 사용자 이름: {user_name}
- 사용자 ID: {user_id}
- 멘션 태그: {user_mention}
- 기본 역할 유형: {role_type}
- 특정 차수 지정: {target_round if target_round else "없음"}

"""

        if is_round_specification:
            # 차수 지정 모드 프롬프트
            round_info = "\n".join([f"- {item['round']}차: {item['role']}" for item in round_role_map])
            prompt += f"""
## 차수별 역할 지정:
{round_info}

## 명령어 해석 방법:
"1딜 2딜"과 같은 명령어에서 숫자는 차수를 의미합니다:
- "1딜"은 1차에 딜러로 참가
- "2딜"은 2차에 딜러로 참가
- "3폿"은 3차에 서포터로 참가

## 중요 지침:
1. 사용자는 한 차수에 최대 1회만 등록 가능합니다(중복 금지).
2. 위에 명시된 차수와 역할에 맞게 정확히 사용자를 등록하세요.
3. 각 차수별로 서포터는 최대 2명, 딜러는 최대 6명으로 제한됩니다.

## 작업 방법:
1. 일정 추가(추가):
   a. 명시된 각 차수에 정해진 역할로 사용자를 추가합니다.
   b. "1딜 2딜 3폿"인 경우:
      - 1차에 딜러로 추가
      - 2차에 딜러로 추가
      - 3차에 서포터로 추가
   c. 필요한 차수가 없으면 새로운 차수를 생성합니다.
"""
        else:
            # 인원 지정 모드 프롬프트
            prompt += f"""
## 요청 분석:
- 딜러 참가 횟수: {dps_count}회
- 서포터 참가 횟수: {support_count}회
- 총 필요 차수: {total_rounds_needed}회

## 명령어 해석 방법:
"1폿 3딜"과 같은 명령어에서 숫자는 해당 역할로 참가할 횟수(인원수)를 의미합니다:
- "1폿"은 1회 서포터로 참가
- "3딜"은 3회 딜러로 참가
즉, 이 사용자는 총 4개 차수에 참가하게 됩니다.

## 중요 지침:
1. 사용자는 한 차수에 최대 1회만 등록 가능합니다(중복 금지).
2. 여러 역할과 횟수가 지정된 경우(예: "1폿 3딜"), 서포터 역할을 먼저 낮은 차수에 배치하고, 나머지 차수에 딜러 역할을 배치합니다.
3. 특정 차수가 명시적으로 지정된 경우(예: "2차 딜러"), 해당 차수에만 추가하고 나머지는 무시합니다.
4. 각 차수별로 서포터는 최대 2명, 딜러는 최대 6명으로 제한됩니다.

## 작업 방법:
1. 일정 추가(추가):
   a. 사용자의 요청에 따라 적절한 차수와 역할에 추가합니다.
   b. "1폿 3딜"인 경우:
      - 첫 번째 가능한 차수에 서포터로 1회 추가
      - 다음 세 개의 가능한 차수에 딜러로 각각 1회씩 추가
   c. 필요한 차수가 없으면 새로운 차수를 생성합니다.
   d. 이미 등록된 차수가 있으면 해당 차수는 건너뛰고 다음 차수에 추가합니다.
"""

        # 공통 프롬프트 부분
        prompt += f"""
2. 일정 제거(제거):
   - 모든 차수에서 사용자의 참가 정보를 제거합니다.
   - 특정 차수만 지정된 경우, 해당 차수에서만 제거합니다.

3. 일정 수정(수정):
   - 요청된 변경사항에 따라 일정 정보를 업데이트합니다.

{user_name}님의 의도를 파악하여 원본 일정 메시지를 {command_type}해주세요.
원본 메시지의 형식을 최대한 유지하면서 일정 정보만 업데이트해주세요.
각 차수마다 서포터(0/2), 딜러(0/6) 형식의 카운트를 반드시 정확하게 업데이트해야 합니다.

다음 JSON 형식으로 응답해주세요:
```json
{{
  "updated_content": "업데이트된 메시지 내용",
  "changes": "어떤 변경이 이루어졌는지 요약",
  "status": "success 또는 error",
  "action": "{command_type}",
  "affected_rounds": [영향받은 차수 번호들],
  "user_role": "사용자 역할 (딜러 또는 서포터)"
}}
```

만약 오류가 발생한 경우:
```json
{{
  "status": "error",
  "error": "오류 메시지",
  "action": "{command_type}"
}}
```
"""
        
        # API 요청
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_api_key}"
                    },
                    json={
                        "model": "gpt-4-0125-preview",
                        "messages": [
                            {"role": "system", "content": f"당신은 디스코드 봇의 레이드 일정 관리 기능을 돕는 AI 비서입니다. {'차수 지정 모드에서는 각 숫자는 차수를 의미합니다(예: 1딜 2딜은 1차와 2차에 딜러로 참가)' if is_round_specification else '인원 지정 모드에서는 숫자는 해당 역할로 참가할 횟수를 의미합니다(예: 1폿 3딜은 서포터 1회, 딜러 3회 참가)'} 사용자는 각 차수마다 최대 1번만 참여 가능합니다."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.1,
                        "response_format": {"type": "json_object"}
                    }
                ) as response:
                    response_data = await response.json()
                    
                    if "error" in response_data:
                        return {"error": f"OpenAI API 오류: {response_data['error']}", "status": "error", "action": command_type}
                    
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        content = response_data["choices"][0]["message"]["content"]
                        try:
                            result = json.loads(content)
                            
                            # 응답 검증: 필수 필드가 있는지 확인
                            if "status" not in result:
                                result["status"] = "success"  # 기본값
                            
                            if "action" not in result:
                                result["action"] = command_type
                                
                            if result["status"] == "error" and "error" not in result:
                                result["error"] = "알 수 없는 오류가 발생했습니다."
                                
                            if result["status"] == "success" and ("updated_content" not in result or "changes" not in result):
                                result["status"] = "error"
                                result["error"] = "LLM 응답에 필수 필드가 누락되었습니다."
                            
                            self.save_to_cache(cache_key, result)
                            return result
                        except json.JSONDecodeError:
                            return {
                                "status": "error", 
                                "error": "LLM 응답을 JSON으로 파싱할 수 없습니다.", 
                                "action": command_type
                            }
                    else:
                        return {
                            "status": "error", 
                            "error": "LLM 응답에서 데이터를 찾을 수 없습니다.", 
                            "action": command_type
                        }
        except Exception as e:
            return {
                "status": "error", 
                "error": f"OpenAI API 요청 중 오류: {e}", 
                "action": command_type
            }

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
                        
                        if support_line[1].strip():
                            supporters = [s.strip() for s in support_line[1].strip().split(",")]
                            current_round["supporters"] = supporters
                elif "딜러" in line and "(" in line and ")" in line:
                    # 딜러 정보 (예: 딜러(3/6): 사용자1, 사용자2, 사용자3)
                    dealer_line = line.split(":", 1)
                    if len(dealer_line) > 1:
                        count_match = re.search(r'\((\d+)/\d+\)', dealer_line[0])
                        if count_match:
                            current_round["dealer_count"] = int(count_match.group(1))
                        
                        if dealer_line[1].strip():
                            dealers = [d.strip() for d in dealer_line[1].strip().split(",")]
                            current_round["dealers"] = dealers
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
            new_lines.append(f"who:{round_info['who']}")
            
            # 서포터 정보
            supporters_str = ", ".join(round_info["supporters"]) if round_info["supporters"] else ""
            new_lines.append(f"서포터({round_info['supporter_count']}/2):{supporters_str}")
            
            # 딜러 정보
            dealers_str = ", ".join(round_info["dealers"]) if round_info["dealers"] else ""
            new_lines.append(f"딜러({round_info['dealer_count']}/6):{dealers_str}")
            
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