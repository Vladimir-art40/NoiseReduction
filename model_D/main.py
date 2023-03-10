import torch
from torch import nn
from torch.utils.data import DataLoader

import Config
from ConformerDetector import ConformerDetector
from CudaDevice import CudaDataLoader, to_cuda
from NetMetods import train, test
from Sheduler import StepLRWithWarmup
from datasets.MixDataset import MixDataset

# wget https://www.openslr.org/resources/17/musan.tar.gz
# wget https://www.openslr.org/resources/12/train-clean-100.tar.gz
# pip3 install torch torchvision torchaudio --extra-index-url https://download.pytorch.org/whl/cu116
# tar -xf musan.tar.gz
# tar -xf train-clean-100.tar.gz

if __name__ == '__main__':
    print(torch.__version__)

    dataset_train = MixDataset(Config.snr_range, Config.iters_per_epoch * Config.batch_size)
    dataset_eval = MixDataset(Config.snr_range, Config.iters_per_epoch * Config.batch_size,
                              noise_pattern_=Config.noise_eval_pattern)

    data_loader_train = DataLoader(dataset_train, batch_size=Config.batch_size, shuffle=False)
    data_loader_valid = DataLoader(dataset_eval, batch_size=Config.batch_size, shuffle=False)

    data_loader_train = CudaDataLoader(data_loader_train)
    data_loader_valid = CudaDataLoader(data_loader_valid)

    loss_fn = nn.BCEWithLogitsLoss()

    model = ConformerDetector(Config.size, Config.conf_blocks_num, Config.conv_kernel_size, 1, Config.w_len,
                              Config.w_len // 2)

    to_cuda(model)

    optimizer = torch.optim.Adam(model.parameters(), lr=Config.opt_lr)

    scheduler = StepLRWithWarmup(optimizer, step_size=Config.step_size, gamma=Config.gamma,
                                 warmup_epochs=Config.warmup_iters, warmup_lr_init=Config.start_lr,
                                 min_lr=Config.min_lr)

    train(model, optimizer, scheduler, loss_fn,
          data_loader_train, data_loader_valid, dataset_eval,
          Config.epochs, Config.save_path, Config.clip_val)

    for i in range(10):
        test(model, dataset_eval, 'finish_' + str(i))

    while True:
        if input() == 'finish':
            break
