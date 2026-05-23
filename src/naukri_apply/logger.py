import csv
from pathlib import Path

from naukri_apply.models import ApplicationResult

HEADERS = [
    "timestamp",
    "company_name",
    "job_title",
    "location",
    "url",
    "apply_type",
    "status",
    "notes",
]


class CSVLogger:
    """Logs application results to a CSV file in real-time."""

    def __init__(self, output_path: str | Path):
        self.output_path = Path(output_path)

        if not self.output_path.exists():
            with open(self.output_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS)

    def log(self, result: ApplicationResult) -> None:
        """Append one application result row to the CSV file."""
        with open(self.output_path, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                result.timestamp.isoformat(),
                result.job.company_name,
                result.job.job_title,
                result.job.location,
                result.job.url,
                result.job.apply_type.value,
                result.status.value,
                result.notes or "",
            ])
            f.flush()
