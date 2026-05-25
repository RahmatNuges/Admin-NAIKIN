from __future__ import annotations

import sys

from app.db import Base, engine


def main() -> int:
    Base.metadata.create_all(bind=engine)
    print("DB tables created at:", engine.url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
