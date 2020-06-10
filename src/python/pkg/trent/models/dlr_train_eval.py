import sys
from pathlib import Path

import torch
import torch.nn as nn

from trent.abt import torch_data as td
from trent.models.dual_loss_regression import (
    Dual_Loss_Regression,
    call_device,
    model_exec,
)

torch.manual_seed(0)

# loader_path = ""
loader_path = Path(__file__).resolve().parents[2]
# loader_path = "/home/cnorman/code_repos/emer2gent-covid19/src/python/pkg/"
sys.path.append(loader_path)

# calling gpu recources if available
use_cuda_if_available = True
parallelize_if_possible = True
device = call_device(use_cuda_if_available, parallelize_if_possible)

# dataloader decisions
REPEAT = 10
FOLDS = 5
BATCH_SIZE = 512

# create the data loader
orchestrator = td.RepeatedStratifiedGroupKFoldOrchestrator(
    "/Users/carl/Documents/code_repos/emer2gent-covid19/carl_data/model_abt.csv",
    repeats=REPEAT,
    folds=FOLDS,
    batch_size=BATCH_SIZE
    )


# initilise the model
num_features = 17
num_loss = 2

# create the model
model = Dual_Loss_Regression(num_features, num_loss)

# initialize weights for the model
def weights_init(m):
    if type(m) == nn.Linear:
        torch.nn.init.xavier_uniform_(m.weight)
        m.bias.data.fill_(0.01)

# Training decisions
learning_rate = 1e-3
num_epochs = 10

health_weight = 1
econ_weight = 1
l2_lambda = 0.001

save_model = True

# path to save checkpoints to
path_weights = Path(
    "/Users/carl/Documents/code_repos",
    "emer2gent-covid19/carl/model_weights/torch_weights.pth",
)


def execute():
    repeat_dict = {}
    for i, repeat in enumerate(orchestrator):
        fold_dict = {}
        for k, (tr, te) in enumerate(repeat):
            print(f'Repeat: {i}, Fold: {k}')
            model.apply(weights_init)
            coeffs_ = model_exec(
                model,
                device,
                tr,  # X,y,z
                te,
                health_weight,
                econ_weight,
                learning_rate,
                num_epochs,  # or do till convergance
                l2_lambda,
                save_model,
                path_weights
            )

            fold_dict[k] = coeffs_.numpy()
        
        repeat_dict[i] = fold_dict

    return repeat_dict



if __name__ == "__main__":
    execute()
