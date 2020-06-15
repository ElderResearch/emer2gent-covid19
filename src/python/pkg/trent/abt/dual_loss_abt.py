"""Transform abt_prepped file to form for use in the regression_chain dataloader."""

import numpy as np
import pandas as pd
import random

features = [
    "travel_limit",
    "stay_home",
    "educational_fac",
    "phase_1",
    "phase_2",
    "phase_3",
    "tmpf_mean",
    "relh_mean",
    "acs_gender_female",
    "acs_race_minority",
    "young_age",
    "old_age",
    "pop_density", 
    "cov_testing_pos_prop"
]

weights = [
    "acs_pop_total"
]

targets = [
    'infection_7day_pct_delta',
    'unemployment_pct_delta'
]

gen_info = [
    "date", "county_fip", "state_code", "state", "county"
]

age_young = [
            'acs_age_25_34','acs_age_35_44','acs_age_45_54','acs_age_55_64'
            ]

age_old = [
            'acs_age_65_74','acs_age_75_84','acs_age_85_ge'
            ]

all_age = ['acs_age_le_24'] + age_young + age_old


class ABT_transform():

    """
    Read-in ABT prepped
    Remove unecessary columns
    
    """

    def __init__(
        self, srcfile: str, date_cutoff: str
    ):
        """Initialize the orchestrator.

        Args:
            srcfile (str): path to the ABT CSV
            folds (int): number of CV folds per repeat
            repeats (int): number of repeats, shuffling each time
            batch_size (int): eventual pandas dataloader batch size
        """
        # Load the data
        self.data = pd.read_csv(srcfile)
        self.date_cutoff = date_cutoff

    def create_abt(self):

        abt = self.data.copy()

        abt = self.age_apply(abt)
        abt = self.policy_apply(abt)
        abt = self.testing_apply(abt)
        abt = self.remove_records(abt)
        abt = self.scaling(abt)
        abt = self.column_select(abt)

        assert abt.isna().sum().sum() == 0, 'Some nans remain'      

        # save final abt to data folder
        abt.to_csv("/Users/carl/Documents/code_repos/emer2gent-covid19/data/model_abt.csv") # TODO: need to update for final ABT location

        return abt


    def age_apply(self, abt):

        abt['young_age'] = abt[age_young].sum(axis=1) / abt[all_age].sum(axis=1)
        abt['old_age'] = abt[age_old].sum(axis=1) / abt[all_age].sum(axis=1)

        return abt

    def policy_apply(self, abt):

        policy_map = {
            'None Issued':0, 
            '0':0, 
            '1':1, 
            0:0, 
            1:1
        }

        abt['travel_limit'] = abt['travel_limit'].map(policy_map)
        abt['stay_home'] = abt['stay_home'].map(policy_map)
        abt['educational_fac'] = abt['educational_fac'].map(policy_map)
        abt['phase_1'] = abt['phase_1'].map(policy_map)
        abt['phase_2'] = abt['phase_2'].map(policy_map)
        abt['phase_3'] = abt['phase_3'].map(policy_map)

        return abt

    def testing_apply(self, abt):
        # abt['state_pop'] = abt.groupby(['state_code','date'])['acs_pop_total'].transform(np.sum)
        # abt['state_pop'] = abt.groupby('state_code')['state_pop'].transform(np.max)
        abt['cov_testing_pos_prop'] = abt['cov_pos_tests'] / abt['cov_total_tests']
        # abt.drop(columns=['state_pop'],inplace=True)
        return abt

    def remove_records(self, abt):

        # infections have started for a county
        abt = abt.loc[abt.confirmed!=0]

        # after specified date cutoff
        abt = abt.loc[abt['date']>=self.date_cutoff]

        # for dates don't have labour data for
        abt = abt.loc[~abt['unemployment_pct_delta'].isna()]

        return abt

    def column_select(self, abt):

        all_cols = gen_info + features + weights + targets
        abt = abt[all_cols]

        return abt

    def scaling(self, abt):

        # temperature and humidity scaling
        abt['tmpf_mean'] = abt.groupby(['county_fip'])['tmpf_mean'].transform(lambda x: (x-x.min())/(x.max()-x.min())).fillna(0.5)
        abt['relh_mean'] = abt.groupby(['county_fip'])['relh_mean'].transform(lambda x: (x-x.min())/(x.max()-x.min())).fillna(0.5)

        # log and global scale of pop density
        abt['pop_density'] = abt['pop_density'].apply(lambda x: np.log(x))
        abt['pop_density'] = abt['pop_density'].transform(lambda x: (x-x.min())/(x.max()-x.min()))

        return abt









                


