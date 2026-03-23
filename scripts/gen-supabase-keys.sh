#!/bin/bash
# Generate Supabase JWT keys (ANON_KEY and SERVICE_ROLE_KEY)
# Requires: openssl
set -e

JWT_SECRET=${1:-$(openssl rand -hex 32)}

echo "============================================"
echo "  Supabase JWT Key Generator"
echo "============================================"
echo ""
echo "JWT_SECRET=$JWT_SECRET"
echo ""

# Generate ANON key (role: anon, iss: supabase)
ANON_PAYLOAD=$(echo -n '{"role":"anon","iss":"supabase","iat":1700000000,"exp":1900000000}' | openssl base64 -A | tr '+/' '-_' | tr -d '=')
ANON_HEADER=$(echo -n '{"alg":"HS256","typ":"JWT"}' | openssl base64 -A | tr '+/' '-_' | tr -d '=')
ANON_SIG=$(echo -n "${ANON_HEADER}.${ANON_PAYLOAD}" | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary | openssl base64 -A | tr '+/' '-_' | tr -d '=')
ANON_KEY="${ANON_HEADER}.${ANON_PAYLOAD}.${ANON_SIG}"

# Generate SERVICE_ROLE key
SVC_PAYLOAD=$(echo -n '{"role":"service_role","iss":"supabase","iat":1700000000,"exp":1900000000}' | openssl base64 -A | tr '+/' '-_' | tr -d '=')
SVC_HEADER=$(echo -n '{"alg":"HS256","typ":"JWT"}' | openssl base64 -A | tr '+/' '-_' | tr -d '=')
SVC_SIG=$(echo -n "${SVC_HEADER}.${SVC_PAYLOAD}" | openssl dgst -sha256 -hmac "$JWT_SECRET" -binary | openssl base64 -A | tr '+/' '-_' | tr -d '=')
SERVICE_ROLE_KEY="${SVC_HEADER}.${SVC_PAYLOAD}.${SVC_SIG}"

echo "ANON_KEY=$ANON_KEY"
echo ""
echo "SERVICE_ROLE_KEY=$SERVICE_ROLE_KEY"
echo ""
echo "Add these to your .env file."
echo "============================================"
