from random import randint

import numpy as np
import torch
from torch import optim, nn
from tqdm.auto import tqdm

import Config
import Logger
from AudioMetods import calc_coefficient, read_audio
from CudaDevice import to_cuda


def train_epoch(model: nn.Module, optimizer: optim, scheduler: optim.lr_scheduler, loss_fn: nn.Module, data_loader,
                point: int, gl_point: int, clip_val: int):
    """
        Аргументы:
            optimizer - оптимайзер
            scheduler - объкт для динамического изменения learning rate
            loss_fn - функция потерь
            data_loader - датасет для тренировки
            point - итерация
            gl_point - итерация эпохи
            clip_val - max значения для параметров для нормализации
        Вход:
            model - модель для обучения
        Выход:
            **output** (dict) - словарь со данными про SNR и ф-ию потерь
    """
    model.train()
    train_loss = 0
    train_accuracy = 0

    for mixture, target in tqdm(data_loader, desc='Train epoch'):
        logits = model(mixture)
        loss = loss_fn(logits, target.float())
        loss.backward()

        prob = torch.sigmoid(logits)
        prob = (prob > 0.5).float()
        prob_mean = float(torch.mean((prob == target).float()))
        train_accuracy += prob_mean

        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), clip_val)
        # Logger.write_grad_norm(float(torch.nn.utils.clip_grad_norm_(model.parameters(), clip_val)), point)
        optimizer.step()

        # Logger.write_lr(scheduler.get_last_lr(), point)
        scheduler.step()
        optimizer.zero_grad()

        train_loss += loss.item()

        # Logger.write_point('train', point, loss.item(), prob_mean)

        Logger.write_point('Train/grad_norm', grad_norm.item(), point)
        Logger.write_point('Train/lr', scheduler.get_last_lr()[0], point)
        Logger.write_point('Train/Loss', loss.item(), point)
        Logger.write_point('Train/Accuracy', prob_mean, point)

        point += 1
    n = len(data_loader)
    train_loss /= n
    train_accuracy /= n

    # Logger.write_epoch_point('train_epoch', gl_point, train_loss, train_accuracy)
    Logger.write_point('Train/Locc_epoch', train_loss, gl_point)
    Logger.write_point('Train/Accuracy_epoch', train_accuracy, gl_point)
    return {
        "train_loss": train_loss,
        "train_accuracy": train_accuracy
    }


@torch.no_grad()
def val_epoch(model, data_loader, loss_fn, point: int, gl_point: int):
    """
        Аргументы:
            loss_fn - функция потерь
            data_loader - реальный датасет
            point - итерация
            gl_point - итерация эпохи
        Вход:
            model - модель для обучения
        Выход:
            **output** (dict) - словарь со данными про SNR и ф-ию потерь
    """
    model.eval()
    val_loss = 0
    val_accuracy = 0
    for mixture, target in tqdm(data_loader, desc='Val epoch'):
        logits = model(mixture)
        loss = loss_fn(logits, target.float())
        val_loss += loss.item()
        prob = torch.sigmoid(logits)
        prob = (prob > 0.5).float()
        prob_mean = float(torch.mean((prob == target).float()))
        val_accuracy += prob_mean

        # Logger.write_point('eval', point, loss.item(), prob_mean)
        Logger.write_point('Val/Loss', loss.item(), point)
        Logger.write_point('Val/Accuracy', prob_mean, point)

        point += 1
    n = len(data_loader)
    val_loss /= n
    val_accuracy /= n
    # Logger.write_epoch_point('eval_epoch', gl_point, val_loss, val_accuracy)
    Logger.write_point('Val/Locc_epoch', val_loss, gl_point)
    Logger.write_point('Val/Accuracy_epoch', val_accuracy, gl_point)
    return {
        "val_loss": val_loss,
        "val_accuracy": val_accuracy
    }


def train(model, optimizer, scheduler, loss_fn, data_loader_train, data_loader_val, dataset_valid, epochs, save_path,
          clip_val: int):
    """
        Аргументы:
            optimizer - оптимайзер
            scheduler - объкт для динамического изменения learning rate
            loss_fn - функция потерь
            data_loader_train - датасет для тренировки
            data_loader_vak - датасет для оценки решения
            epochs - кол-во эпох
            save_path - куда сохранять путь
            clip_val - max значения для параметров для нормализации
        Вход:
            model - модель для обучения
        Выход:
            ничего
    """
    # save_path .tar
    logs = {
        "train_loss": [],
        "train_accuracy": [],
        "val_loss": [],
        "val_accuracy": []
    }

    print('Training...')
    for epoch in tqdm(range(epochs), desc='Training...'):
        cur_train = train_epoch(model, optimizer, scheduler, loss_fn, data_loader_train, epoch * Config.iters_per_epoch,
                                epoch, clip_val)
        cur_val = val_epoch(model, data_loader_val, loss_fn, epoch * Config.iters_per_epoch, epoch)
        # for _ in range(3):
        #     test(model, dataset_valid, 'epoch_' + str(epoch))

        logs["train_loss"].append(cur_train["train_loss"])
        logs["train_accuracy"].append(cur_train["train_accuracy"])

        logs["val_loss"].append(cur_val["val_loss"])
        logs["val_accuracy"].append(cur_val["val_accuracy"])

        snapshot = {
            "model": model.state_dict(),
            "optimizer": optimizer.state_dict(),
            "logs": logs,
        }
        # print('Loss', cur_val["val_loss"])

        print()
        print()
        for key, value in logs.items():
            print(f'{key} = {value[-1]:.3f}')
        print()
        print()

        torch.save(snapshot, save_path)


def test(model, dataset, i: str):
    f = dataset.clean_dataset.audio_paths[randint(0, len(dataset.clean_dataset.audio_paths) - 1)]
    audio = read_audio(f)[0]
    # ashow(audio)

    f = dataset.noise_dataset.audio_paths[randint(0, len(dataset.noise_dataset.audio_paths) - 1)]
    noise = read_audio(f)[0]
    while len(noise) < len(audio):
        noise = np.concatenate((noise, noise))
    noise = noise[:len(audio)]

    mixture = audio + calc_coefficient(audio, noise, 2) * noise
    Logger.save_audio(torch.from_numpy(mixture), str(i) + '_mix')
    # ashow(mixture)

    mixture = torch.from_numpy(mixture)
    mixture = to_cuda(mixture)

    model.eval()
    wave = model(mixture[None])[0]
    Logger.save_audio(wave.cpu().detach(), str(i) + '_wave')
    # ashow(wave.cpu().detach().numpy())
