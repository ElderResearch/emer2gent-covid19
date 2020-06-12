"""Datasets and dataloaders for PyTorch."""

from typing import Generator, Iterable, Tuple

import numpy as np
import pandas as pd
import random

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
        self, srcfile: str, folds: int = 5, repeats: int = 1, seed: int = 0
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
        self.seed = seed

    def __iter__(self) -> Generator["_StratifiedGroupKFoldOrchestrator", None, None]:
        """Shuffle the dataset and produce a CV orchestrator."""

        np.random.seed(self.seed)
        random.seed(self.seed)
        random_states = random.sample(range(1000),self.repeats)

        for i in range(self.repeats):
            yield _StratifiedGroupKFoldOrchestrator(
                data=self.data.sample(frac=1, random_state=random_states[i]).copy(),
                folds=self.folds,
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

    def __init__(self, data, folds: int = 5):
        """Initialize the K-fold CV.

        Args:
            folds (int): number of CV folds per repeat
            batch_size (int): eventual torch dataloader batch size
        """
        self.folds = folds

        # Split the data into folds now
        lookup = data.loc[:, ["county_fip", "state_code"]].drop_duplicates()
        lookup["__fold"] = lookup.groupby("state_code")["county_fip"].transform(
            lambda c: np.arange(len(c)) % folds + 1
        )

        self.data = data.merge(lookup, on=["county_fip", "state_code"])
        assert self.data.shape[0] == data.shape[0]

    def __iter__(self) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """Yield train and test loaders over the fold splits."""
        for ifold in range(1, 1 + self.folds):
            # Test is fold "ifold;" train is others
            train_folds = set(range(1, 1 + self.folds)).difference([ifold])
            train_ds = self._make_dataset(folds=train_folds)
            test_ds = self._make_dataset(folds=[ifold])
            yield (
                train_ds,
                test_ds,
            )

    def _make_dataset(self, folds: Iterable[int]) -> "_ABTDataset":
        """Make a dataset from a subsetted data frame."""
        sub = self.data.loc[self.data["__fold"].isin(folds), :]
        return _ABTDataset(data=sub.copy())


class _ABTDataset():
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
        self.data = data
        self.data.loc[self.data.infection_momentum.isna(), "infection_momentum"] = 1

        # Pre-allocate tensors
        self.zmat = np.sqrt(self.data["acs_pop_total"]) / np.sum(np.sqrt(self.data["acs_pop_total"]))

        self.ymat = self.data[["infection_target", "unemployment_target"]].values.astype(float)
    
        self.xmat = self.data[
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
                    "unemployment_penetration"
                ]
            ].values.astype(float)
            

    def __len__(self):
        """Length is the number of rows in the data."""
        return self.data.shape[0]

    def __width__(self):
        """Number of features in the data"""
        return self.xmat.shape[1]

    def __getitem__(self, i) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Produce 3-tuples of features, responses, and weights."""
        return (self.xmat, self.ymat, self.zmat)
