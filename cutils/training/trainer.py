"""
Various training algorithms
"""
from __future__ import print_function

import theano
import theano.tensor as T
from theano.compile.nanguardmode import NanGuardMode
import scipy.optimize

from cutils.numeric import numpy_floatX


def sgd(cost, params, learning_rate):
    """
    Implements stochastic gradient descent

    :type cost : Theano symbolic expression
    :param cost : The cost function to be minimized

    :type params : List of theano.tensor.TensorType
    :param params : The parameters to be updated

    :type learning_rate : int
    :param learning_rate : The learning rate for SGD

    Returns : A list of tuples representing param updates
              (param, update)
    """
    updates = []
    for p in params:
        grad_p = T.grad(cost=cost, wrt=p)
        updates.append((p, p - learning_rate * grad_p))
    return updates


def new_sgd(lr, tparams, grads, cost, *args):
    """
    Implements stochastic gradient descent
    """
    gshared = [theano.shared(p.get_value() * 0., name='%s_grad' % k)
               for k, p in tparams.items()]
    # Gradient clipping
    # Move the rescale parameter to an argument or config
    grad_norm = T.sqrt(sum(map(lambda x: T.sqr(x).sum(), grads)))
    rescale = 5.
    scaling_num = rescale
    scaling_den = T.maximum(rescale, grad_norm)
    gsup = [(gs, g * (scaling_num / scaling_den))
            for gs, g in zip(gshared, grads)]
    # Compute gradients but do not update them
    grad_input = list(args)
    f_grad_shared = theano.function(grad_input, cost, updates=gsup,
                                    name='sgd_f_grad_shared',
                                    profile=True,
                                    #mode=NanGuardMode(nan_is_error=True,
                                                      #inf_is_error=True,
                                                      #big_is_error=True),
                                    #mode=theano.compile.MonitorMode(
                                        #pre_func=inspect_inputs,
                                        #post_func=inspect_outputs),
                    )
    pup = [(p, p - lr * g) for p, g in zip(tparams.values(), gshared)]
    # Function which updates weights
    f_update = theano.function([lr], [], updates=pup,
                               name='sgd_f_update')
    return f_grad_shared, f_update


def adadelta(lr, tparams, grads, cost, *args):
    """
    An adaptive learning rate optimizer

    Parameters
    ----------
    lr : Theano SharedVariable
        Initial learning rate
    tpramas: Theano SharedVariable
        Model parameters
    grads: Theano variable
        Gradients of cost w.r.t to parameres
    x: Theano variable
        Model inputs
    mask: Theano variable
        Sequence mask
    y: Theano variable
        Targets
    cost: Theano variable
        Objective fucntion to minimize

    Notes
    -----
    For more information, see [ADADELTA]_.

    .. [ADADELTA] Matthew D. Zeiler, *ADADELTA: An Adaptive Learning
       Rate Method*, arXiv:1212.5701.
    """
    zipped_grads = [theano.shared(p.get_value() * numpy_floatX(0.),
                                  name='%s_grad' % k)
                    for k, p in tparams.items()]
    running_up2 = [theano.shared(p.get_value() * numpy_floatX(0.),
                                 name='%s_rup2' % k)
                   for k, p in tparams.items()]
    running_grads2 = [theano.shared(p.get_value() * numpy_floatX(0.),
                                    name='%s_rgrad2' % k)
                      for k, p in tparams.items()]

    zgup = [(zg, g) for zg, g in zip(zipped_grads, grads)]
    rg2up = [(rg2, 0.95 * rg2 + 0.05 * (g ** 2))
             for rg2, g in zip(running_grads2, grads)]

    grad_input = list(args)
    f_grad_shared = theano.function(grad_input, cost, updates=zgup + rg2up,
                                    name='adadelta_f_grad_shared')

    updir = [-T.sqrt(ru2 + 1e-6) / T.sqrt(rg2 + 1e-6) * zg
             for zg, ru2, rg2 in zip(zipped_grads,
                                     running_up2,
                                     running_grads2)]
    ru2up = [(ru2, 0.95 * ru2 + 0.05 * (ud ** 2))
             for ru2, ud in zip(running_up2, updir)]
    param_up = [(p, p + ud) for p, ud in zip(tparams.values(), updir)]

    f_update = theano.function([lr], [], updates=ru2up + param_up,
                               on_unused_input='ignore',
                               name='adadelta_f_update')

    return f_grad_shared, f_update


def rmsprop(lr, tparams, grads, cost, *args):
    """
    A variant of  SGD that scales the step size by running average of the
    recent step norms.

    Parameters
    ----------
    lr : Theano SharedVariable
        Initial learning rate
    tpramas: Theano SharedVariable
        Model parameters
    grads: Theano variable
        Gradients of cost w.r.t to parameres
    x: Theano variable
        Model inputs
    mask: Theano variable
        Sequence mask
    y: Theano variable
        Targets
    cost: Theano variable
        Objective fucntion to minimize

    Notes
    -----
    For more information, see [Hint2014]_.

    .. [Hint2014] Geoff Hinton, *Neural Networks for Machine Learning*,
       lecture 6a,
       http://cs.toronto.edu/~tijmen/csc321/slides/lecture_slides_lec6.pdf
    """

    zipped_grads = [theano.shared(p.get_value() * numpy_floatX(0.),
                                  name='%s_grad' % k)
                    for k, p in tparams.items()]
    running_grads = [theano.shared(p.get_value() * numpy_floatX(0.),
                                   name='%s_rgrad' % k)
                     for k, p in tparams.items()]
    running_grads2 = [theano.shared(p.get_value() * numpy_floatX(0.),
                                    name='%s_rgrad2' % k)
                      for k, p in tparams.items()]

    zgup = [(zg, g) for zg, g in zip(zipped_grads, grads)]
    rgup = [(rg, 0.95 * rg + 0.05 * g) for rg, g in zip(running_grads, grads)]
    rg2up = [(rg2, 0.95 * rg2 + 0.05 * (g ** 2))
             for rg2, g in zip(running_grads2, grads)]

    grad_input = list(args)
    f_grad_shared = theano.function(grad_input, cost,
                                    updates=zgup + rgup + rg2up,
                                    name='rmsprop_f_grad_shared')

    updir = [theano.shared(p.get_value() * numpy_floatX(0.),
                           name='%s_updir' % k)
             for k, p in tparams.items()]
    updir_new = [(ud, 0.9 * ud - 1e-4 * zg / T.sqrt(rg2 - rg ** 2 + 1e-4))
                 for ud, zg, rg, rg2 in zip(updir, zipped_grads, running_grads,
                                            running_grads2)]
    param_up = [(p, p + udn[1])
                for p, udn in zip(tparams.values(), updir_new)]
    f_update = theano.function([lr], [], updates=updir_new + param_up,
                               on_unused_input='ignore',
                               name='rmsprop_f_update')

    return f_grad_shared, f_update


def conjugate_gradient_descent(train_fn, train_fn_grad,
                               callback, x0, n_epochs):
    """
    Implements the conjugate gradient solver
    """
    best_params = scipy.optimize.fmin_cg(
        f=train_fn,
        x0=x0,
        fprime=train_fn_grad,
        callback=callback,
        disp=0,
        maxiter=n_epochs
    )
    return best_params

def inspect_inputs(i, node, fn):
    #print(i, node, "input(s) value(s):", [input[0] for input in fn.inputs], end='')
    print(i, node, "input(s) value(s):",end='')

def inspect_outputs(i, node, fn):
    print(" output(s) value(s):", [output[0] for output in fn.outputs])
