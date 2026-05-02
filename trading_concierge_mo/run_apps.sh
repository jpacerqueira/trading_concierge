API_KEY=$1:-"YOUR_API_KEY"
export GEMINI_API_KEY="$API_KEY"
export GOOGLE_API_KEY="$API_KEY"
export GEMINI_INFERENCE_MODEL=gemini-3.1-pro-preview
export GEMINI_CONTEXT_MODEL=gemini-3.1-pro-preview
export GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
export GEMINI_TEMPERATURE=1.0
docker compose up --build
