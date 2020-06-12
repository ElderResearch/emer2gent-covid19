import sys
from pathlib import Path

from trent.abt import sklearn_cv_data as cv_data

import numpy as np
import pandas as pd

from sklearn.multioutput import RegressorChain
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error

# paths for packages
loader_path = Path(__file__).resolve().parents[2]
sys.path.append(loader_path)

# set seed
np.random.seed(0)

# dataloader decisions
REPEAT = 10
FOLDS = 5

# create the data loader
orchestrator = cv_data.RepeatedStratifiedGroupKFoldOrchestrator(
    "/Users/carl/Documents/code_repos/emer2gent-covid19/carl_data/model_abt.csv",
    repeats=REPEAT,
    folds=FOLDS
    )

# create the model
model = Ridge(alpha=0.001, random_state=0)
 

def execute():

    health_first_repeat_dict = {}
    econ_first_repeat_dict = {}
    for i, repeat in enumerate(orchestrator): # each repetition of cv
        health_first_fold_dict = {}
        econ_first_fold_dict = {}
        for k, (tr, te) in enumerate(repeat): # each fold within a cv iteration
            
            X_train = tr[0][0]
            y_train = tr[0][1]
            z_train = tr[0][2]

            X_val = te[0][0]
            y_val = te[0][1]
            z_val = te[0][2]

            print(f'Repeat: {i}, Fold: {k}')
            run_iter = f'rpt_{i}_fold_{k}'
            # path to save checkpoints to

            # econ model adjusted for health model
            r_chain_1 = RegressorChain(
                                model, 
                                order=[0,1],
                                cv=5,
                                random_state=0
                                )
            r_chain_1.fit(X_train, y_train)
            y_pred = r_chain_1.predict(X_val)
            score = mean_squared_error(y_val, y_pred, sample_weight=z_val)
            models = r_chain_1.estimators_
            health_model_1 = models[0]
            econ_model_1 = models[1]
            

            # econ model adjusted for health model
            r_chain_2 = RegressorChain(
                                model, 
                                order=[1,0],
                                cv=5,
                                random_state=0
                                )
            r_chain_2.fit(X_train, y_train)
            y_pred = r_chain_2.predict(X_val)
            score = mean_squared_error(y_val, y_pred, sample_weight=z_val)
            models = r_chain_2.estimators_
            health_model_2 = models[1]
            econ_model_2 = models[0]
            
            health_first_fold_dict[k] = [health_model_1.coef_, econ_model_1.coef_]
            econ_first_fold_dict[k] = [health_model_2.coef_, econ_model_2.coef_]

        
        health_first_repeat_dict[i] = health_first_fold_dict
        econ_first_repeat_dict[i] = econ_first_fold_dict

    return health_first_repeat_dict, econ_first_repeat_dict



if __name__ == "__main__":
    execute()
