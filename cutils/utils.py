import numpy
import theano
import theano.tensor as T
import warnings


def xavier_init(rng, n_in, n_out, activation, size=None):
    """
    Returns a matrix (n_in X n_out) based on the
    Xavier initialization technique
    """

    if activation not in [T.tanh, T.nnet.sigmoid]:
        warnings.warn("You are using the Xavier init with an \
                       activation function that is not sigmoidal")
    # Default value for size
    if size is None:
        size = (n_in, n_out)
    W_values = numpy.asarray(
        rng.uniform(
            low=-numpy.sqrt(6. / (n_in + n_out)),
            high=numpy.sqrt(6. / (n_in + n_out)),
            size=size,
        ),
        dtype=theano.config.floatX
    )
    if activation == T.nnet.sigmoid:
        return W_values * 4
    return W_values
