
import sys
from pathlib import Path

from trent.abt import torch_data as td
from trent.models.dual_loss_regression import (
    Dual_Loss_Regression,
    call_device,
    model_exec,
)

data_dir = Path(__file__).resolve().parents[5] / "carl_data"


# loader_path = ""
loader_path = Path(__file__).resolve().parents[2]
# loader_path = "/home/cnorman/code_repos/emer2gent-covid19/src/python/pkg/"
sys.path.append(loader_path)

# calling gpu recources if available
use_cuda_if_available = True
parallelize_if_possible = True

device = call_device(use_cuda_if_available, parallelize_if_possible)

num_features = 16
num_loss = 2

# dataloader decisions
REPEAT = 2
FOLDS = 5
BATCH_SIZE = 256

# create the data loader
orchestrator = td.RepeatedStratifiedGroupKFoldOrchestrator(
    # "/Users/tshafer/Projects/Trent/emer2gent-covid19/data/test_abt.csv",
    "/home/cnorman/code_repos/emer2gent-covid19/carl_data/test_abt.csv",
    repeats=REPEAT,
    folds=FOLDS,
    batch_size=BATCH_SIZE,
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
# path_weights = "/Users/tshafer/Projects/Trent/emer2gent-covid19/data/weights.pth"
path_weights = Path(
    "/Users/carl/Documents/code_repos",
    "emer2gent-covid19/carl/model_weights/torch_weights.pth",
)


def execute():
    for repeat in orchestrator:
        for tr, te in repeat:
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
                path_weights,
            )


if __name__ == "__main__":
    execute()
