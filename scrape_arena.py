import logging
import os
import re

# --- GLOBAL LOGGING CONFIGURATION ---
ENV_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, ENV_LOG_LEVEL, logging.INFO)

# Format: [YYYY-MM-DD HH:MM:SS] [script_name] [LEVEL] Context message
LOG_FORMAT = "[%(asctime)s] [scrape_arena] [%(levelname)s] %(message)s"
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
logger = logging.getLogger(__name__)

import json
from datetime import datetime

import polars as pl
from datasets import load_dataset

# Configuration
HISTORY_FILE = "data/history.json"
ARCHIVE_FILE = "data/archive.json"
os.makedirs("data", exist_ok=True)

# Custom mapping for organization capitalization conventions
ORG_MAPPING = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "zai": "Z.ai",
    "minimax": "MiniMax",
    "xiaomi": "Xiaomi",
    "moonshot": "Moonshot",
    "alibaba": "Alibaba",
    "xai": "SpaceXAI",
    "deepseek": "DeepSeek",
}

def slugify_name(name: str) -> str:
  """Converts a model name into a clean kebab-case identifier.
  Example: 'Claude Opus 5.5 (Max)' -> 'claude-opus-5.5-max'
  """
  slug = name.lower()
  slug = re.sub(r"[^\w\s\.-]", "", slug)
  slug = re.sub(r"[\s_]+", "-", slug)
  return slug.strip("-")

def get_latest_data():
    logger.info("Fetching latest WebDev Arena dataset using Polars...")

    # Pull live webdev dataset and convert natively to a Polars DataFrame via Apache Arrow
    dataset = load_dataset("lmarena-ai/leaderboard-dataset", "webdev")
    df = dataset["latest"].to_polars()

    # FILTER: Keep only the overall WebDev leaderboard category
    if "category" in df.columns:
        df = df.filter(pl.col("category").str.to_lowercase() == "overall")
        logger.debug("Filtered dataset to 'overall' category successfully.")

    # Sort by official rank to guarantee the exact leaderboard order
    if "rank" in df.columns:
        df = df.sort("rank", descending=False)

    standardized = []
    seen_models = set()  # Track unique models to prevent duplicate entries

    # Iterate safely through rows using Polars' high-performance row iter
    for m in df.iter_rows(named=True):
        name = m.get("model_name") or m.get("modelDisplayName")
        score = m.get("rating") or m.get("score")  # dataset uses 'rating' for Elo
        org = m.get("organization") or m.get("modelOrganization")

        if name and score:
            model_key = str(name).strip().lower()

            # Skip if we already recorded this model in the current run
            if model_key in seen_models:
                continue

            try:
                parsed_score = round(float(score), 1)
            except (ValueError, TypeError):
                continue

            # Format organization name using the custom convention map
            raw_org_key = str(org).strip().lower() if org else ""
            formatted_org = ORG_MAPPING.get(
                raw_org_key, str(org).strip().title() if org else "Unknown"
            )

            seen_models.add(model_key)
            formatted_name = slugify_name(str(name))
            standardized.append(
                {"name": formatted_name, "score": parsed_score, "org": formatted_org}
            )

        # Stop once we have gathered the top 25 unique models
        if len(standardized) >= 25:
            break

    if not standardized:
        logger.error("Dataset loaded, but no valid unique model entries found.")
        raise ValueError(
            "Dataset loaded, but no valid unique model entries found for the overall category."
        )
    logger.info(
        f"Successfully processed {len(standardized)} unique models from top-tier rankings."
    )

    return standardized


def update_history():
    try:
        new_snapshot = get_latest_data()
        today = datetime.now().strftime("%Y-%m-%d")

        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
            logger.debug(f"Loaded existing history file with {len(history)} records.")
        else:
            history = []
            logger.debug(
                "No existing history file found. Initializing empty history list."
            )

        # Prevent duplicate entries for the same day
        if not any(entry["date"] == today for entry in history):
            history.append({"date": today, "models": new_snapshot})

            # ARCHIVE LOGIC: Check if history now exceeds 100 entries
            if len(history) > 100:
                old_records = history[:-100]
                logger.info(
                    f"History length ({len(history)}) exceeds threshold. Archiving {len(old_records)} old record(s)."
                )

                if os.path.exists(ARCHIVE_FILE):
                    with open(ARCHIVE_FILE, "r") as f:
                        archive_data = json.load(f)
                else:
                    archive_data = []

                archive_data.extend(old_records)
                with open(ARCHIVE_FILE, "w") as f:
                    json.dump(archive_data, f, indent=2)

            # Keep only last 100 snapshots
            history = history[-100:]

            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
            logger.info(f"Successfully updated history snapshot for {today}.")
        else:
            logger.warning(
                f"Snapshot for today ({today}) already exists. Skipping duplicate entry."
            )

    except Exception as e:
        logger.critical(f"Critical error during history update workflow: {e}")
        raise  # Re-raise to ensure GitHub Actions reports failure


if __name__ == "__main__":
    logger.info("Starting WebDev Arena daily tracking job...")
    update_history()
    logger.info("Job execution completed.")
