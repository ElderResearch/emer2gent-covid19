"""Datasets and dataloaders for PyTorch."""

from typing import Generator, Iterable, Tuple

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader, Dataset


class RepeatedStratifiedGroupKFoldOrchestrator:
    """Orchestrate repeated, stratified, group-wise, K-fold CV.

    For want of time, this _assumes_ you stratify by *state* and group
    by *county*.

    Usage:

        cv = RepeatedStratifiedGroupKFoldOrchestrator(
            srcfile="test.csv",
            folds=5,
            repeats=5,
            batch_size=64
        )

        for repeat in cv:
            for train_dl, test_dl in repeat:
                for batch in train_dl:
                    ...
                for batch in test_dl:
                    ...
    """

    def __init__(
        self, srcfile: str, folds: int = 5, repeats: int = 1, batch_size: int = 1
    ):
        """Initialize the orchestrator.

        Args:
            srcfile (str): path to the ABT CSV
            folds (int): number of CV folds per repeat
            repeats (int): number of repeats, shuffling each time
            batch_size (int): eventual torch dataloader batch size
        """
        # Load the data
        self.data = pd.read_csv(srcfile)
        self.folds = folds
        self.repeats = repeats
        self.batch_size = batch_size

    def __iter__(self) -> Generator["_StratifiedGroupKFoldOrchestrator", None, None]:
        """Shuffle the dataset and produce a CV orchestrator."""
        for i in range(self.repeats):
            yield _StratifiedGroupKFoldOrchestrator(
                data=self.data.sample(frac=1).copy(),
                folds=self.folds,
                batch_size=self.batch_size,
            )


class _StratifiedGroupKFoldOrchestrator:
    """Helper class to carry out grouped, stratified CV

    Again, the various columns are (sadly) hard-coded for now.

    Usage:

        kcv = _StratifiedGroupKFoldOrchestrator(
            data=my_df,
            folds=5,
            batch_size=64
        )

        for train_dl, test_dl in kcv:
            ...
    """

    def __init__(self, data, folds: int = 5, batch_size: int = 1):
        """Initialize the K-fold CV.

        Args:
            folds (int): number of CV folds per repeat
            batch_size (int): eventual torch dataloader batch size
        """
        self.folds = folds
        self.batch_size = batch_size

        # Split the data into folds now
        lookup = data.loc[:, ["county_fip", "state_code"]].drop_duplicates()
        lookup["__fold"] = lookup.groupby("state_code")["county_fip"].transform(
            lambda c: np.arange(len(c)) % folds + 1
        )

        self.data = data.merge(lookup, on=["county_fip", "state_code"])
        assert self.data.shape[0] == data.shape[0]

    def __iter__(self) -> Generator[Tuple[DataLoader, DataLoader], None, None]:
        """Yield train and test loaders over the fold splits."""
        for ifold in range(1, 1 + self.folds):
            # Test is fold "ifold;" train is others
            train_folds = set(range(1, 1 + self.folds)).difference([ifold])
            train_ds = self._make_dataset(folds=train_folds)
            test_ds = self._make_dataset(folds=[ifold])
            yield (
                DataLoader(train_ds, batch_size=self.batch_size),
                DataLoader(test_ds, batch_size=self.batch_size),
            )

    def _make_dataset(self, folds: Iterable[int]) -> "_ABTDataset":
        """Make a dataset from a subsetted data frame."""
        sub = self.data.loc[self.data["__fold"].isin(folds), :]
        return _ABTDataset(data=sub)


class _ABTDataset(Dataset):
    """A dataset to generate output triples from the ABT.

    Usage:

        ds = _ABTDataset(data=my_df)
        X, y, w = ds[0]
        ...
    """

    def __init__(self, data: pd.DataFrame):
        """Initialize the internal rep of the dataset.

        Args:
            data (DataFrame): data from upstream, to be split into
                (X, y, weight) triples
        """
        # NB: simple imputation for infection_momentum
        self.data = data.copy()
        self.data.infection_momentum.loc[self.data.infection_momentum.isna()] = 1

    def __len__(self):
        """Length is the number of rows in the data."""
        return self.data.shape[0]

    def __getitem__(self, i) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Produce 3-tuples of features, responses, and weights."""
        z = 1 / torch.sqrt(torch.tensor(self.data.iloc[i, :]["acs_pop_total"]))
        y = torch.tensor(
            self.data.iloc[i, :][
                ["infection_target", "unemployment_target"]
            ].values.astype(float)
        )
        x = torch.tensor(
            self.data.iloc[i, :][
                [
                    "travel_limit",
                    "stay_home",
                    "educational_fac",
                    "phase_1",
                    "phase_2",
                    "phase_3",
                    "tmpf_mean",
                    "relh_mean",
                    "male_proportion",
                    "Percentage_white",
                    "young_age",
                    "mid_age",
                    "old_age",
                    "infection_penetration",
                    "infection_momentum",
                    "unemployment_rate",
                ]
            ].values.astype(float)
        )
        return (x, y, z)
