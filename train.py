# -*- coding: utf-8 -*-

import os
import argparse
import torch.nn as nn
from tqdm import tqdm
from torch.utils.data import DataLoader
from MelonDataset import SongTagDataset, SongTagDataset_with_WE, SongDataset
from Models import *
from data_util import *
from arena_util import write_json
from evaluate import ArenaEvaluator


def train_type0(train_dataset, id2prep_song_file_path, question_dataset, answer_file_path, model_file_path):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    id2prep_song_dict = dict(np.load(id2prep_song_file_path, allow_pickle=True).item())

    # parameters
    num_songs = train_dataset.num_songs

    # hyper parameters
    D_in = D_out = num_songs

    evaluator = ArenaEvaluator()
    data_loader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size, num_workers=num_workers)

    model = AutoEncoder(D_in, H, D_out, dropout=dropout).to(device)

    testevery = 5

    parameters = model.parameters()
    loss_func = nn.BCELoss()
    optimizer = torch.optim.Adam(parameters, lr=learning_rate)

    try:
        model = torch.load(model_file_path)
        print("\n--------model restored--------\n")
    except:
        print("\n--------model not restored--------\n")
        pass

    temp_fn = 'arena_data/answers/temp.json'
    if os.path.exists(temp_fn):
        os.remove(temp_fn)

    for epoch in range(epochs):
        print()
        print('epoch: ', epoch)
        running_loss = 0.0
        for idx, (_id, _data) in enumerate(tqdm(data_loader, desc='training...')):
            _data = _data.to(device)
            optimizer.zero_grad()
            output = model(_data)
            loss = loss_func(output, _data)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        print('loss: %d %d%% %.4f' % (epoch, epoch / epochs * 100, running_loss))

        torch.save(model, model_file_path)

        if not submit:
            qestion_data_loader = DataLoader(question_dataset, shuffle=True, batch_size=batch_size,
                                             num_workers=num_workers)
            tags_dummy = ['_', '!', '@', '#', '$', '%', '&', '*', '(', ')']
            if epoch % testevery == 0:
                elements = []
                for idx, (_id, _data) in enumerate(tqdm(qestion_data_loader, desc='testing...')):
                    with torch.no_grad():
                        _data = _data.to(device)
                        output = model(_data)
                        _id = list(map(int, _id))
                        songs_ids = binary_songs2ids(_data, output, id2prep_song_dict)
                        for i in range(len(_id)):
                            element = {'id': _id[i], 'songs': list(songs_ids[i]), 'tags': tags_dummy}
                            elements.append(element)

                write_json(elements, temp_fn)
                evaluator.evaluate(answer_file_path, temp_fn)
                os.remove(temp_fn)


def train_type1(train_dataset, id2prep_song_file_path, id2tag_file_path,
                question_dataset, answer_file_path, model_file_path, song_only=False):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    id2tag_dict = dict(np.load(id2tag_file_path, allow_pickle=True).item())
    id2prep_song_dict = dict(np.load(id2prep_song_file_path, allow_pickle=True).item())

    # parameters
    num_songs = train_dataset.num_songs
    num_tags = train_dataset.num_tags

    # hyper parameters
    D_in = num_songs + num_tags
    if song_only:
        D_out = num_songs
    else:
        D_out = num_songs + num_tags

    evaluator = ArenaEvaluator()
    data_loader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size, num_workers=num_workers)

    model = AutoEncoder(D_in, H, D_out, dropout=dropout).to(device)

    testevery = 5

    parameters = model.parameters()
    loss_func = nn.BCELoss()
    optimizer = torch.optim.Adam(parameters, lr=learning_rate)

    try:
        model = torch.load(model_file_path)
        print("\n--------model restored--------\n")
    except:
        print("\n--------model not restored--------\n")
        pass

    temp_fn = 'arena_data/answers/temp.json'
    if os.path.exists(temp_fn):
        os.remove(temp_fn)

    for epoch in range(epochs):
        print()
        print('epoch: ', epoch)
        running_loss = 0.0
        for idx, (_id, _data) in enumerate(tqdm(data_loader, desc='training...')):
            _data = _data.to(device)

            optimizer.zero_grad()
            output = model(_data)
            if song_only:
                _songs, _ = torch.split(_data, num_songs, dim=1)
                loss = loss_func(output, _songs)
            else:
                loss = loss_func(output, _data)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        print('loss: %d %d%% %.4f' % (epoch, epoch / epochs * 100, running_loss))

        torch.save(model, model_file_path)

        if not submit:
            qestion_data_loader = DataLoader(question_dataset, shuffle=True, batch_size=batch_size,
                                             num_workers=num_workers)
            if epoch % testevery == 0:
                elements = []
                for idx, (_id, _data) in enumerate(tqdm(qestion_data_loader, desc='testing...')):
                    with torch.no_grad():
                        _data = _data.to(device)
                        output = model(_data)

                        songs_input, tags_input = torch.split(_data, num_songs, dim=1)
                        if not song_only:
                            songs_output, tags_output = torch.split(output, num_songs, dim=1)
                            songs_ids = binary_songs2ids(songs_input, songs_output, id2prep_song_dict)
                        else:
                            songs_ids = binary_songs2ids(songs_input, output, id2prep_song_dict)

                        if not song_only:
                            tag_ids = binary_tags2ids(tags_input, tags_output, id2tag_dict)
                        else:
                            tag_ids = [['_', '!', '@', '#', '$', '%', '&', '*', '(', ')']]*batch_size

                        _id = list(map(int, _id))
                        for i in range(len(_id)):
                            element = {'id': _id[i], 'songs': list(songs_ids[i]), 'tags': tag_ids[i]}
                            elements.append(element)

                write_json(elements, temp_fn)
                evaluator.evaluate(answer_file_path, temp_fn)
                os.remove(temp_fn)


def train_type2(train_dataset, id2prep_song_file_path, id2tag_file_path,
                question_dataset, answer_file_path, model_file_path):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    id2tag_dict = dict(np.load(id2tag_file_path, allow_pickle=True).item())
    id2prep_song_dict = dict(np.load(id2prep_song_file_path, allow_pickle=True).item())

    # parameters
    num_songs = train_dataset.num_songs
    num_tags = train_dataset.num_tags

    # hyper parameters
    D_in = num_songs + num_tags

    evaluator = ArenaEvaluator()
    data_loader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size, num_workers=num_workers)

    model = AutoEncoder_var_song_only(D_in, H, num_songs, dropout=dropout).to(device)

    testevery = 5

    parameters = model.parameters()
    loss_func = nn.BCELoss()
    optimizer = torch.optim.Adam(parameters, lr=learning_rate)

    try:
        model = torch.load(model_file_path)
        print("\n--------model restored--------\n")
    except:
        print("\n--------model not restored--------\n")
        pass

    temp_fn = 'arena_data/answers/temp.json'
    if os.path.exists(temp_fn):
        os.remove(temp_fn)

    for epoch in range(epochs):
        print()
        print('epoch: ', epoch)
        running_loss = 0.0
        for idx, (_id, _data) in enumerate(tqdm(data_loader, desc='training...')):
            optimizer.zero_grad()
            _data = _data.to(device)
            out = model(_data)
            songs_label, _ = torch.split(_data, num_songs, dim=1)
            loss = loss_func(out, songs_label)
            loss.backward()
            optimizer.step()

            running_loss += loss.item()

        print('loss: %d %d%% %.4f' % (epoch, epoch / epochs * 100, running_loss))

        torch.save(model, model_file_path)

        if not submit:
            qestion_data_loader = DataLoader(question_dataset, shuffle=True, batch_size=batch_size,
                                             num_workers=num_workers)
            tags_dummy = ['_', '!', '@', '#', '$', '%', '&', '*', '(', ')']
            if epoch % testevery == 0:
                elements = []
                for idx, (_id, _data) in enumerate(tqdm(qestion_data_loader, desc='testing...')):
                    with torch.no_grad():
                        _data = _data.to(device)

                        songs_input, tags_input = torch.split(_data, num_songs, dim=1)
                        out = model(_data)

                        songs_ids = binary_songs2ids(songs_input, out, id2prep_song_dict)

                        _id = list(map(int, _id))
                        for i in range(len(_id)):
                            element = {'id': _id[i], 'songs': list(songs_ids[i]), 'tags': tags_dummy}
                            elements.append(element)

                write_json(elements, temp_fn)
                evaluator.evaluate(answer_file_path, temp_fn)
                os.remove(temp_fn)


def train_type3(train_dataset, id2prep_song_file_path, id2tag_file_path,
                question_dataset, answer_file_path, model_file_path):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    id2tag_dict = dict(np.load(id2tag_file_path, allow_pickle=True).item())
    id2prep_song_dict = dict(np.load(id2prep_song_file_path, allow_pickle=True).item())

    # parameters
    num_songs = train_dataset.num_songs
    num_tags = train_dataset.num_tags

    # hyper parameters
    D_in = num_songs + num_tags

    evaluator = ArenaEvaluator()
    data_loader = DataLoader(train_dataset, shuffle=True, batch_size=batch_size, num_workers=num_workers)

    model = AutoEncoder_var(D_in, H, num_songs, num_tags, dropout=dropout).to(device)

    testevery = 5

    parameters = model.parameters()
    loss_func1 = nn.BCELoss()
    loss_func2 = nn.BCELoss()
    optimizer = torch.optim.Adam(parameters, lr=learning_rate)

    try:
        model = torch.load(model_file_path)
        print("\n--------model restored--------\n")
    except:
        print("\n--------model not restored--------\n")
        pass

    temp_fn = 'arena_data/answers/temp.json'
    if os.path.exists(temp_fn):
        os.remove(temp_fn)

    for epoch in range(epochs):
        print()
        print('epoch: ', epoch)
        running_loss = 0.0
        for idx, (_id, _data) in enumerate(tqdm(data_loader, desc='training...')):
            optimizer.zero_grad()
            _data = _data.to(device)
            output1, output2 = model(_data)
            songs_label, tags_label = torch.split(_data, num_songs, dim=1)
            loss1 = loss_func1(output1, songs_label)
            loss2 = loss_func2(output2, tags_label)
            loss1.backward()
            loss2.backward()
            optimizer.step()

            running_loss += loss1.item() + loss2.item()

        print('loss: %d %d%% %.4f' % (epoch, epoch / epochs * 100, running_loss))

        torch.save(model, model_file_path)

        if not submit:
            qestion_data_loader = DataLoader(question_dataset, shuffle=True, batch_size=batch_size,
                                             num_workers=num_workers)
            if epoch % testevery == 0:
                elements = []
                for idx, (_id, _data) in enumerate(tqdm(qestion_data_loader, desc='testing...')):
                    with torch.no_grad():
                        _data = _data.to(device)

                        songs_input, tags_input = torch.split(_data, num_songs, dim=1)
                        songs_output, tags_output = model(_data)

                        songs_ids = binary_songs2ids(songs_input, songs_output, id2prep_song_dict)
                        tag_ids = binary_tags2ids(tags_input, tags_output, id2tag_dict)

                        _id = list(map(int, _id))
                        for i in range(len(_id)):
                            element = {'id': _id[i], 'songs': list(songs_ids[i]), 'tags': tag_ids[i]}
                            elements.append(element)

                write_json(elements, temp_fn)
                evaluator.evaluate(answer_file_path, temp_fn)
                os.remove(temp_fn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-model_type', type=int, help="model selection 0 to 3", default=1)
    parser.add_argument('-dimension', type=int, help="hidden layer dimension", default=100)
    parser.add_argument('-epochs', type=int, help="total epochs", default=10)
    parser.add_argument('-batch_size', type=int, help="batch size", default=256)
    parser.add_argument('-learning_rate', type=float, help="learning rate", default=0.001)
    parser.add_argument('-dropout', type=float, help="dropout", default=0.0)
    parser.add_argument('-num_workers', type=int, help="num workers", default=4)
    parser.add_argument('-prep_method', type=int, help="data preprocessing method, 'frequency':0 'like_cnt':1", default=0)
    parser.add_argument('-prep_method_thr', type=float, help="'frequency':0 < number 'like_cnt': 0~1 float", default=2)
    parser.add_argument('-submit', type=int, help="arena_data/orig: 0 res: 1", default=0)

    args = parser.parse_args()
    print(args)

    model_type = args.model_type
    H = args.dimension
    epochs = args.epochs
    batch_size = args.batch_size
    learning_rate = args.learning_rate
    dropout = args.dropout
    num_workers = args.num_workers
    prep_method = args.prep_method
    prep_method_thr = args.prep_method_thr
    if prep_method == 0:
        prep_method_thr = int(prep_method_thr)
    submit = args.submit

    if submit:
        default_file_path = 'res'
        question_file_path = 'res/val.json'
        model_postfix = 'sub'
    else:
        default_file_path = 'arena_data/orig'
        question_file_path = 'arena_data/questions/sample_val.json'
        model_postfix = ' '

    train_file_path = f'{default_file_path}/train.json'

    answer_file_path = 'arena_data/answers/sample_val.json'

    tag2id_file_path = f'{default_file_path}/tag2id.npy'
    id2tag_file_path = f'{default_file_path}/id2tag.npy'

    prep_methods = ['freq_song', 'liked_song']
    prep_song2id_file_path = f'{default_file_path}/{prep_methods[prep_method]}2id_thr{prep_method_thr}.npy'
    id2prep_song_file_path = f'{default_file_path}/id2{prep_methods[prep_method]}_thr{prep_method_thr}.npy'

    if not (os.path.exists(tag2id_file_path) & os.path.exists(id2tag_file_path)):
        tags_ids_convert(train_file_path, tag2id_file_path, id2tag_file_path)

    if model_type == 0:
        model_file_path = 'model/autoencoder0_{}_{}_{}_{}_{}_{}_{}.pkl'.\
            format(H, batch_size, learning_rate, dropout, prep_method, prep_method_thr, model_postfix)

        train_dataset = SongDataset(train_file_path, prep_song2id_file_path)
        question_dataset = SongDataset(question_file_path, prep_song2id_file_path)

        train_type0(train_dataset, id2prep_song_file_path, question_dataset, answer_file_path, model_file_path)
    if model_type == 1:
        model_file_path = 'model/autoencoder_{}_{}_{}_{}_{}_{}_{}.pkl'. \
            format(H, batch_size, learning_rate, dropout, prep_method, prep_method_thr, model_postfix)

        train_dataset = SongTagDataset(train_file_path, tag2id_file_path, prep_song2id_file_path)
        question_dataset = SongTagDataset(question_file_path, tag2id_file_path, prep_song2id_file_path)

        train_type1(train_dataset, id2prep_song_file_path, id2tag_file_path,
                    question_dataset, answer_file_path, model_file_path)
    elif model_type == 2:
        model_file_path = 'model/autoencoder_var_song_only_{}_{}_{}_{}_{}_{}_{}.pkl'. \
            format(H, batch_size, learning_rate, dropout, prep_method, prep_method_thr, model_postfix)

        train_dataset = SongTagDataset(train_file_path, tag2id_file_path, prep_song2id_file_path)
        question_dataset = SongTagDataset(question_file_path, tag2id_file_path, prep_song2id_file_path)

        train_type2(train_dataset, id2prep_song_file_path, id2tag_file_path,
                    question_dataset, answer_file_path, model_file_path)
    elif model_type == 3:
        model_file_path = 'model/autoencoder_var_{}_{}_{}_{}_{}_{}_{}.pkl'. \
            format(H, batch_size, learning_rate, dropout, prep_method, prep_method_thr, model_postfix)

        train_dataset = SongTagDataset(train_file_path, tag2id_file_path, prep_song2id_file_path)
        question_dataset = SongTagDataset(question_file_path, tag2id_file_path, prep_song2id_file_path)

        train_type3(train_dataset, id2prep_song_file_path, id2tag_file_path,
                    question_dataset, answer_file_path, model_file_path)

    print('train completed')
