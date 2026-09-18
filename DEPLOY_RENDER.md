# Render Deployment Handoff

This is the only deployment task assigned to the friend.

Do not modify application code.

1. Open Render and create **New → Web Service**.
2. Connect GitHub and select `MrNowYouSeeMe/bup-gridwise-llm-2026`.
3. Branch: `main`.
4. Runtime: **Docker**.
5. Root directory: repository root.
6. Prefer the Singapore region when available.
7. Health Check Path: `/health`.
8. Add environment variables:
   - `OPENAI_API_KEY` = actual secret value
   - `OPENAI_MODEL` = `gpt-5.6-terra`
   - `GRIDWISE_LOG_LEVEL` = `INFO`
9. Do not commit/upload `.env`.
10. Deploy the Web Service.
11. After the service is Live, open `<base-url>/health`.
12. Send back only:
    - Render base URL
    - deploy status
    - `/health` result
    - relevant build/deploy logs if deployment failed

Do not send the OpenAI API key in chat, GitHub, screenshots, or logs.

After the URL is returned, the project owner will run the final external E2E and latency checks.