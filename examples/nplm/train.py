import os
import sys
import theano
import theano.tensor as T
import numpy
from collections import OrderedDict
import time

from cutils.training.trainer import new_sgd
from cutils.training.utils import get_minibatches_idx

# Include current path in the pythonpath
script_path = os.path.dirname(os.path.realpath(__file__))
sys.path.append(script_path)

from nplm import NPLM
from settimes import SetTimes


def sgd_optimization_nplm_mlp(learning_rate=1., L1_reg=0.0, L2_reg=0.0001,
                              n_epochs=1000, dataset='../../data/settimes',
                              batch_size=1000, n_in=150, n_h1=750, n_h2=150,
                              context_size=4):
    st_data = SetTimes(dataset, emb_dim=n_in)
    print("... Creating the partitions")
    train, valid = st_data.load_data(context_size=context_size)
    #train_x, train_y = train
    #valid_x, valid_y = valid
    print("... Done creating partitions")

    # Notice that get_value is called with borrow
    # so that a deep copy of the input is not created
    #n_train_batches = train_x.get_value(borrow=True).shape[0] // batch_size
    #n_valid_batches = valid_x.get_value(borrow=True).shape[0] // batch_size

    print("... Building the model")

    # Symbolic variables for input and output for a batch
    x = T.imatrix('x')
    y = T.ivector('y')
    lr = T.scalar(name='lr')

    emb_x = st_data.dictionary.Wemb[x.flatten()] \
        .reshape([x.shape[0], context_size * n_in])

    rng = numpy.random.RandomState(1234)
    model = NPLM(
        rng=rng,
        input=emb_x,
        n_in=context_size * n_in,
        n_h1=n_h1,
        n_h2=n_h2,
        n_out=st_data.dictionary.num_words()
    )

    # Cost to minimize
    cost = model.loss(y)
    #cost = (
        #model.loss(y)
        #+ L1_reg * model.L1
        #+ L2_reg * model.L2
    #)

    tparams = OrderedDict()
    for i, nplm_m in enumerate(model.params):
        tparams['nplm_' + str(i)] = nplm_m
    tparams['Wemb'] = st_data.dictionary.Wemb
    grads = T.grad(cost, wrt=list(tparams.values()))

    f_cost = theano.function([x, y], cost, name='f_cost')

    f_grad_shared, f_update = new_sgd(lr, tparams, grads,
                                      x, None, y, cost)

    print("... Optimization")
    kf_valid = get_minibatches_idx(len(valid[0]), batch_size)
    print("%d training examples" % len(train[0]))
    print("%d valid examples" % len(valid[0]))

    disp_freq = 10
    valid_freq = len(train[0]) // batch_size
    save_freq = len(train[0]) // batch_size

    uidx = 0
    estop = False
    start_time = time.time()
    for eidx in range(n_epochs):
        n_samples = 0
        # Shuffle and get training stuff
        kf = get_minibatches_idx(len(train[0]), batch_size, shuffle=True)
        for _, train_index in kf:
            uidx += 1
            x = [train[0][t] for t in train_index]
            y = [train[1][t] for t in train_index]
            # Convert x and y into numpy objects
            x = numpy.asarray(x, dtype='int32')
            y = numpy.asarray(y, dtype='int32')

            cost = f_grad_shared(x, y)
            f_update(learning_rate)

            if numpy.isnan(cost) or numpy.isinf(cost):
                print('bad cost detected: ', cost)
                return 1., 1.

            if numpy.mod(uidx, disp_freq) == 0:
                print('Epoch', eidx, 'Update', uidx, 'Cost', cost)

if __name__ == '__main__':
    sgd_optimization_nplm_mlp(dataset=sys.argv[1])
