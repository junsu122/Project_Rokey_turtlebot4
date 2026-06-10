#!/usr/bin/env bash
# 보안팀 로그인 경로 점검: 로그인 -> 인증 토큰 -> events 읽기 -> get_robots RPC.
# 비밀번호는 입력만 받고 출력/저장하지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."
CFG=web-vercel/supabase-config.js
URL=$(grep -oP 'url:\s*"\K[^"]+' "$CFG")
ANON=$(grep -oP 'anonKey:\s*"\K[^"]+' "$CFG")

read -rp "운영자 이메일: " EMAIL
read -rsp "비밀번호: " PW; echo

TOK=$(curl -s "$URL/auth/v1/token?grant_type=password" \
  -H "apikey: $ANON" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PW\"}")

AT=$(echo "$TOK" | grep -oP '"access_token":"\K[^"]+' || true)
if [ -z "$AT" ]; then
  echo "❌ 로그인 실패:"; echo "$TOK"
  echo "   (error_description 에 'Email not confirmed' 이면 Supabase > Authentication > Users 에서 해당 유저 Confirm)"
  exit 1
fi
echo "✅ 로그인 성공 (access_token 발급)"

echo -n "→ events 읽기(인증): "
curl -s -o /dev/null -w "HTTP %{http_code}\n" "$URL/rest/v1/events?select=*&limit=1" \
  -H "apikey: $ANON" -H "Authorization: Bearer $AT"

echo -n "→ get_robots RPC: "
curl -s -w "  HTTP %{http_code}\n" "$URL/rest/v1/rpc/get_robots" \
  -H "apikey: $ANON" -H "Authorization: Bearer $AT" \
  -H "Content-Type: application/json" -d '{"timeout_s":10}'

echo "둘 다 HTTP 200 이면 보안팀 화면 데이터 경로 정상."
