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
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

# 로깅 설정
logger = logging.getLogger('raid_scheduler')
logger.setLevel(logging.INFO)

# 표준 출력으로 로그 보내기
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# 데이터 클래스 정의
@dataclass
class Character:
    name: str
    role: str  # "서포터" 또는 "딜러"

@dataclass
class UserPreference:
    user_id: str
    user_name: str
    characters: List[Character] = field(default_factory=list)
    # 특정 차수에 특정 캐릭터로 참가하고 싶은 명시적 요청
    explicit_requests: Dict[str, List[Character]] = field(default_factory=dict)  # round_name -> 캐릭터 목록
    # 우선순위: 명시적 요청이 없는 경우 사용
    priority: int = 0  # 캐릭터 수에 기반한 우선순위

@dataclass
class RoundInfo:
    name: str
    when: str = ""
    note: str = ""
    supporter_max: int = 2
    dealer_max: int = 6
    # 참가가 확정된 사용자들
    confirmed_supporters: List[Tuple[str, str]] = field(default_factory=list)  # (user_name, character_name)
    confirmed_dealers: List[Tuple[str, str]] = field(default_factory=list)  # (user_name, character_name)

@dataclass
class RaidData:
    header: str
    info: List[str] = field(default_factory=list)
    rounds: List[RoundInfo] = field(default_factory=list)
    # 사용자 선호도 및 참가 요청
    user_preferences: Dict[str, UserPreference] = field(default_factory=dict)  # user_name -> UserPreference

class RaidSchedulerBase:
    """레이드 일정 관리를 위한 기본 클래스"""
    
    def __init__(self, bot):
        self.bot = bot
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        # 캐시 디렉토리 설정
        self.cache_dir = pathlib.Path('/tmp/discord_bot_llm_cache')
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"{self.__class__.__name__} 초기화 완료")
    
    # 캐시 관련 메서드
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
                logger.info(f"캐시에서 결과를 로드했습니다: {cache_key}")
                return cached_data
            except Exception as e:
                logger.error(f"캐시 로드 중 오류 발생: {e}")
        return None
    
    def save_to_cache(self, cache_key, result):
        """결과를 캐시에 저장"""
        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"결과를 캐시에 저장했습니다: {cache_key}")
        except Exception as e:
            logger.error(f"캐시 저장 중 오류 발생: {e}")
    
    def cleanup_cache(self):
        """오래된 캐시 파일 정리"""
        current_time = datetime.datetime.now()
        cache_stats = {"total": 0, "deleted": 0, "kept": 0, "errors": 0}
        
        for cache_file in self.cache_dir.glob("*.json"):
            cache_stats["total"] += 1
            try:
                # 파일 수정 시간 확인
                mod_time = datetime.datetime.fromtimestamp(os.path.getmtime(cache_file))
                file_age = current_time - mod_time
                
                # 24시간 이상 지난 파일 삭제
                if file_age.total_seconds() > 24 * 60 * 60:
                    os.remove(cache_file)
                    cache_stats["deleted"] += 1
                else:
                    cache_stats["kept"] += 1
            except Exception as e:
                logger.error(f"캐시 파일 정리 중 오류: {e}")
                cache_stats["errors"] += 1
        
        return cache_stats
    
    async def is_empty_round(self, round_info):
        """차수가 빈 상태인지 확인 (참가자 없음)"""
        # 참가자가 없어도 일정이 지정되어 있으면 빈 차수로 간주하지 않음
        has_participants = (len(round_info.confirmed_supporters) > 0 or 
                          len(round_info.confirmed_dealers) > 0)
        
        # 일정이 있거나 노트가 있으면 빈 차수가 아님
        has_information = bool(round_info.when.strip() or round_info.note.strip())
        
        return not (has_participants or has_information)

    async def clean_empty_rounds(self, raid_data):
        """빈 차수 제거"""
        before_count = len(raid_data.rounds)
        raid_data.rounds = [r for r in raid_data.rounds if not await self.is_empty_round(r)]
        removed_count = before_count - len(raid_data.rounds)
        if removed_count > 0:
            logger.info(f"{removed_count}개의 빈 차수가 제거되었습니다")
        return removed_count

    async def apply_changes_to_data(self, raid_data, changes_data):
        """변경 사항을 데이터에 적용"""
        changes_applied = []
        
        if not isinstance(changes_data, list):
            logger.error("변경 데이터가 리스트 형식이 아닙니다")
            return changes_applied
        
        for change in changes_data:
            try:
                change_type = change.get("type")
                
                if change_type == "add_participant":
                    # 참가자 추가
                    user_name = change.get("user_name", "")
                    round_name = change.get("round_name", "")
                    role = change.get("role", "")
                    
                    if not all([user_name, round_name, role]):
                        logger.warning(f"참가자 추가 정보 부족: {change}")
                        continue
                    
                    # 대상 차수 찾기
                    target_round = None
                    for r in raid_data.rounds:
                        if r.name == round_name:
                            target_round = r
                            break
                    
                    # 차수가 없으면 새로 생성
                    if not target_round:
                        # 차수 번호 추출
                        round_num = self.get_round_number(round_name)
                        if round_num > 0:
                            target_round = RoundInfo(name=round_name)
                            
                            # 올바른 위치에 삽입 (차수 번호 순)
                            insert_idx = 0
                            for i, r in enumerate(raid_data.rounds):
                                r_num = self.get_round_number(r.name)
                                if r_num > round_num:
                                    insert_idx = i
                                    break
                                insert_idx = i + 1
                            
                            raid_data.rounds.insert(insert_idx, target_round)
                    
                    if target_round:
                        # 역할에 따라 참가자 추가
                        if role.lower() in ["서포터", "서폿", "support", "supporter"]:
                            # 이미 참가 중인지 확인
                            if not any(s[0] == user_name for s in target_round.confirmed_supporters):
                                target_round.confirmed_supporters.append((user_name, ""))
                                changes_applied.append(f"{user_name}님이 {round_name}의 서포터로 추가됨")
                        
                        elif role.lower() in ["딜러", "딜", "dps", "dealer", "damage"]:
                            # 이미 참가 중인지 확인
                            if not any(d[0] == user_name for d in target_round.confirmed_dealers):
                                target_round.confirmed_dealers.append((user_name, ""))
                                changes_applied.append(f"{user_name}님이 {round_name}의 딜러로 추가됨")
                
                elif change_type == "remove_participant":
                    # 참가자 제거
                    user_name = change.get("user_name", "")
                    round_name = change.get("round_name", "")
                    role = change.get("role", "")  # 역할 정보 추가
                    
                    if not user_name:
                        logger.warning(f"참가자 제거 정보 부족: {change}")
                        continue
                    
                    # 숫자+역할 형식 파싱 (예: "2딜", "3서폿" 등)
                    role_count = 1  # 기본값: 1개 역할 제거
                    if not round_name and role:
                        count_match = re.match(r'^(\d+)(.+)$', role)
                        if count_match:
                            role_count = int(count_match.group(1))
                            role = count_match.group(2)  # 숫자를 제외한 역할명만 추출
                    
                    # 특정 차수에서 제거 (round_name이 있는 경우)
                    if round_name:
                        for r in raid_data.rounds:
                            if r.name == round_name:
                                # 역할이 지정된 경우, 해당 역할만 제거
                                if role.lower() in ["서포터", "서폿", "support", "supporter"]:
                                    before_count = len(r.confirmed_supporters)
                                    r.confirmed_supporters = [s for s in r.confirmed_supporters if s[0] != user_name]
                                    if before_count > len(r.confirmed_supporters):
                                        changes_applied.append(f"{user_name}님이 {r.name}의 서포터에서 제거됨")
                                elif role.lower() in ["딜러", "딜", "dps", "dealer", "damage"]:
                                    before_count = len(r.confirmed_dealers)
                                    r.confirmed_dealers = [d for d in r.confirmed_dealers if d[0] != user_name]
                                    if before_count > len(r.confirmed_dealers):
                                        changes_applied.append(f"{user_name}님이 {r.name}의 딜러에서 제거됨")
                                # 역할이 지정되지 않은 경우, 모든 역할에서 제거
                                elif not role:
                                    # 서포터에서 제거
                                    before_count = len(r.confirmed_supporters)
                                    r.confirmed_supporters = [s for s in r.confirmed_supporters if s[0] != user_name]
                                    if before_count > len(r.confirmed_supporters):
                                        changes_applied.append(f"{user_name}님이 {r.name}의 서포터에서 제거됨")
                                    
                                    # 딜러에서 제거
                                    before_count = len(r.confirmed_dealers)
                                    r.confirmed_dealers = [d for d in r.confirmed_dealers if d[0] != user_name]
                                    if before_count > len(r.confirmed_dealers):
                                        changes_applied.append(f"{user_name}님이 {r.name}의 딜러에서 제거됨")
                                break
                    else:
                        # 차수가 지정되지 않은 경우, 후순위(마지막) 차수부터 지정된 개수만큼 제거
                        rounds_reversed = list(reversed(raid_data.rounds))  # 후순위부터 처리
                        logger.info(f"차수 미지정 제거: 사용자={user_name}, 역할={role}, 제거 수={role_count}")
                        
                        # 역할이 지정된 경우, 해당 역할만 지정된 개수만큼 제거
                        if role.lower() in ["서포터", "서폿", "support", "supporter"]:
                            removed_count = 0
                            for r in rounds_reversed:
                                if removed_count >= role_count:
                                    break  # 지정된 개수만큼 제거 완료
                                
                                # 해당 사용자가 이 차수의 서포터인지 확인
                                is_supporter = any(s[0] == user_name for s in r.confirmed_supporters)
                                if is_supporter:
                                    before_count = len(r.confirmed_supporters)
                                    r.confirmed_supporters = [s for s in r.confirmed_supporters if s[0] != user_name]
                                    changes_applied.append(f"{user_name}님이 {r.name}의 서포터에서 제거됨")
                                    removed_count += 1
                                    logger.info(f"서포터 제거: 사용자={user_name}, 차수={r.name}, 남은 제거 수={role_count-removed_count}")
                        
                        elif role.lower() in ["딜러", "딜", "dps", "dealer", "damage"]:
                            removed_count = 0
                            for r in rounds_reversed:
                                if removed_count >= role_count:
                                    break  # 지정된 개수만큼 제거 완료
                                
                                # 해당 사용자가 이 차수의 딜러인지 확인
                                is_dealer = any(d[0] == user_name for d in r.confirmed_dealers)
                                if is_dealer:
                                    before_count = len(r.confirmed_dealers)
                                    r.confirmed_dealers = [d for d in r.confirmed_dealers if d[0] != user_name]
                                    changes_applied.append(f"{user_name}님이 {r.name}의 딜러에서 제거됨")
                                    removed_count += 1
                                    logger.info(f"딜러 제거: 사용자={user_name}, 차수={r.name}, 남은 제거 수={role_count-removed_count}")
                        
                        # 역할이 지정되지 않은 경우, 모든 차수에서 모든 역할 제거
                        elif not role:
                            logger.info(f"모든 역할 제거: 사용자={user_name}")
                            for r in raid_data.rounds:
                                # 서포터에서 제거
                                before_count = len(r.confirmed_supporters)
                                r.confirmed_supporters = [s for s in r.confirmed_supporters if s[0] != user_name]
                                if before_count > len(r.confirmed_supporters):
                                    changes_applied.append(f"{user_name}님이 {r.name}의 서포터에서 제거됨")
                                    logger.info(f"서포터 제거: 사용자={user_name}, 차수={r.name}")
                                
                                # 딜러에서 제거
                                before_count = len(r.confirmed_dealers)
                                r.confirmed_dealers = [d for d in r.confirmed_dealers if d[0] != user_name]
                                if before_count > len(r.confirmed_dealers):
                                    changes_applied.append(f"{user_name}님이 {r.name}의 딜러에서 제거됨")
                                    logger.info(f"딜러 제거: 사용자={user_name}, 차수={r.name}")
                
                elif change_type == "update_schedule":
                    # 일정 업데이트
                    round_name = change.get("round_name", "")
                    schedule = change.get("schedule", "")
                    
                    if not all([round_name, schedule]):
                        logger.warning(f"일정 업데이트 정보 부족: {change}")
                        continue
                    
                    # 해당 차수 찾기
                    for r in raid_data.rounds:
                        if r.name == round_name:
                            r.when = schedule
                            changes_applied.append(f"{round_name}의 일정이 '{schedule}'로 업데이트됨")
                            break
                
                elif change_type == "add_round":
                    # 새 차수 추가
                    round_name = change.get("round_name", "")
                    schedule = change.get("schedule", "")
                    
                    if not round_name:
                        logger.warning(f"차수 추가 정보 부족: {change}")
                        continue
                    
                    # 이미 존재하는지 확인
                    round_exists = any(r.name == round_name for r in raid_data.rounds)
                    
                    if not round_exists:
                        # 차수 번호 추출
                        round_num = self.get_round_number(round_name)
                        new_round = RoundInfo(name=round_name, when=schedule)
                        
                        # 올바른 위치에 삽입 (차수 번호 순)
                        insert_idx = 0
                        for i, r in enumerate(raid_data.rounds):
                            r_num = self.get_round_number(r.name)
                            if r_num > round_num:
                                insert_idx = i
                                break
                            insert_idx = i + 1
                        
                        raid_data.rounds.insert(insert_idx, new_round)
                        changes_applied.append(f"새로운 차수 {round_name}이(가) 추가됨")
                
                elif change_type == "update_note":
                    # 노트 업데이트
                    round_name = change.get("round_name", "")
                    note = change.get("note", "")
                    
                    if not round_name:
                        logger.warning(f"노트 업데이트 정보 부족: {change}")
                        continue
                    
                    # 해당 차수 찾기
                    for r in raid_data.rounds:
                        if r.name == round_name:
                            r.note = note
                            changes_applied.append(f"{round_name}의 노트가 업데이트됨")
                            break
            
            except Exception as e:
                logger.error(f"변경 적용 중 오류 발생: {e}", exc_info=True)
        
        # 변경 적용 후 빈 차수 제거
        removed_count = await self.clean_empty_rounds(raid_data)
        if removed_count > 0:
            changes_applied.append(f"{removed_count}개의 빈 차수가 제거되었습니다")
        
        return changes_applied

    def get_round_number(self, round_name):
        """차수 이름에서 번호 추출"""
        match = re.search(r'(\d+)', round_name)
        if match:
            return int(match.group(1))
        return 9999  # 숫자가 없는 경우 맨 뒤로

    async def call_openai_api(self, messages, model="gpt-4-0125-preview", temperature=0.1, response_format=None):
        """OpenAI API 호출 함수"""
        if not self.openai_api_key:
            return {"error": "OpenAI API 키가 설정되지 않았습니다."}
        
        try:
            json_data = {
                "model": model,
                "messages": messages,
                "temperature": temperature
            }
            
            if response_format:
                json_data["response_format"] = response_format
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.openai_api_key}"
                    },
                    json=json_data
                ) as response:
                    response_data = await response.json()
                    
                    if "error" in response_data:
                        return {"error": f"OpenAI API 오류: {response_data['error']}"}
                    
                    if "choices" in response_data and len(response_data["choices"]) > 0:
                        content = response_data["choices"][0]["message"]["content"]
                        return {"content": content}
                    else:
                        return {"error": "LLM 응답에서 데이터를 찾을 수 없습니다."}
        except Exception as e:
            return {"error": f"OpenAI API 요청 중 오류: {e}"}

    async def update_message_safely(self, message, new_content):
        """안전하게 메시지 업데이트"""
        try:
            # 내용이 같으면 업데이트 건너뛰기
            if message.content == new_content:
                return {"status": "skipped", "reason": "내용이 동일합니다"}
            
            # 내용이 너무 길면 자르기
            if len(new_content) > 2000:
                logger.warning(f"메시지가 너무 깁니다 ({len(new_content)} 자). 2000자로 자릅니다.")
                new_content = new_content[:1997] + "..."
            
            await message.edit(content=new_content)
            return {"status": "success"}
        except discord.Forbidden:
            return {"status": "error", "reason": "메시지 수정 권한이 없습니다"}
        except discord.HTTPException as e:
            return {"status": "error", "reason": f"메시지 업데이트 중 오류: {e}"}
        except Exception as e:
            return {"status": "error", "reason": f"알 수 없는 오류: {e}"}

    async def parse_message_to_data(self, message_content):
        """메시지 내용을 구조화된 데이터로 파싱"""
        raid_data = RaidData(header="")
        
        # 메시지를 줄 단위로 분리
        lines = message_content.strip().split("\n")
        if not lines:
            return raid_data
        
        # 첫 줄은 헤더로 간주
        raid_data.header = lines[0]
        
        # 정보/차수 파싱
        current_section = "info"  # info, round
        current_round = None
        
        for i, line in enumerate(lines[1:], 1):  # 헤더 다음부터
            stripped_line = line.strip()
            
            # 빈 줄 건너뛰기
            if not stripped_line:
                continue
            
            # 새 차수 시작 확인 - '## N차' 형식
            round_match = re.match(r'^##\s+(\d+)차$', stripped_line)
            if not round_match:  # 기존 형식도 지원
                round_match = re.match(r'^(\d+)차$', stripped_line)
                
            if round_match:
                current_section = "round"
                # 이전 차수 저장
                if current_round is not None:
                    # 비어있지 않은 차수만 저장
                    if len(current_round.confirmed_supporters) > 0 or len(current_round.confirmed_dealers) > 0:
                        raid_data.rounds.append(current_round)
                
                # 새 차수 생성
                round_num = int(round_match.group(1))
                current_round = RoundInfo(name=f"{round_num}차")
                continue
            
            # info 섹션 처리
            if current_section == "info" and stripped_line.startswith("🔹"):
                raid_data.info.append(stripped_line)
                continue
            
            # round 섹션 처리
            if current_section == "round" and current_round is not None:
                # when 정보
                if stripped_line.startswith("- when:"):
                    current_round.when = stripped_line[7:].strip()
                elif stripped_line.startswith("when:"):  # 기존 형식도 지원
                    current_round.when = stripped_line[5:].strip()
                
                # who 정보
                elif stripped_line.startswith("- who:") or stripped_line.startswith("who:"):
                    continue  # who: 라인은 정보가 없으므로 건너뜀
                
                # 서포터 정보
                elif "서포터" in stripped_line and ":" in stripped_line:
                    parts = stripped_line.split(":", 1)
                    count_match = re.search(r'\((\d+)/\d+\)', parts[0])
                    
                    if len(parts) > 1 and parts[1].strip():
                        supporters = [s.strip() for s in parts[1].strip().split(",")]
                        current_round.confirmed_supporters = [(s, "") for s in supporters]
                
                # 딜러 정보
                elif "딜러" in stripped_line and ":" in stripped_line:
                    parts = stripped_line.split(":", 1)
                    count_match = re.search(r'\((\d+)/\d+\)', parts[0])
                    
                    if len(parts) > 1 and parts[1].strip():
                        dealers = [d.strip() for d in parts[1].strip().split(",")]
                        current_round.confirmed_dealers = [(d, "") for d in dealers]
                
                # 노트 정보
                elif stripped_line.startswith("- note:"):
                    current_round.note = stripped_line[7:].strip()
                elif stripped_line.startswith("note:"):  # 기존 형식도 지원
                    current_round.note = stripped_line[5:].strip()
        
        # 마지막 차수 추가 (비어있지 않은 경우만)
        if current_round is not None and (len(current_round.confirmed_supporters) > 0 or len(current_round.confirmed_dealers) > 0):
            raid_data.rounds.append(current_round)
        
        return raid_data

    async def format_data_to_message(self, raid_data):
        """구조화된 데이터를 메시지 형식으로 변환"""
        lines = [raid_data.header]
        
        # 정보 섹션 추가
        if raid_data.info:
            lines.append("")  # 헤더와 정보 사이 빈 줄
            lines.extend(raid_data.info)
        
        # 차수 정보 추가 (비어있는 차수는 건너뛰기)
        for r_idx, round_info in enumerate(raid_data.rounds):
            # 빈 차수는 건너뛰기
            if await self.is_empty_round(round_info):
                continue
                
            lines.append("")  # 차수 구분을 위한 빈 줄
            lines.append(f"## {round_info.name}")
            lines.append(f"- when: {round_info.when}")
            lines.append(f"- who:")
            
            # 서포터 정보
            supporters_str = ", ".join([s[0] for s in round_info.confirmed_supporters]) if round_info.confirmed_supporters else ""
            lines.append(f"  - 서포터({len(round_info.confirmed_supporters)}/{round_info.supporter_max}): {supporters_str}")
            
            # 딜러 정보
            dealers_str = ", ".join([d[0] for d in round_info.confirmed_dealers]) if round_info.confirmed_dealers else ""
            lines.append(f"  - 딜러({len(round_info.confirmed_dealers)}/{round_info.dealer_max}): {dealers_str}")
            
            # 노트 정보
            lines.append(f"- note: {round_info.note}")
        
        return "\n".join(lines) 