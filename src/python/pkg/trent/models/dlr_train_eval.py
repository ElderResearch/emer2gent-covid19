import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import numpy as np

from dual_loss_regression import Dual_Loss_Regression, model_exec, call_device

from pathlib import Path
data_dir = Path(__file__).resolve().parents[5] / "carl_data"

import sys
# loader_path = Path(__file__).resolve().parents[2] 
loader_path = "/Users/carl/Documents/code_repos/emer2gent-covid19/src/python/pkg/"
sys.path.append(loader_path)
from trent.abt import torch_data as td

abt = pd.read_csv(data_dir / 'ABT_C1.csv.gz', compression='gzip')

# calling gpu recources if available
use_cuda_if_available = True
parallelize_if_possible = False


num_features = 16
num_loss = 2

# dataloader decisions
REPEAT = 2
FOLDS = 5
BATCH_SIZE = 32

# create the data loader
orchestrator = td.RepeatedStratifiedGroupKFoldOrchestrator(
    "/Users/carl/Documents/code_repos/emer2gent-covid19/data/test_abt.csv", 
    repeats=REPEAT, 
    folds=FOLDS, 
    batch_size=BATCH_SIZE
)

# create the model
model = Dual_Loss_Regression(num_features, num_loss)

# Training decisions
learning_rate = 1e-4
num_epochs = 50

health_weight = 1
econ_weight = 1
l2_lambda = 0.001

save_model = True
# path to save checkpoints to
path_weights = '/Users/carl/Documents/code_repos/emer2gent-covid19/carl/model_weights/torch_weights.pth'


def execute():
    for repeat in orchestrator:
        for tr, te in repeat:
    #         X, y, z = next(iter(tr))
            coeffs_ = model_exec(
                                model,
                                tr, # X,y,z
                                te,
                                health_weight,
                                econ_weight,
                                learning_rate,
                                num_epochs, # or do till convergance
                                l2_lambda,
                                save_model, 
                                path_weights
                                )


if __name__ == "__main__":
    execute()
    
    