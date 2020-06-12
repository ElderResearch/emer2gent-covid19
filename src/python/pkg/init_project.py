#!/usr/bin/env python3

import io
import sys
import tarfile
from pathlib import Path

import requests

sys.path.append("trent")
from trent.data import run_pipeline

VERSION_ID = "ubTsPxn.gyi2RgyAtE9SrmpbGarnKzWK"


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
    run_pipeline()
