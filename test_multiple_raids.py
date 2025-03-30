import json

# 테스트용 가상 스레드 메시지 생성
test_messages = [
    {
        'author': '사용자1',
        'author_id': '111111111111111111',
        'content': '저는 하기르 레이드에 참가할 수 있어요. 바드 캐릭터로 참가할게요.',
        'created_at': '2023-07-01 10:00:00'
    },
    {
        'author': '사용자2',
        'author_id': '222222222222222222',
        'content': '저도 참가하고 싶어요! 소서리스로 참여할게요.',
        'created_at': '2023-07-01 10:05:00'
    },
    {
        'author': '사용자3',
        'author_id': '333333333333333333',
        'content': '저는 홀리나이트로 참가할게요.',
        'created_at': '2023-07-01 10:10:00'
    },
    {
        'author': '사용자1',
        'author_id': '111111111111111111',
        'content': '7월 5일 저녁 8시에 진행하면 어떨까요?',
        'created_at': '2023-07-01 10:15:00'
    },
    {
        'author': '사용자2',
        'author_id': '222222222222222222',
        'content': '좋아요! 저는 그 시간에 가능합니다.',
        'created_at': '2023-07-01 10:20:00'
    },
    {
        'author': '사용자3',
        'author_id': '333333333333333333',
        'content': '저도 가능합니다. 8시에 뵙겠습니다!',
        'created_at': '2023-07-01 10:25:00'
    },
    {
        'author': '사용자4',
        'author_id': '444444444444444444',
        'content': '저도 참가할게요! 인파이터로 참여하겠습니다.',
        'created_at': '2023-07-01 10:30:00'
    },
    {
        'author': '사용자1',
        'author_id': '111111111111111111',
        'content': '그럼 7월 5일 저녁 8시에 하기르 레이드 진행하도록 하겠습니다!',
        'created_at': '2023-07-01 10:35:00'
    },
    {
        'author': '사용자5',
        'author_id': '555555555555555555',
        'content': '저는 2차 때 참가할게요! 바드로 참여하겠습니다.',
        'created_at': '2023-07-01 10:40:00'
    },
    {
        'author': '사용자2',
        'author_id': '222222222222222222',
        'content': '2차는 언제 진행하나요?',
        'created_at': '2023-07-01 10:45:00'
    },
    {
        'author': '사용자5',
        'author_id': '555555555555555555',
        'content': '2차는 7월 6일 저녁 9시에 어떨까요?',
        'created_at': '2023-07-01 10:50:00'
    },
    {
        'author': '사용자6',
        'author_id': '666666666666666666',
        'content': '2차에 저도 참가할게요! 소울이터로 참여하겠습니다.',
        'created_at': '2023-07-01 10:55:00'
    }
]

# 가상의 분석 결과
analysis_result = {
    "participants": {
        "supporters": ["사용자1", "사용자3"],
        "dealers": ["사용자2", "사용자4"]
    },
    "schedule": {
        "date": "2023-07-05",
        "time": "저녁 8시"
    },
    "additional_info": "하기르 레이드 진행",
    "multiple_raids": [
        {
            "name": "2차",
            "participants": {
                "supporters": ["사용자5"],
                "dealers": ["사용자6"]
            },
            "schedule": {
                "date": "2023-07-06",
                "time": "저녁 9시"
            },
            "additional_info": None
        }
    ]
}

# 원본 메시지
original_message = """# 하기르 (카제로스 1막 하드)
🔹 필요 레벨: 1680 이상
🔹 모집 인원: 8명

## 1차
- when: 
- who: 서포터( ) / 딜러( )
- note: 
"""

def update_raid_message_simulation(original_content, analysis_result, messages):
    """레이드 메시지 업데이트 시뮬레이션"""
    # 참가자 정보 가져오기
    supporters = analysis_result.get("participants", {}).get("supporters", [])
    dealers = analysis_result.get("participants", {}).get("dealers", [])
    
    # 사용자 이름과 ID 매핑
    user_ids = {}
    for msg in messages:
        user_ids[msg['author']] = msg['author_id']
    
    # 멘션 형식으로 변환
    supporter_mentions = []
    for supporter in supporters:
        if supporter in user_ids:
            supporter_mentions.append(f"<@{user_ids[supporter]}>")
        else:
            supporter_mentions.append(supporter)
    
    dealer_mentions = []
    for dealer in dealers:
        if dealer in user_ids:
            dealer_mentions.append(f"<@{user_ids[dealer]}>")
        else:
            dealer_mentions.append(dealer)
    
    supporters = supporter_mentions
    dealers = dealer_mentions
    
    # 일정 정보 가져오기
    date_info = analysis_result.get("schedule", {}).get("date")
    time_info = analysis_result.get("schedule", {}).get("time")
    when_info = ""
    if date_info and time_info:
        when_info = f"{date_info} {time_info}"
    elif date_info:
        when_info = date_info
    elif time_info:
        when_info = time_info
    
    # 추가 정보 가져오기
    additional_info = analysis_result.get("additional_info")
    
    # 1차 일정 업데이트
    new_content = original_content
    
    # '- when:' 부분 업데이트
    if when_info:
        if "- when:" in new_content:
            lines = new_content.split("\n")
            for i, line in enumerate(lines):
                if "- when:" in line:
                    lines[i] = f"- when: {when_info}"
                    break
            new_content = "\n".join(lines)
    
    # '- who:' 부분 업데이트
    if supporters or dealers:
        supporters_str = ", ".join(supporters)
        dealers_str = ", ".join(dealers)
        
        if "- who:" in new_content:
            lines = new_content.split("\n")
            for i, line in enumerate(lines):
                if "- who:" in line:
                    lines[i] = f"- who: 서포터({supporters_str}) / 딜러({dealers_str})"
                    break
            new_content = "\n".join(lines)
    
    # '- note:' 부분 업데이트
    if additional_info:
        if "- note:" in new_content:
            lines = new_content.split("\n")
            for i, line in enumerate(lines):
                if "- note:" in line:
                    lines[i] = f"- note: {additional_info}"
                    break
            new_content = "\n".join(lines)
    
    # 추가 일정(2차, 3차 등) 업데이트
    multiple_raids = analysis_result.get("multiple_raids", [])
    if multiple_raids:
        # 현재 메시지에 있는 최종 차수 확인
        current_raids = []
        for line in new_content.split("\n"):
            if line.startswith("## ") and "차" in line:
                current_raids.append(line.replace("## ", "").strip())
        
        # 추가 일정 처리
        for raid in multiple_raids:
            raid_name = raid.get("name")
            if raid_name and raid_name not in current_raids:
                raid_supporters = raid.get("participants", {}).get("supporters", [])
                raid_dealers = raid.get("participants", {}).get("dealers", [])
                
                # 멘션 형식으로 변환
                raid_supporter_mentions = []
                for supporter in raid_supporters:
                    if supporter in user_ids:
                        raid_supporter_mentions.append(f"<@{user_ids[supporter]}>")
                    else:
                        raid_supporter_mentions.append(supporter)
                
                raid_dealer_mentions = []
                for dealer in raid_dealers:
                    if dealer in user_ids:
                        raid_dealer_mentions.append(f"<@{user_ids[dealer]}>")
                    else:
                        raid_dealer_mentions.append(dealer)
                
                raid_supporters = raid_supporter_mentions
                raid_dealers = raid_dealer_mentions
                
                schedule = raid.get("schedule", {})
                date_info = schedule.get("date")
                time_info = schedule.get("time")
                when_info = ""
                if date_info and time_info:
                    when_info = f"{date_info} {time_info}"
                elif date_info:
                    when_info = date_info
                elif time_info:
                    when_info = time_info
                
                additional_info = raid.get("additional_info", "")
                
                supporters_str = ", ".join(raid_supporters)
                dealers_str = ", ".join(raid_dealers)
                
                # 새 일정 추가
                new_content += f"\n\n## {raid_name}\n"
                new_content += f"- when: {when_info}\n"
                new_content += f"- who: 서포터({supporters_str}) / 딜러({dealers_str})\n"
                new_content += f"- note: {additional_info if additional_info else ''}"
    
    return new_content

# 메시지 업데이트 시뮬레이션 실행
updated_message = update_raid_message_simulation(original_message, analysis_result, test_messages)

# 결과 출력
print("원본 메시지:")
print("------------")
print(original_message)
print("\n업데이트된 메시지:")
print("------------------")
print(updated_message) 