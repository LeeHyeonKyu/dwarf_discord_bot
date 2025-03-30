import json
import asyncio
import aiohttp
import os
import sys
import pathlib
import hashlib
from dotenv import load_dotenv

# 상위 디렉토리 경로를 추가하여 프로젝트 모듈을 import할 수 있게 함
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# .env.secret 파일 로드
load_dotenv('.env.secret')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# 캐시 디렉토리 설정
CACHE_DIR = pathlib.Path('/tmp/discord_bot_llm_cache')
CACHE_DIR.mkdir(parents=True, exist_ok=True)
print(f"LLM 캐시 디렉토리: {CACHE_DIR}")

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

# 원본 메시지
original_message = """# 하기르 (카제로스 1막 하드)
🔹 필요 레벨: 1680 이상
🔹 모집 인원: 8명

## 1차
- when: 
- who: 
  - 서포터(0/2): 
  - 딜러(0/6): 
- note: 
"""

def get_cache_key(thread_messages, message_content, raid_name):
    """입력 데이터의 해시값(캐시 키)을 생성합니다"""
    # 입력 데이터를 문자열로 직렬화
    data_str = json.dumps({
        'thread_messages': thread_messages,
        'message_content': message_content,
        'raid_name': raid_name
    }, sort_keys=True, ensure_ascii=False)
    
    # SHA-256 해시 생성
    hash_obj = hashlib.sha256(data_str.encode('utf-8'))
    return hash_obj.hexdigest()

def get_cached_result(cache_key):
    """캐시에서 결과를 가져옵니다"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
            print(f"캐시에서 결과를 로드했습니다: {cache_key}")
            return cached_data
        except Exception as e:
            print(f"캐시 로드 중 오류 발생: {e}")
    return None

def save_to_cache(cache_key, result):
    """결과를 캐시에 저장합니다"""
    cache_file = CACHE_DIR / f"{cache_key}.json"
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"결과를 캐시에 저장했습니다: {cache_key}")
    except Exception as e:
        print(f"캐시 저장 중 오류 발생: {e}")

async def analyze_messages_with_openai(thread_messages, message_content, raid_name):
    """OpenAI API를 사용하여 메시지 분석하고 업데이트된 메시지 반환 (캐싱 적용)"""
    if not OPENAI_API_KEY:
        return {"error": "OpenAI API 키가 설정되지 않았습니다. .env.secret 파일을 확인해주세요."}
    
    # 캐시 키 생성
    cache_key = get_cache_key(thread_messages, message_content, raid_name)
    
    # 캐시 확인
    cached_result = get_cached_result(cache_key)
    if cached_result:
        return cached_result
    
    # 메시지 포맷팅
    formatted_messages = []
    for msg in thread_messages:
        formatted_messages.append(f"{msg['author']} ({msg['created_at']}): {msg['content']}")
    
    messages_text = "\n".join(formatted_messages)
    
    # 디스코드 ID 매핑 생성
    user_ids = {}
    for msg in thread_messages:
        user_ids[msg['author']] = msg['author_id']
    
    # OpenAI에 보낼 프롬프트
    prompt = f"""
이것은 '{raid_name}' 레이드 참가에 관한 디스코드 스레드의 원본 메시지와 대화 내용입니다.

## 원본 메시지:
{message_content}

## 스레드 대화 내용:
{messages_text}

대화 내용을 분석하여 원본 메시지를 업데이트해주세요:
1. 참가자 목록을 서포터와 딜러로 구분하여 추가하세요
2. 참가자 이름은 디스코드 멘션 형식(<@사용자ID>)으로 변경해주세요
   - 사용자 ID 정보: {json.dumps(user_ids, ensure_ascii=False)}
3. 일정 정보(날짜, 시간)가 있으면 추가하세요
   - 날짜 형식은 "월/일(요일)" 형태로 통일해주세요 (예: "7/5(수)")
   - 시간은 24시간제로 표시해주세요 (예: "21:00")
   - 날짜와 시간은 함께 표시하세요 (예: "7/5(수) 21:00")
4. 추가 정보(메모, 특이사항 등)가 있으면 추가하세요
5. 2차, 3차 등의 추가 일정이 언급되었다면 새 섹션으로 추가하세요

## 참가자 규칙:
- 8인 레이드의 경우 서포터는 최대 2명까지만 가능합니다
- 4인 레이드의 경우 서포터는 최대 1명만 가능합니다
- "폿1딜2 참여"와 같은 메시지는 총 3번에 걸쳐서 참여하겠다는 의미입니다
  (서포터로 1번, 딜러로 2번 참여)
- 특정 차수를 지정하지 않은 경우, 모든 일정에 해당 참가자를 추가해야 합니다
- 서포터가 이미 최대 인원인 경우, 새로운 차수(예: 다음 차수)를 생성하여 초과된 서포터를 배정하세요

원본 메시지 형식을 유지하면서 대화 내용에서 파악한 정보를 채워넣은 완성된 메시지를 반환해주세요.
추가 설명 없이 업데이트된 메시지 내용만 반환해주세요.
"""

    try:
        print(f"OpenAI API 호출 중... (캐시 키: {cache_key[:8]}...)")
        # OpenAI API 호출
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }
        
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "당신은 디스코드 대화에서 정보를 추출하여 메시지를 업데이트하는 도우미입니다."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.openai.com/v1/chat/completions", 
                headers=headers, 
                json=payload
            ) as response:
                if response.status == 200:
                    response_data = await response.json()
                    content = response_data['choices'][0]['message']['content']
                    
                    # 텍스트 정제 (불필요한 설명이나 마크다운 포맷 제거)
                    if "```" in content:
                        # 코드 블록 내용만 추출
                        content = content.split("```")[1].strip()
                        if content.startswith("markdown\n") or content.startswith("md\n"):
                            content = "\n".join(content.split("\n")[1:])
                    
                    result = {"content": content}
                    
                    # 결과를 캐시에 저장
                    save_to_cache(cache_key, result)
                    
                    return result
                else:
                    error_result = {"error": f"OpenAI API 오류: 상태 코드 {response.status}"}
                    return error_result
    
    except Exception as e:
        error_result = {"error": f"OpenAI API 오류: {str(e)}"}
        return error_result

async def main():
    """테스트 실행"""
    if not OPENAI_API_KEY:
        print("OPENAI_API_KEY가 설정되지 않았습니다. .env.secret 파일을 확인해주세요.")
        return
    
    print("테스트 메시지 분석을 시작합니다...")
    
    # 테스트 메시지 분석 및 직접 업데이트된 메시지 생성
    analysis_result = await analyze_messages_with_openai(test_messages, original_message, "하기르")
    
    if "error" in analysis_result:
        print(f"분석 오류: {analysis_result['error']}")
    else:
        print("\n원본 메시지:")
        print("------------")
        print(original_message)
        print("\n업데이트된 메시지:")
        print("------------------")
        print(analysis_result["content"])

if __name__ == "__main__":
    asyncio.run(main()) 