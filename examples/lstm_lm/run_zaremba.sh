#!/usr/bin/env bash

#$ -cwd
#$ -S /bin/bash
#$ -M gkumar6@jhu.edu
#$ -m eas
#$ -l gpu=1
#$ -V
#$ -j y -o log/zaremba.log

. ../../setup.sh

THEANO_FLAGS=device=gpu python train.py \
    --save-to lm_zaremba.npz \
    --dataset ../../data/simple-examples/data \
    --dim-proj 650 \
    --n-words 10000 \
    --maxlen 35 \
    --batch-size 20 \
    --max-epochs 40 \
    --decay-lr-after-ep 6 \
    --decay-lr-factor 1.2 \
    --optimizer sgd \
    --lrate 1.0
