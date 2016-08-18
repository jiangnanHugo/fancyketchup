"""
An encoder-decoder model using LSTMs
"""

from __future__ import print_function

import numpy
import theano
import theano.tensor as T
from collections import OrderedDict
from theano.sandbox.rng_mrg import MRG_RandomStreams as RandomStreams

from cutils.numeric import numpy_floatX
from cutils.layers.utils import dropout_layer
from cutils.layers.lstm import LSTM
from cutils.data_interface.utils import pad_and_mask
from cutils.params.utils import init_tparams


class ENCODER_DECODER(object):
    def _p(self, pp, name):
        return '%s_%s' % (pp, name)


    def __init__(self, dim_proj, ydim, word_dict, random_seed):
        """
        Embedding and classifier params
        word_dict is the source embedding dictionary
        """
        self.layers = {}
        self.random_seed = random_seed
        self.dim_proj = dim_proj
        self.ydim = ydim
        self.rng = numpy.random.RandomState(self.random_seed)
        self.params = OrderedDict()
        self.tparams = OrderedDict()
        self.f_cost = None
        self.f_decode = None

        def unpack(source, target):
            for kk, vv in source.items():
                target[kk] = vv

        # Add parameters from dictionary
        unpack(word_dict.params, self.params)
        unpack(word_dict.tparams, self.tparams)
        # Initialize LSTM and add its params
        # Two LSTMs for forward and backward runs
        self.layers['lstm_enc_f'] = LSTM(dim_proj, self.rng)
        unpack(self.layers['lstm_enc_f'].params, self.params)
        unpack(self.layers['lstm_enc_f'].tparams, self.tparams)
        self.layers['lstm_enc_b'] = LSTM(dim_proj, self.rng)
        unpack(self.layers['lstm_enc_b'].params, self.params)
        unpack(self.layers['lstm_enc_b'].tparams, self.tparams)

        self.layers['lstm_dec'] = LSTM(dim_proj, self.rng)
        unpack(self.layers['lstm_dec'].params, self.params)
        unpack(self.layers['lstm_dec'].tparams, self.tparams)

        # Initialize other params
        other_params = OrderedDict()
        # Dim here
        other_params['U'] = 0.01 * numpy.random.randn(2 * dim_proj, dim_proj) \
            .astype(theano.config.floatX)
        other_params['b'] = numpy.zeros((dim_proj,)).astype(theano.config.floatX)
        other_params['U_y'] = 0.01 * numpy.random.randn(dim_proj, ydim) \
            .astype(theano.config.floatX)
        other_params['b_y'] = numpy.zeros((ydim,)).astype(theano.config.floatX)
        other_tparams = init_tparams(other_params)
        unpack(other_params, self.params)
        unpack(other_tparams, self.tparams)


    def build_model(self, use_dropout=True):
        use_noise = theano.shared(numpy_floatX(0.))
        x = T.matrix('x', dtype='int64')
        y = T.matrix('y', dtype='int64')
        # Since we are simply predicting the next word, the
        # following statement shifts the content of the x by 1
        # in the time dimension for prediction (axis 0, assuming TxNxV)
        mask_x = T.matrix('mask_x', dtype=theano.config.floatX)
        mask_y = T.matrix('mask_y', dtype=theano.config.floatX)

        n_timesteps = x.shape[0]
        n_samples = x.shape[1]

        emb = self.tparams['Wemb'][x.flatten()].reshape([n_timesteps,
                                                         n_samples,
                                                         self.dim_proj])
        emb_b = emb[::-1]
        mask_b = mask_x[::-1]
        proj_f = self.layers['lstm_enc_f'].lstm_layer(emb, self.dim_proj, mask=mask)
        proj_b = self.layers['lstm_enc_b'].lstm_layer(emb_b, self.dim_proj, mask=mask_b)
        # Concatenate last forward and backward hidden states
        proj = T.concatenate([proj_f[-1], proj_b[-1]], axis=1)
        # Apply the mask to the final output to 0 out the time steps that are invalid
        # TODO, this should probably be set to 1? 
        proj = proj * mask_x[:, :, None]
        if use_dropout:
            trng = RandomStreams(self.random_seed)
            proj = dropout_layer(proj, use_noise, trng)

        context = T.dot(proj, self.tparams['U']) + self.tparams['b']
        y_n_timesteps = y.shape[0]

        def y_output_to_input_transform():
            return context

        proj_y = self.layers['lstm_dec'].lstm_layer([], self.dim_proj, mask=mask_y, n_steps=y_n_timesteps,
                                                    output_to_input_func=y_output_to_input_transform)
        proj_y = proj_y * mask_y[:, :, None]
        if use_dropout:
            trng = RandomStreams(self.random_seed)
            proj_y = dropout_layer(proj_y, use_noise, trng)

        pre_s = T.dot(proj, self.tparams['U_y']) + self.tparams['b_y']
        # Softmax works for 2-tensors (matrices) only. We have a 3-tensor
        # TxNxV. So we reshape it to (T*N)xV, apply softmax and reshape again
        # -1 is a proxy for infer dim based on input (numpy style)
        pre_s_r = T.reshape(pre_s, (pre_s.shape[0] * pre_s.shape[1], -1))
        # Softmax will receive all-0s for previously padded entries
        pred_r = T.nnet.softmax(pre_s_r)
        pred = T.reshape(pred_r, pre_s.shape)

        off = 1e-8
        if pred.dtype == 'float16':
            off = 1e-6

        # Note the use of flatten here. We can't directly index a 3-tensor
        # and hence we use the (T*N)xV view which is indexed by the flattened
        # label matrix, dim = (T*N)x1
        cost = -T.log(pred_r[T.arange(pred_r.shape[0]), y.flatten()] + off).mean()

        self.f_cost = theano.function([x, y, mask_x, mask_y], cost, name='f_cost')

        return use_noise, x, y, mask_x, mask_y, cost


    def build_decode(self):
        x = T.matrix('x', dtype='int64')
        emb = self.tparams['Wemb'][x.flatten()].reshape([x.shape[0],
                                                         x.shape[1],
                                                         self.dim_proj])
        mask = T.matrix('mask', dtype=theano.config.floatX)
        n_timesteps = T.iscalar('n_time')
        n_samples = x.shape[1]

        def output_to_input_transform(output):
            """
            TODO:t_mask is the mask for the current time step, shape=(Nx1)
            probably required
            """
            ## N x dim
            #output = output * previous_mask[:, None]
            # N X y_dim
            pre_soft = T.dot(output, self.tparams['U']) + self.tparams['b']
            # Softmax will receive all-0s for previously padded entries
            pred = T.nnet.softmax(pre_soft)
            # N x 1
            pred_argmax = pred.argmax(axis=1)
            new_input = self.tparams['Wemb'][pred_argmax.flatten()].reshape([n_samples,
                                                                       self.dim_proj])
            return new_input

        proj = self.layers['lstm_enc'].lstm_layer(emb, self.dim_proj, mask=mask, n_steps=n_timesteps,
                                               output_to_input_func=output_to_input_transform)
        pre_s = T.dot(proj, self.tparams['U']) + self.tparams['b']
        # Softmax works for 2-tensors (matrices) only. We have a 3-tensor
        # TxNxV. So we reshape it to (T*N)xV, apply softmax and reshape again
        # -1 is a proxy for infer dim based on input (numpy style)
        pre_s_r = T.reshape(pre_s, (pre_s.shape[0] * pre_s.shape[1], -1))
        # Softmax will receive all-0s for previously padded entries
        pred_r = T.nnet.softmax(pre_s_r)
        pred = T.reshape(pred_r, pre_s.shape).argmax(axis=2)
        self.f_decode = theano.function([x, mask, n_timesteps], pred, name='f_decode')

        return x, mask, n_timesteps


    def pred_cost(self, data, iterator, verbose=False):
        """
        Probabilities for new examples from a trained model

        data : The complete dataset. A list of lists. Each nested list is a sample
        iterator : A list of lists. Each nested list is a batch with idxs to the sample in data
        """
        # Total samples
        n_samples = len(data)
        running_cost = []
        samples_seen = []

        n_done = 0

        # valid_index is a list containing the IDXs of samples for a batch
        for _, valid_index in iterator:
            x, mask, _ = pad_and_mask([data[t] for t in valid_index])
            # Accumulate running cost
            samples_seen.append(len(valid_index))
            running_cost.append(self.f_cost(x, mask))
            n_done += len(valid_index)
            if verbose:
                print("%d/%d samples classified" % (n_done, n_samples))

        return sum([samples_seen[i] * running_cost[i] for i in range(len(samples_seen))]) / sum(samples_seen)
