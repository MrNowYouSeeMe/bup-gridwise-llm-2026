# Final Submission Checklist

## Already automated locally

- [ ] Full offline regression passes.
- [ ] Official 10-case public optimizer suite passes.
- [ ] Live model-backed E2E accuracy suite passes.
- [ ] Full E2E p95 latency is at or below 5 seconds in the final local measurement.
- [ ] Real concurrent requests complete correctly.
- [ ] `/health` returns exactly `{"status":"ok"}`.
- [ ] Docker image builds from a clean repository.
- [ ] Docker container reaches `/health`.
- [ ] Docker container completes one real `/optimize-energy` public sample.
- [ ] `.env` remains untracked.
- [ ] Repository secret scan passes.
- [ ] Fresh-clone offline reproduction passes using only `requirements.txt` and documented commands.
- [ ] Git working tree is clean and final local commit is pushed.

## Friend — Render deployment only

- [ ] Create one Render **Web Service** from this repository.
- [ ] Runtime: Docker.
- [ ] Branch: `main`.
- [ ] Root directory: repository root.
- [ ] Health path: `/health`.
- [ ] Environment: `OPENAI_API_KEY`, `OPENAI_MODEL=gpt-5.6-terra`, `GRIDWISE_LOG_LEVEL=INFO`.
- [ ] Do not paste the API key into code, Dockerfile, README, or logs.
- [ ] Return the final Render base URL and deployment status.

## After the friend returns the URL

- [ ] External `GET /health`.
- [ ] External official-sample `POST /optimize-energy`.
- [ ] External repeated requests.
- [ ] External p95 latency measurement.
- [ ] Verify endpoint stays reachable for judging.

## Submission artifacts requiring a human/account action

- [ ] Push/publish an exact Docker fallback image tag/digest to a registry.
- [ ] Record/upload the <=3-minute tie-break video.
- [ ] Submit public endpoint.
- [ ] Submit source repository.
- [ ] Make repository public after the organizer-defined submission deadline.
- [ ] Confirm Docker image remains pullable through the evaluation window.