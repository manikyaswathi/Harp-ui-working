import pandas as pd
import numpy as np
import re, os, math, copy, time

from sklearn.metrics import mean_squared_error, mean_absolute_error, mean_absolute_percentage_error
from sklearn.utils import shuffle
from sklearn import metrics #Import scikit-learn metrics module for accuracy calculation
from sklearn.model_selection import train_test_split


import tensorflow as tf
from tensorflow import keras


np.random.seed(2048)
tf.random.set_seed(2048)

def MAPE(gold, predict):
    overall=0
    for g, p in zip(gold, predict):
        overall+=(abs(g-p)/g)*100
    overall=overall/len(gold)
    return round(overall, 4)


def Under_predict(gold, predict):
    count = 0
    for g, p in zip(gold, predict):
        if p < g:
            count+=1
    return round(count/len(gold)*100, 4)

def MAPE_UP(gold, predict):
    count = 0
    overall=[]
    sumi=0
    for g, p in zip(gold, predict):
        if p < g:
            count+=1
            #overall.append((abs(g-p)/g)*100)
            overall.append((abs(p-g)/g)*100)
            sumi+=(abs(p-g)/g)*100
    if len(overall) > 0:
        mape_up = np.average(overall)
    else:
        mape_up = 0.0
    return round(mape_up, 4)


def MAPE_OV(gold, predict):
    count = 0
    overall=[]
    sumi=0
    for g, p in zip(gold, predict):
        if p > g:
            count+=1
            #overall.append((abs(g-p)/g)*100)
            overall.append((abs(p-g)/g)*100)
            sumi+=(abs(p-g)/g)*100
    if len(overall) > 0:
        mape_ov = np.average(overall)
    else:
        mape_ov = 0.0
    return round(mape_ov, 4)



def get_scores(gold, predict, printIt=False):
    mape = MAPE(gold, predict)
    upp =  Under_predict(gold, predict)
    up_mape = MAPE_UP(gold, predict)
    ov_mape = MAPE_OV(gold, predict)
    mseF = tf.keras.losses.MeanSquaredError()
    mse = round(mseF(gold, predict).numpy(), 4)
    maeF = tf.keras.losses.MeanAbsoluteError()
    mae = round(maeF(gold, predict).numpy(), 4)
    
    if printIt:
        print("Mean Squared Error:", mse)
        print("Mean Absolute Error:", mae)
        print("MAPE:", MAPE(gold, predict))
        print("Under Prediction Percentage:", upp)
        print("Under Prediction Percentag MAPE:", up_mape)
        print("Over Estimation Percentag MAPE:", ov_mape)
        
    return(mse, mae, mape, upp, up_mape, ov_mape)
