import argparse
import asyncio
import json

from app.workers.indexing_task import _index_drive_folder


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run local indexing for one FaceFind event.")
    parser.add_argument("event_id", help="Event UUID to index")
    args = parser.parse_args()

    result = await _index_drive_folder(args.event_id, task=None)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
