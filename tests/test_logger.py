import csv
from datetime import datetime

import pytest

from naukri_apply.logger import CSVLogger, HEADERS
from naukri_apply.models import (
    ApplicationResult,
    ApplicationStatus,
    ApplyType,
    JobListing,
)


@pytest.fixture
def job_listing():
    return JobListing(
        company_name="Acme Inc",
        job_title="Python Developer",
        location="Bangalore",
        url="https://www.naukri.com/job-12345",
        apply_type=ApplyType.EASY_APPLY,
    )


class TestCSVLogger:
    def test_creates_file_with_headers(self, tmp_csv_path):
        logger = CSVLogger(tmp_csv_path)

        assert tmp_csv_path.exists()

        with open(tmp_csv_path, "r") as f:
            reader = csv.reader(f)
            headers = next(reader)

        assert headers == HEADERS

    def test_appends_row(self, tmp_csv_path, job_listing):
        logger = CSVLogger(tmp_csv_path)

        result = ApplicationResult(
            job=job_listing,
            status=ApplicationStatus.APPLIED,
            notes="Applied successfully",
        )
        logger.log(result)

        with open(tmp_csv_path, "r") as f:
            reader = csv.reader(f)
            headers = next(reader)
            row = next(reader)

        assert row[1] == "Acme Inc"
        assert row[2] == "Python Developer"
        assert row[3] == "Bangalore"
        assert row[5] == "easy_apply"
        assert row[6] == "applied"
        assert row[7] == "Applied successfully"

    def test_multiple_logs_produce_multiple_rows(self, tmp_csv_path, job_listing):
        logger = CSVLogger(tmp_csv_path)

        for i in range(3):
            result = ApplicationResult(
                job=job_listing,
                status=ApplicationStatus.APPLIED,
                notes=f"Application {i}",
            )
            logger.log(result)

        with open(tmp_csv_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # 1 header + 3 data rows
        assert len(rows) == 4

    def test_file_content_is_valid_csv(self, tmp_csv_path, job_listing):
        logger = CSVLogger(tmp_csv_path)

        result = ApplicationResult(
            job=job_listing,
            status=ApplicationStatus.FAILED,
            notes="Button not found",
        )
        logger.log(result)

        with open(tmp_csv_path, "r") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["company_name"] == "Acme Inc"
        assert rows[0]["status"] == "failed"
        assert rows[0]["notes"] == "Button not found"

    def test_does_not_overwrite_existing_file(self, tmp_csv_path, job_listing):
        # First logger creates file and logs
        logger1 = CSVLogger(tmp_csv_path)
        result = ApplicationResult(
            job=job_listing,
            status=ApplicationStatus.APPLIED,
        )
        logger1.log(result)

        # Second logger should not overwrite
        logger2 = CSVLogger(tmp_csv_path)
        result2 = ApplicationResult(
            job=job_listing,
            status=ApplicationStatus.SKIPPED,
        )
        logger2.log(result2)

        with open(tmp_csv_path, "r") as f:
            reader = csv.reader(f)
            rows = list(reader)

        # 1 header + 2 data rows
        assert len(rows) == 3
