echo "Requesting BVH file for 'a person walking forward'"
curl -X POST "http://localhost:6006/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "text_prompt": "a person walking forward"
  }' \
  --output walking.bvh