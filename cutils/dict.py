import numpy
import theano
from collections import OrderedDict

from cutils.params.utils import init_tparams


class Dict:
    def __init__(self, sentences, n_words, emb_dim):
        self.locked = False
        wordcount = dict()
        for ss in sentences:
            words = ss.strip().split()
            for w in words:
                if w not in wordcount:
                    wordcount[w] = 0
                wordcount[w] += 1
        counts = wordcount.values()
        keys = wordcount.keys()
        self.worddict = dict()
        self.worddict['<UNK>'] = 1
        self.worddict['<PAD>'] = 0
        # Reverse and truncate at max_words
        sorted_idx = numpy.argsort(counts)[::-1][:n_words]
        for idx, ss in enumerate(sorted_idx):
            self.worddict[keys[ss]] = idx + 2

        self.locked = True
        self.n_words = n_words + 2

        print("Total words read by dict = %d" % numpy.sum(counts))
        print("Total unique words read by dict = %d" % len(keys))
        print("Total words retained = %d" % len(self.worddict))

        self.embedding_size = emb_dim
        self.rng = None
        self.Wemb = None
        self.initialize_embedding()

    def initialize_embedding(self):
        randn = numpy.random.rand(self.n_words, self.embedding_size)
        Wemb = (0.01 * randn).astype(theano.config.floatX)
        self.Wemb = init_tparams(OrderedDict([('Wemb', Wemb)]))['Wemb']

    def read_sentence(self, line):
        line = line.strip().split()
        return [self.worddict[w] if w in self.worddict else 1 for w in line]

    def num_words(self):
        """ + 2 for the UNK symbols """
        return self.n_words

    def get_embedding(self, word):
        if word not in self.words:
            word = "UNK"
        return self.embeddings[self.words[word]]
