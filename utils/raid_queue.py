import dataclasses
import copy
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class RaidQueueElement:
    """레이드 참여 큐의 요소를 나타내는 데이터 클래스"""
    round: int  # 차수 (0은 미지정)
    user_participation_count: int  # 사용자의 참여 신청 캐릭터 수
    role: str  # 역할 (support, dealer)
    user_name: str  # 사용자 이름
    user_id: str  # 사용자 ID (Discord 멘션용)


@dataclass
class UserParticipationData:
    """사용자 참여 데이터를 관리하는 데이터 클래스"""
    user_id: str  # 사용자 ID
    user_name: str  # 사용자 이름
    participation_count: int = 0  # 참여 신청 캐릭터 수


@dataclass
class RoundInfo:
    """라운드 정보"""
    round_index: int
    when: str = ""
    support: List[Tuple[str, str]] = field(default_factory=list)  # (user_name, user_id)
    dealer: List[Tuple[str, str]] = field(default_factory=list)  # (user_name, user_id)
    note: str = ""


class RaidQueue:
    """레이드 참여 큐를 관리하는 클래스"""
    
    def __init__(self, thread_id: str):
        """
        Args:
            thread_id: 스레드 ID
        """
        self.thread_id = thread_id
        self.queue: List[RaidQueueElement] = []
        # 사용자별 참여 데이터 (user_id -> UserParticipationData)
        self.user_data: Dict[str, UserParticipationData] = {}
    
    def _sort_queue(self):
        """큐를 우선순위에 따라 정렬"""
        # 우선순위: round 지정 > user_참여_count > role(support)
        self.queue.sort(key=lambda x: (
            -1 if x.round > 0 else 0,  # round 지정한 것이 우선
            x.user_participation_count,  # 참여 횟수가 많을수록 우선
            1 if x.role.lower() == 'support' else 0  # support 역할이 우선
        ), reverse=True)
    
    def add_user_participation(self, user_id: str, user_name: str):
        """사용자 참여 카운트 증가"""
        if user_id in self.user_data:
            self.user_data[user_id].participation_count += 1
        else:
            self.user_data[user_id] = UserParticipationData(
                user_id=user_id,
                user_name=user_name,
                participation_count=1
            )
    
    def decrease_user_participation(self, user_id: str):
        """사용자 참여 카운트 감소"""
        if user_id in self.user_data and self.user_data[user_id].participation_count > 0:
            self.user_data[user_id].participation_count -= 1
            return True
        return False
    
    def enqueue(self, user_id: str, user_name: str, role: str, round_num: int = 0):
        """큐에 요소 추가
        
        Args:
            user_id: 사용자 ID
            user_name: 사용자 이름
            role: 역할 (support, dealer)
            round_num: 차수 (0은 미지정)
        """
        # 사용자 참여 카운트 증가
        self.add_user_participation(user_id, user_name)
        
        # 현재 사용자의 참여 카운트 가져오기
        participation_count = self.user_data[user_id].participation_count
        
        # 큐에 요소 추가
        element = RaidQueueElement(
            round=round_num,
            user_participation_count=participation_count,
            role=role,
            user_name=user_name,
            user_id=user_id
        )
        self.queue.append(element)
        
        # 큐 정렬
        self._sort_queue()
        
        return element
    
    def dequeue(self, user_name: str, role: Optional[str] = None, round_num: Optional[int] = None):
        """큐에서 요소 제거
        
        Args:
            user_name: 사용자 이름
            role: 역할 (옵션)
            round_num: 차수 (옵션)
        
        Returns:
            제거된 요소, 없으면 None
        """
        # 디버깅: 현재 큐의 상태와 제거 요청 정보 출력
        logger.info(f"[DEBUG] Thread ID: {self.thread_id}, 제거 요청: user_name={user_name}, role={role}, round={round_num}")
        logger.info(f"[DEBUG] 현재 큐 상태 (총 {len(self.queue)}개 항목):")
        for idx, item in enumerate(self.queue):
            logger.info(f"  [{idx}] user={item.user_name}, user_id={item.user_id}, role={item.role}, round={item.round}, count={item.user_participation_count}")
        
        # 멘션 형태 확인 (Discord ID 추출)
        user_id_from_mention = None
        mention_match = re.match(r'<@(\d+)>', user_name)
        if mention_match:
            user_id_from_mention = mention_match.group(1)
            logger.info(f"[DEBUG] 멘션 형태에서 추출한 사용자 ID: {user_id_from_mention}")
        
        # 사용자 ID가 포함된 경우도 확인
        contained_user_ids = re.findall(r'(\d{17,20})', user_name)
        if contained_user_ids:
            logger.info(f"[DEBUG] 사용자 이름에서 추출한 가능한 ID들: {contained_user_ids}")
        
        # 라운드 요청이 없는 경우 라운드 검사를 건너뛰도록 플래그 설정
        check_round = round_num is not None and round_num > 0
        
        logger.info(f"[DEBUG] 라운드 검사 여부: {check_round}, 요청된 라운드: {round_num}")
        
        # 일치하는 모든 요소의 인덱스 저장
        matching_indices = []
        
        # 조건에 맞는 요소 찾기
        for i, element in enumerate(self.queue):
            matches = False
            
            # 1. 정확한 이름 일치
            if element.user_name.lower() == user_name.lower():
                matches = True
                logger.info(f"[DEBUG] 정확한 이름 일치: {element.user_name} == {user_name}")
            
            # 2. 멘션 형태로 일치 (요청이 멘션 형태인 경우)
            elif user_id_from_mention and element.user_id == user_id_from_mention:
                matches = True
                logger.info(f"[DEBUG] 멘션 ID 일치: {element.user_id} == {user_id_from_mention}")
            
            # 3. 요소가 멘션 형태인 경우
            elif element.user_name.startswith('<@') and element.user_name.endswith('>'):
                element_id_match = re.match(r'<@(\d+)>', element.user_name)
                if element_id_match and element_id_match.group(1) in user_name:
                    matches = True
                    logger.info(f"[DEBUG] 요소의 멘션 ID가 요청에 포함됨: {element.user_name} in {user_name}")
            
            # 4. 추출된 ID가 요소의 user_id와 일치하는 경우
            elif contained_user_ids and element.user_id in contained_user_ids:
                matches = True
                logger.info(f"[DEBUG] 추출된 ID 일치: {element.user_id} in {contained_user_ids}")
            
            # 역할 체크 (지정된 경우만)
            if matches and role:
                if element.role.lower() != role.lower():
                    matches = False
                    logger.info(f"[DEBUG] 역할 불일치: {element.role} != {role}")
            
            # 차수 체크 (지정된 경우만)
            if matches and check_round:
                if element.round != round_num:
                    matches = False
                    logger.info(f"[DEBUG] 차수 불일치: {element.round} != {round_num}")
            
            # 모든 조건 일치 시 인덱스 저장
            if matches:
                matching_indices.append(i)
                logger.info(f"[DEBUG] 일치하는 요소 발견: 인덱스 {i}, 사용자={element.user_name}, 역할={element.role}, 라운드={element.round}")
        
        # 일치하는 요소가 없으면 None 반환
        if not matching_indices:
            logger.info(f"[DEBUG] 조건에 맞는 요소를 찾지 못함: user_name={user_name}, role={role}, round={round_num}")
            return None
        
        # 가장 먼저 찾은 요소 제거 (인덱스가 큰 순서대로 제거해야 앞의 인덱스가 변하지 않음)
        i = matching_indices[0]  # 첫 번째 일치하는 요소만 제거
        removed = self.queue.pop(i)
        logger.info(f"[DEBUG] 요소 제거 성공: {removed}")
        
        # 사용자 참여 카운트 감소
        if removed.user_id:
            self.decrease_user_participation(removed.user_id)
            logger.info(f"[DEBUG] 사용자({removed.user_id}) 참여 카운트 감소됨")
        
        return removed
    
    def get_elements_by_user(self, user_name: str) -> List[RaidQueueElement]:
        """특정 사용자의 모든 큐 요소 반환"""
        # 멘션 형태 확인 (Discord ID 추출)
        user_id_from_mention = None
        mention_match = re.match(r'<@(\d+)>', user_name)
        if mention_match:
            user_id_from_mention = mention_match.group(1)
            logger.info(f"[DEBUG] get_elements_by_user: 멘션 형태에서 추출한 사용자 ID: {user_id_from_mention}")
        
        result = []
        for elem in self.queue:
            # 일반 이름 비교
            if elem.user_name.lower() == user_name.lower():
                result.append(elem)
                continue
            
            # 멘션 형태로 비교
            if user_id_from_mention and elem.user_id == user_id_from_mention:
                logger.info(f"[DEBUG] get_elements_by_user: 멘션 형식으로 일치: {elem.user_id} == {user_id_from_mention}")
                result.append(elem)
                continue
            
            # elem.user_name이 멘션 형태인 경우
            element_mention_match = re.match(r'<@(\d+)>', elem.user_name)
            if element_mention_match:
                element_user_id = element_mention_match.group(1)
                # user_name에 ID가 포함되어 있는지 확인
                if element_user_id == elem.user_id and elem.user_id in user_name:
                    logger.info(f"[DEBUG] get_elements_by_user: 요소의 멘션 형식으로 일치: {elem.user_name} 포함 {user_name}")
                    result.append(elem)
        
        return result
    
    def get_elements_by_round(self, round_num: int) -> List[RaidQueueElement]:
        """특정 차수의 모든 큐 요소 반환"""
        return [elem for elem in self.queue if elem.round == round_num]
    
    def clear(self):
        """큐 초기화"""
        self.queue.clear()
        self.user_data.clear()
    
    def deepcopy(self):
        """큐의 깊은 복사본 반환"""
        return copy.deepcopy(self)
    
    def generate_schedule_message(self, 
                                 support_max: int = 2, 
                                 dealer_max: int = 6) -> Tuple[str, List[RoundInfo]]:
        """큐를 기반으로 일정 메시지 생성
        
        Args:
            support_max: 서포터 최대 인원
            dealer_max: 딜러 최대 인원
        
        Returns:
            생성된 메시지와 라운드 정보 목록
        """
        # 디버깅: 현재 큐 상태 출력
        logger.info(f"[DEBUG] generate_schedule_message 실행 - 현재 큐 상태 (총 {len(self.queue)}개 항목):")
        for idx, item in enumerate(self.queue):
            logger.info(f"  [{idx}] user={item.user_name}, user_id={item.user_id}, role={item.role}, round={item.round}, count={item.user_participation_count}")
        
        # 큐 복사
        queue_copy = self.deepcopy()
        
        # 라운드 정보 목록
        round_infos: List[RoundInfo] = []
        
        # 이미 배정된 사용자 추적
        assigned_users = set()
        
        # 사용자 ID를 저장하기 위한 매핑
        user_id_map = {}  # user_name -> user_id
        
        # 큐의 모든 요소에서 사용자 ID 매핑 구성
        for element in self.queue:
            user_id_map[element.user_name] = element.user_id
        
        # 라운드 지정된 요소 먼저 처리
        has_round_specified_elements = False
        for element in list(queue_copy.queue):
            if element.round > 0:
                has_round_specified_elements = True
                # 해당 라운드 정보 찾기 또는 생성
                round_info = None
                for ri in round_infos:
                    if ri.round_index == element.round:
                        round_info = ri
                        break
                
                if round_info is None:
                    round_info = RoundInfo(round_index=element.round)
                    # 올바른 위치에 삽입
                    inserted = False
                    for i, ri in enumerate(round_infos):
                        if ri.round_index > element.round:
                            round_infos.insert(i, round_info)
                            inserted = True
                            break
                    if not inserted:
                        round_infos.append(round_info)
                    logger.info(f"[DEBUG] 새 라운드 생성: 라운드 {element.round}")
                
                # 사용자가 이미 이 라운드에 배정되어 있는지 확인
                user_key = f"{element.user_name}:{element.round}"
                if user_key in assigned_users:
                    continue
                
                # 역할별 인원 체크 후 배정
                if element.role.lower() == 'support' and len(round_info.support) < support_max:
                    round_info.support.append((element.user_name, element.user_id))
                    assigned_users.add(user_key)
                    queue_copy.queue.remove(element)
                    logger.info(f"[DEBUG] 라운드 {element.round}에 서포터 배정: {element.user_name}")
                elif element.role.lower() == 'dealer' and len(round_info.dealer) < dealer_max:
                    round_info.dealer.append((element.user_name, element.user_id))
                    assigned_users.add(user_key)
                    queue_copy.queue.remove(element)
                    logger.info(f"[DEBUG] 라운드 {element.round}에 딜러 배정: {element.user_name}")
        
        # 라운드가 지정된 요소가 없는 경우, 기본 라운드 생성
        if not has_round_specified_elements and not round_infos:
            default_round = RoundInfo(round_index=1)
            round_infos.append(default_round)
            logger.info("[DEBUG] 라운드 지정된 요소가 없어 기본 1차 생성")
        
        # 나머지 요소 처리 (라운드가 0인 요소들)
        remaining_elements = sorted(
            queue_copy.queue, 
            key=lambda x: (x.user_participation_count, 1 if x.role.lower() == 'support' else 0),
            reverse=True
        )
        
        for element in remaining_elements:
            # 적합한 라운드 찾기
            assigned = False
            
            for round_info in sorted(round_infos, key=lambda x: x.round_index):
                # 사용자가 이미 이 라운드에 배정되어 있는지 확인
                user_key = f"{element.user_name}:{round_info.round_index}"
                if user_key in assigned_users:
                    continue
                
                # 역할별 인원 체크 후 배정
                if element.role.lower() == 'support' and len(round_info.support) < support_max:
                    round_info.support.append((element.user_name, element.user_id))
                    assigned_users.add(user_key)
                    assigned = True
                    logger.info(f"[DEBUG] 라운드 {round_info.round_index}에 서포터 배정: {element.user_name} (라운드 미지정 요소)")
                    break
                elif element.role.lower() == 'dealer' and len(round_info.dealer) < dealer_max:
                    round_info.dealer.append((element.user_name, element.user_id))
                    assigned_users.add(user_key)
                    assigned = True
                    logger.info(f"[DEBUG] 라운드 {round_info.round_index}에 딜러 배정: {element.user_name} (라운드 미지정 요소)")
                    break
            
            # 적합한 라운드가 없으면 새 라운드 생성
            if not assigned:
                next_round_index = 1
                if round_infos:
                    next_round_index = max(ri.round_index for ri in round_infos) + 1
                
                new_round = RoundInfo(round_index=next_round_index)
                
                # 역할에 따라 배정
                if element.role.lower() == 'support':
                    new_round.support.append((element.user_name, element.user_id))
                    logger.info(f"[DEBUG] 새 라운드 {next_round_index}에 서포터 배정: {element.user_name}")
                else:
                    new_round.dealer.append((element.user_name, element.user_id))
                    logger.info(f"[DEBUG] 새 라운드 {next_round_index}에 딜러 배정: {element.user_name}")
                
                assigned_users.add(f"{element.user_name}:{new_round.round_index}")
                round_infos.append(new_round)
        
        # 메시지 포맷팅
        message = ""
        for round_info in sorted(round_infos, key=lambda x: x.round_index):
            message += f"{round_info.round_index}차\n"
            message += f"when: {round_info.when}\n"
            
            # 서포터
            support_count = len(round_info.support)
            message += f"서포터({support_count}/{support_max}):"
            if round_info.support:
                message += " "
                # 유저 이름을 멘션으로 변환
                support_mentions = []
                for name, user_id in round_info.support:
                    if user_id:
                        support_mentions.append(f"<@{user_id}>")
                    else:
                        support_mentions.append(name)
                message += ", ".join(support_mentions)
            message += "\n"
            
            # 딜러
            dealer_count = len(round_info.dealer)
            message += f"딜러({dealer_count}/{dealer_max}):"
            if round_info.dealer:
                message += " "
                # 유저 이름을 멘션으로 변환
                dealer_mentions = []
                for name, user_id in round_info.dealer:
                    if user_id:
                        dealer_mentions.append(f"<@{user_id}>")
                    else:
                        dealer_mentions.append(name)
                message += ", ".join(dealer_mentions)
            message += "\n"
            
            # 노트
            message += f"note: {round_info.note}\n"
            
            message += "\n"
        
        logger.info(f"[DEBUG] 생성된 일정 메시지: {len(round_infos)}개 라운드")
        return message, round_infos


class RaidQueueManager:
    """스레드별 레이드 큐 관리자"""
    
    def __init__(self):
        # 스레드 ID -> RaidQueue
        self.queues: Dict[str, RaidQueue] = {}
    
    def get_queue(self, thread_id: str) -> RaidQueue:
        """특정 스레드의 큐 반환, 없으면 생성"""
        if thread_id not in self.queues:
            self.queues[thread_id] = RaidQueue(thread_id)
        return self.queues[thread_id]
    
    def process_add_command(self, thread_id: str, user_id: str, user_name: str, 
                            role: str, round_num: int = 0) -> RaidQueueElement:
        """추가 명령어 처리"""
        queue = self.get_queue(thread_id)
        logger.info(f"[DEBUG] 추가 명령어 처리: thread_id={thread_id}, user={user_name}, role={role}, round={round_num}")
        
        # 유효한 라운드 번호인지 확인 (0은 미지정)
        if round_num is None:
            round_num = 0
        
        # 역할 정규화
        normalized_role = role.lower()
        if normalized_role == "딜러" or normalized_role == "딜" or normalized_role == "dealer":
            normalized_role = "dealer"
        elif normalized_role == "서포터" or normalized_role == "서폿" or normalized_role == "폿" or normalized_role == "support":
            normalized_role = "support"
        
        # 큐에 요소 추가
        element = queue.enqueue(user_id, user_name, normalized_role, round_num)
        
        logger.info(f"[DEBUG] 큐에 요소 추가됨: {element.user_name} ({normalized_role}, 라운드 {round_num})")
        return element
    
    def process_remove_command(self, thread_id: str, user_name: str, 
                              role: Optional[str] = None, 
                              round_num: Optional[int] = None) -> Optional[RaidQueueElement]:
        """제거 명령어 처리"""
        if thread_id not in self.queues:
            logger.warning(f"[DEBUG] 제거 명령어 처리: thread_id={thread_id}의 큐가 존재하지 않음")
            return None
        
        queue = self.queues[thread_id]
        
        # 역할 정규화
        normalized_role = None
        if role:
            normalized_role = role.lower()
            if normalized_role == "딜러" or normalized_role == "딜" or normalized_role == "dealer":
                normalized_role = "dealer"
            elif normalized_role == "서포터" or normalized_role == "서폿" or normalized_role == "폿" or normalized_role == "support":
                normalized_role = "support"
        
        logger.info(f"[DEBUG] 제거 명령어 처리: thread_id={thread_id}, user={user_name}, role={normalized_role}, round={round_num}")
        
        # 큐에서 요소 제거
        removed = queue.dequeue(user_name, normalized_role, round_num)
        
        if removed:
            logger.info(f"[DEBUG] 큐에서 요소 제거됨: {removed.user_name} ({removed.role}, 라운드 {removed.round})")
        else:
            logger.warning(f"[DEBUG] 큐에서 요소 제거 실패: user={user_name}, role={normalized_role}, round={round_num}")
        
        return removed


# 전역 큐 매니저
raid_queue_manager = RaidQueueManager() 