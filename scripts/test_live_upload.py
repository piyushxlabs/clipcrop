import asyncio
from pathlib import Path
import sys
import httpx


async def test():
    target_path = sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/test...ellipsis...case.mp4"
    filename = Path(target_path).name
    print(f"Uploading target file: {target_path} as '{filename}'")
    async with httpx.AsyncClient(timeout=60.0) as client:
        with open(target_path, "rb") as f:
            files = {"file": (filename, f, "video/mp4")}
            resp = await client.post("http://127.0.0.1:8000/runs", files=files)
            print("POST /runs status:", resp.status_code)
            data = resp.json()
            print("POST /runs data:", data)
            run_id = data.get("run_id")

        if run_id:
            print(f"Connecting to stream for run: {run_id}...")
            async with client.stream("GET", f"http://127.0.0.1:8000/runs/{run_id}/stream") as s:
                print("Stream status:", s.status_code)
                count = 0
                async for line in s.aiter_lines():
                    if line.strip():
                        print("SSE line:", line)
                        if "data-run-end" in line:
                            print("Pipeline run completed successfully!")
                            break
                        if '"type": "error"' in line or '"type":"error"' in line:
                            print("Encountered error event!")
                            break


if __name__ == "__main__":
    asyncio.run(test())
