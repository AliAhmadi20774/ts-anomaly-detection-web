"""
Dataset class for loading time series signals.

This module provides a custom PyTorch Dataset class that
prepares time series data for use with DataLoader.

Classes:
    AirbusData: Dataset class for batch loading of signals
"""

import torch
import pandas as pd
from torch.utils.data import Dataset
import numpy as np
        

class AirbusData(Dataset):
    def __init__(self, data):
        self.data = torch.as_tensor(data, dtype=torch.float32)

    def __len__(self):
        return self.data.shape[0]

    def __getitem__(self, idx):
        return self.data[idx]