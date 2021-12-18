"""
Author: Ce Li
"""
import sys
import os
BASE_PATH = os.path.abspath(os.path.join(os.getcwd()))
sys.path.append(BASE_PATH)
import pickle
import tensorflow as tf
from tools import Generator
import config


with open(config.a_x, 'rb') as f:
    x = pickle.load(f)

with open(config.a_x_authors, 'rb') as f:
    x_authors = pickle.load(f)

with open(config.a_y, 'rb') as f:
    y = pickle.load(f)  # label

# params
b_size = 16
learning_rate = 2e-4
verbose = 2
epochs = 1000
author_emb_dim = 128
paper_emb_dim = 256
rnn_units = 128
mlp_units = 64
max_seq = config.seq_length
max_authors = config.author_length
max_papers = config.max_papers
patience = 10
dropout = 0.2
weight_decay = 1e-6


print('Max # authors:', max_authors)
print('Max # sequences:', max_seq)
print('# authors:', len(x))

train = x[:int(len(x)*.5)]
val = x[int(len(x)*.5):int(len(x)*.75)]
test = x[int(len(x)*.75):]

train_authors, train_y = x_authors[:int(len(x_authors)*.5)], y[:int(len(x_authors)*.5)]
val_authors, val_y = x_authors[int(len(x_authors)*.5):int(len(x_authors)*.75)], \
              y[int(len(x_authors)*.5):int(len(x_authors)*.75)]
test_authors, test_y = x_authors[int(len(x_authors)*.75):], y[int(len(x_authors)*.75):]

early_stop = tf.keras.callbacks.EarlyStopping(monitor='val_msle', patience=patience,
                                              verbose=1, restore_best_weights=True)

# model
input = tf.keras.layers.Input(shape=(max_papers, max_seq, paper_emb_dim))
input_authors = tf.keras.layers.Input(shape=(max_papers, max_seq, max_authors, author_emb_dim))

re_authors = tf.keras.layers.Reshape((-1, max_authors, author_emb_dim),
                                     input_shape=(max_papers, max_seq, max_authors, author_emb_dim))(input_authors)

masked_input = tf.keras.layers.Masking(mask_value=0., input_shape=(max_seq, rnn_units))(input)
masked_input_authors = tf.keras.layers.Masking(mask_value=0., input_shape=(max_seq, max_authors, author_emb_dim))(re_authors)


rnn_authors = tf.keras.layers.TimeDistributed(
    tf.keras.layers.GRU(rnn_units, dropout=dropout), input_shape=(max_seq*max_papers, max_authors, author_emb_dim),
)(masked_input_authors)

ree_authors = tf.keras.layers.Reshape((max_papers, max_seq, author_emb_dim),
                                     input_shape=(max_seq*max_papers, author_emb_dim))(rnn_authors)


con = tf.keras.layers.concatenate([masked_input, ree_authors])

add_rnn = tf.keras.layers.TimeDistributed(
    tf.keras.layers.GRU(rnn_units, dropout=dropout), input_shape=(max_papers, max_seq, author_emb_dim + paper_emb_dim)
)(con)

rnn_1 = tf.keras.layers.Bidirectional(
    tf.keras.layers.GRU(rnn_units, return_sequences=True, dropout=dropout)
)(add_rnn)

rnn_2 = tf.keras.layers.Bidirectional(
    tf.keras.layers.GRU(rnn_units//2, dropout=dropout)
)(rnn_1)

mlp_1 = tf.keras.layers.Dense(mlp_units, activation='relu')(rnn_2)
mlp_2 = tf.keras.layers.Dense(mlp_units//2, activation='relu')(mlp_1)
output = tf.keras.layers.Dense(1)(mlp_2)

xovee = tf.keras.Model(inputs=[input, input_authors], outputs=output)

adam = tf.keras.optimizers.RMSprop(learning_rate=learning_rate, decay=weight_decay)

xovee.compile(loss='msle', optimizer=adam, metrics=['msle'])

xovee.summary()

train_generator = Generator(train, train_authors, train_y, b_size, max_papers, max_seq, max_authors)
val_generator = Generator(val, val_authors, val_y, b_size, max_papers, max_seq, max_authors)
test_generator = Generator(test, test_authors, test_y, b_size, max_papers, max_seq, max_authors)


train_history = xovee.fit(train_generator,
                          validation_data=val_generator,
                          epochs=epochs,
                          verbose=verbose,
                          callbacks=[early_stop]
                          )

result_metric = xovee.evaluate(test_generator,  verbose=1)

# you can save your prediction here
pred = xovee.predict(test_generator)

print('Finished!')
