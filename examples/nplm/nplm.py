import os
import theano.tensor as T

import cutils.regularization as reg
from cutils.layers.dense_layer import DenseLayer
from cutils.layers.logistic_regression import LogisticRegression

# Include logistic_regressioncurrent path in the pythonpath
script_path = os.path.dirname(os.path.realpath(__file__))


class NPLM(object):
    """
    Neural Network Language Model

    A multilayer perceptron is a feedforward artificial neural network model
    that has one layer or more of hidden units and nonlinear activations.
    Intermediate layers usually have as activation function tanh or the
    sigmoid function (defined here by a ``HiddenLayer`` class)  while the
    top layer is a softmax layer (defined here by a ``LogisticRegression``
    class).
    """

    def __init__(self, rng, input, n_in, n_h1, n_h2, n_out):
        """Initialize the parameters for the multilayer perceptron

        :type rng: numpy.random.RandomState
        :param rng: a random number generator used to initialize weights

        :type input: theano.tensor.TensorType
        :param input: symbolic variable that describes the input of the
        architecture (one minibatch)

        :type n_in: int
        :param n_in: number of input units, the dimension of the space in
        which the datapoints lie

        :type n_hidden: int
        :param n_hidden: number of hidden units

        :type n_out: int
        :param n_out: number of output units, the dimension of the space in
        which the labels lie

        """

        # Since we are dealing with a one hidden layer MLP, this will translate
        # into a HiddenLayer with a tanh activation function connected to the
        # LogisticRegression layer; the activation function can be replaced by
        # sigmoid or any other nonlinear function

        self.h1 = DenseLayer(
            rng=rng,
            input=input,
            n_in=n_in,
            n_out=n_h1,
            activation=T.nnet.relu
        )

        self.h2 = DenseLayer(
            rng=rng,
            input=self.h1.output,
            n_in=n_h1,
            n_out=n_h2,
            activation=T.nnet.relu
        )

        # The logistic regression layer
        self.log_regression_layer = LogisticRegression(
            input=self.h2.output,
            n_in=n_h2,
            n_out=n_out
        )

        # Use L1 and L2 regularization
        #self.L1 = reg.L1([self.h1.W, self.h2.W, self.log_regression_layer.W])
        #self.L2 = reg.L2([self.h1.W, self.h2.W, self.log_regression_layer.W])
        # Copy loss and error functions from the logistic regression class
        self.loss = self.log_regression_layer.loss
        #self.errors = self.log_regression_layer.errors

        self.params = self.h1.params + self.h2.params + \
            self.log_regression_layer.params

        self.input = input
