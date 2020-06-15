import sys
from pathlib import Path

from trent.abt import sklearn_cv_data as cv_data

import numpy as np
import pandas as pd

from sklearn.multioutput import RegressorChain
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error

import matplotlib.pyplot as plt
import seaborn as sns

# paths for packages
loader_path = Path(__file__).resolve().parents[2]
sys.path.append(loader_path)

 
class Regressor_Chain():

        def __init__(
        self, srcfile: str, folds: int = 5, repeats: int = 1, seed: int = 0, l2_lambda: float = 0.001, verbose: bool=False
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
            self.l2_lambda = l2_lambda
            self.verbose = verbose

            # create the model
            self.model = Ridge(alpha=self.l2_lambda, random_state=self.seed)

            # set seed
            np.random.seed(self.seed)

            # data loader initialisation
            self.orchestrator = orchestrator = cv_data.RepeatedStratifiedGroupKFoldOrchestrator(
                "/Users/carl/Documents/code_repos/emer2gent-covid19/data/model_abt.csv", # TODO: need to update for final ABT location
                repeats=self.repeats,
                folds=self.folds,
                )
            self.features, self.num_features  = cv_data.abt_info()



        # run model for data above:
        def execute(self):

            health_first_repeat_dict = {}
            econ_first_repeat_dict = {}
            for i, repeat in enumerate(self.orchestrator): # each repetition of cv
                health_first_fold_dict = {}
                econ_first_fold_dict = {}
                for k, (tr, te) in enumerate(repeat): # each fold within a cv iteration
                    
                    X_train = tr[0][0]
                    y_train = tr[0][1]
                    z_train = tr[0][2]

                    X_val = te[0][0]
                    y_val = te[0][1]
                    z_val = te[0][2]

                    run_iter = f'rpt_{i}_fold_{k}'
                    # path to save checkpoints to

                    # econ model adjusted for health model
                    r_chain_1 = RegressorChain(
                                        self.model, 
                                        order=[0,1],
                                        cv=5,
                                        random_state=self.seed
                                        )

                    r_chain_1.fit(X_train, y_train)
                    y_pred = r_chain_1.predict(X_val)
                    score_1 = mean_squared_error(y_val, y_pred, sample_weight=z_val)
                    models = r_chain_1.estimators_
                    health_model_1 = models[0]
                    econ_model_1 = models[1]
                    

                    # econ model adjusted for health model
                    r_chain_2 = RegressorChain(
                                        self.model, 
                                        order=[1,0],
                                        cv=5,
                                        random_state=self.seed
                                        )
                    r_chain_2.fit(X_train, y_train)
                    y_pred = r_chain_2.predict(X_val)
                    score_2 = mean_squared_error(y_val, y_pred, sample_weight=z_val)
                    models = r_chain_2.estimators_
                    health_model_2 = models[1]
                    econ_model_2 = models[0]

                    if self.verbose: print(f'Repeat: {i}, Fold: {k}, Validation Results: Model_1: {score_1}, Model_2: {score_2}')
                    
                    health_first_fold_dict[k] = [health_model_1.coef_, econ_model_1.coef_]
                    econ_first_fold_dict[k] = [health_model_2.coef_, econ_model_2.coef_]

                
                health_first_repeat_dict[i] = health_first_fold_dict
                econ_first_repeat_dict[i] = econ_first_fold_dict

            return health_first_repeat_dict, econ_first_repeat_dict

        def graph_builder(
                        self, 
                        health_first_repeat_dict, 
                        econ_first_repeat_dict, 
                        height: float=1.25, 
                        aspect: float=8, 
                        low_lim: float=-5, 
                        high_lim: float=10,
                        plot=1,
                        save=False
                        ):

            run = [f'Run {i}' for i in range(self.repeats*self.folds)]

            # MODEL 1:
            if plot == 1 or plot == 2:
                # select the health first model and format the coeffs for use in graphs
                health_first_coeffs = [health_first_repeat_dict[i][j] for i in range(self.repeats) for j in range(self.folds)]
                health_coeffs_1 = np.array([item[0] for item in health_first_coeffs])
                econ_coeffs_1 = np.array([item[1] for item in health_first_coeffs])
                econ_coeffs_1 = econ_coeffs_1[:,:self.num_features] # want only the feature coefficients, ignores the other target dependent coeff 
    
                # create dataframe of all model runs and select the order based on median
                health_df_1 = pd.DataFrame(health_coeffs_1, index=run, columns=self.features)
                health_order_1 = health_df_1.describe().loc['50%',:].sort_values(ascending=False).index.tolist()
                econ_df_1 = pd.DataFrame(econ_coeffs_1, index=run, columns=self.features)
                econ_order_1 = econ_df_1.describe().loc['50%',:].sort_values(ascending=False).index.tolist()

                # reshape dataframes for plotting distribution graphs
                health_df_1 = pd.melt(health_df_1, value_vars=self.features, var_name='feature', value_name='coeff_value')
                econ_df_1 = pd.melt(econ_df_1, value_vars=self.features, var_name='feature', value_name='coeff_value')

                if plot == 1:
                    # create graphs for model_1
                    g_health_1 = sns.FacetGrid(health_df_1, row="feature", row_order=health_order_1,
                        height=height, aspect=aspect, xlim=(low_lim, high_lim))
                    g_health_1.map(sns.distplot, 'coeff_value', rug=True, hist=False, color="grey", kde_kws={"shade": True})

                    plt.subplots_adjust(top=0.95)
                    g_health_1.fig.suptitle('Health Feature Coefficients, Economic dependent on Health Output')  

                    if save: plt.savefig('/Users/carl/Documents/code_repos/emer2gent-covid19/data/result_graphs/health_1.png')

                    plt.show()
                
                elif plot == 2:
                    g_econ_1 = sns.FacetGrid(econ_df_1, row="feature", row_order=econ_order_1,
                        height=height, aspect=aspect, xlim=(low_lim, high_lim))
                    g_econ_1.map(sns.distplot, 'coeff_value', rug=True, hist=False, color="grey", kde_kws={"shade": True})

                    plt.subplots_adjust(top=0.95)
                    g_econ_1.fig.suptitle('Economic Feature Coefficients, Economic dependent on Health Output')  

                    if save: plt.savefig('/Users/carl/Documents/code_repos/emer2gent-covid19/data/result_graphs/econ_1.png')

                    plt.show()


            # MODEL 2:
            elif plot == 3 or plot == 4:

                # select the health first model and format the coeffs for use in graphs
                econ_first_coeffs = [econ_first_repeat_dict[i][j] for i in range(self.repeats) for j in range(self.folds)]
                health_coeffs_2 = np.array([item[0] for item in econ_first_coeffs])
                health_coeffs_2 = health_coeffs_2[:,:self.num_features] # want only the feature coefficients, ignores the other target dependent coeff 
                econ_coeffs_2 = np.array([item[1] for item in econ_first_coeffs])


                # create dataframe of all model runs and select the order based on median
                health_df_2 = pd.DataFrame(health_coeffs_2, index=run, columns=self.features)
                health_order_2 = health_df_2.describe().loc['50%',:].sort_values(ascending=False).index.tolist()
                econ_df_2 = pd.DataFrame(econ_coeffs_2, index=run, columns=self.features)
                econ_order_2 = econ_df_2.describe().loc['50%',:].sort_values(ascending=False).index.tolist()

                # reshape dataframes for plotting distribution graphs
                health_df_2 = pd.melt(health_df_2, value_vars=self.features, var_name='feature', value_name='coeff_value')
                econ_df_2 = pd.melt(econ_df_2, value_vars=self.features, var_name='feature', value_name='coeff_value')

                # create graphs for model_1

                if plot == 3:
                    g_health_2 = sns.FacetGrid(health_df_2, row="feature", row_order=health_order_2,
                        height=height, aspect=aspect, xlim=(low_lim, high_lim))
                    g_health_2.map(sns.distplot, 'coeff_value', rug=True, hist=False, color="grey", kde_kws={"shade": True})

                    plt.subplots_adjust(top=0.95)
                    g_health_2.fig.suptitle('Health Feature Coefficients, Health dependent on Economic Output')  

                    if save: plt.savefig('/Users/carl/Documents/code_repos/emer2gent-covid19/data/result_graphs/health_2.png')

                    plt.show()

                elif plot == 4:
                    g_econ_2 = sns.FacetGrid(econ_df_2, row="feature", row_order=econ_order_2,
                        height=height, aspect=aspect, xlim=(low_lim, high_lim))
                    g_econ_2.map(sns.distplot, 'coeff_value', rug=True, hist=False, color="grey", kde_kws={"shade": True})

                    plt.subplots_adjust(top=0.95)
                    g_econ_2.fig.suptitle('Economic Feature Coefficients, Health dependent on Economic Output')  

                    if save: plt.savefig('/Users/carl/Documents/code_repos/emer2gent-covid19/data/result_graphs/econ_2.png')

                    plt.show()


            else: print('Plot chosen not available')
            


if __name__ == "__main__":
    execute()
