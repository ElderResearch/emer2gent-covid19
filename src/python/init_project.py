#!/usr/bin/env python3

from pathlib import Path
import io
import tarfile
import requests

VERSION_ID = "bWNeG9_Pi5XUxdx_R9n3kDfuIsMHueZW"


def download_data():
    """Download data sources archive from S3 and unpack into the data directory"""
    curdir = Path(__file__).resolve()
    data_dir = curdir.parents[2] / "data"
    if not data_dir.exists():
        data_dir.mkdir()

    r = requests.get(
        f"https://emer2gent-covid19.s3.amazonaws.com/data/project_data.tar.gz?versionId={VERSION_ID}"
    )

    with tarfile.open(mode="r:gz", fileobj=io.BytesIO(r.content)) as archive:
        archive.extractall(path=data_dir)


if __name__ == "__main__":
    download_data()
