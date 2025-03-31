FROM python:3.9-slim

WORKDIR /app

# 환경 변수 설정 - 파이썬 출력을 버퍼링하지 않음
ENV PYTHONUNBUFFERED=1

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 데이터 디렉토리 생성
RUN mkdir -p data
RUN mkdir -p /tmp/discord_bot_llm_cache

# 봇 실행 - -u 옵션으로 출력 버퍼링 비활성화
CMD ["python", "-u", "bot.py"] 