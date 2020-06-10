import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset
import pandas as pd
import numpy as np


class Dual_Loss_Regression(nn.Module):

    def __init__(self,
                 num_features,
                 num_loss
                ):
        
        super(Dual_Loss_Regression, self).__init__()             
        
        self.num_features = num_features
        self.num_loss = num_loss
        
        # Define the network
        self.layer_1 = nn.Linear(self.num_features, self.num_loss)


    def forward(self, x):

        x = self.layer_1(x)

        return x

def call_device (
    use_cuda_if_available = True,
    parallelize_if_possible = False
    ):

    device = torch.device('cpu')
    if use_cuda_if_available:
        
        device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        
        if str(device) == 'cuda:0':
            device_used_for_training = 'GPU'
            
    print('Device used for training: ' + device_used_for_training)

    if str(device) == 'cuda:0' and parallelize_if_possible and torch.cuda.device_count() > 1:
        print('Number of GPUs used: ' + str(torch.cuda.device_count()))
            
    elif str(device) == 'cuda:0':
        print('Number of GPUs used: ' + str(1))
        
    else:
        print('Number of GPUs used: ' + str(0))

    return device

def model_exec(
            model, device,
            data_loader, # X,y,z
            data_loader_val,
            health_weight,
            econ_weight,
            learning_rate,
            num_epochs, # or do till convergance
            l2_lambda,
            save_model, 
            path_weights,
            verbose=True):

    
    optimiser = torch.optim.SGD(model.parameters(), lr=learning_rate, weight_decay=l2_lambda)
    model.to(device)
    model.train()

    for e in range(num_epochs):

        loss_tot = 0

        for i, (x, y, z) in enumerate(data_loader):
            
            x = x.float().to(device)
            y = y.float().to(device)
            z = z.float().to(device)
            
            outputs = model(x)
            
            health_pred = outputs[:,0]
            econ_pred = outputs[:,1]
            
            health_targ = y[:,0]
            econ_targ = y[:,1]
            
            loss_func = nn.MSELoss(reduction='none')
            
            health_loss = loss_func(health_pred, health_targ)*z
            health_loss = health_loss.sum()
            
            econ_loss = loss_func(econ_pred, econ_targ)*z
            econ_loss = econ_loss.sum()
            
            # Sum all loss functions for final result
            loss = health_weight*health_loss + econ_weight*econ_loss 

            optimiser.zero_grad()

            loss.backward()

            optimiser.step()
            
            loss_batch = loss.item()
            
            loss_tot += loss.item()
            
            val_loss = val_part(
                                model, device,
                                data_loader_val,
                                health_weight,
                                econ_weight,
                                save_model, 
                                path_weights
                                )
            
            if i % 1 == 0 and verbose == True:
                print(f'Batch_loss {i}: {loss_batch}')
        
        if e % 1 == 0 and verbose == True:
            print(f'Epoch: {e}, Train_Loss: {loss_tot}')
            print(f'Val_loss: {val_loss}')
            
    print(f'Epoch: {e}, Train_Loss: {loss_tot}')
    print(f'Val_loss: {val_loss}')
    
#     if save_model: torch.save(model.state_dict(), path_weights)
        
    coeffs_ = model.layer_1.weight
        
    return coeffs_

def val_part(
        model, device,
        data_loader, # X,y,z
        health_weight,
        econ_weight,
        save_model, 
        path_weights,
        verbose=True):

    model = model.to(device)
    # if save_model: model.load_state_dict(torch.load(path_weights))
    model.eval()
    
    with torch.no_grad():


        loss_tot = 0

        for i, (x, y, z) in enumerate(data_loader):
            
            x = x.float().to(device)
            y = y.float().to(device)
            z = z.float().to(device)
            
            outputs = model(x)

            health_pred = outputs[:,0]
            econ_pred = outputs[:,1]

            health_targ = y[:,0]
            econ_targ = y[:,1]

            loss_func = nn.MSELoss(reduction='none')
            
            health_loss = loss_func(health_pred, health_targ)*z
            health_loss = health_loss.sum()
            
            econ_loss = loss_func(econ_pred, econ_targ)*z
            econ_loss = econ_loss.sum()

            # Sum all loss functions for final result
            loss = health_weight*health_loss + econ_weight*econ_loss 

            loss_tot += loss.item()

    return loss_tot
