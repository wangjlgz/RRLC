from __future__ import division

from math import log
import numpy as np
import pandas as pd
import copy
from operator import itemgetter
import time
import random


# calculate NDCG@k
def NDCG_at_k(predicted_list, ground_truth, k):
    dcg_value = [(v / log(i + 1 + 1, 2)) for i, v in enumerate(predicted_list[:k])]
    dcg = np.sum(dcg_value)
    if len(ground_truth) < k:
        ground_truth += [0 for i in range(k - len(ground_truth))]
    idcg_value = [(v / log(i + 1 + 1, 2)) for i, v in enumerate(ground_truth[:k])]
    idcg = np.sum(idcg_value)
    return dcg / idcg


# calculate precision@k, recall@k, NDCG@k, where k = 1,5,10,15
def user_precision_recall_ndcg(new_user_prediction, test):
    dcg_list = []

    # compute the number of true positive items at top k
    count_1, count_5, count_10, count_15, count_50 = 0, 0, 0, 0, 0
    for i in range(50):
        if i == 0 and new_user_prediction[i][0] in test:
            count_1 = 1.0
        if i < 5 and new_user_prediction[i][0] in test:
            count_5 += 1.0
        if i < 10 and new_user_prediction[i][0] in test:
            count_10 += 1.0
        if i < 15 and new_user_prediction[i][0] in test:
            count_15 += 1.0
        if new_user_prediction[i][0] in test:
            count_50 += 1.0
            dcg_list.append(1)
        else:
            dcg_list.append(0)

    # calculate NDCG@k
    idcg_list = [1 for i in range(len(test))]
    ndcg_tmp_1 = NDCG_at_k(dcg_list, idcg_list, 1)
    ndcg_tmp_5 = NDCG_at_k(dcg_list, idcg_list, 5)
    ndcg_tmp_10 = NDCG_at_k(dcg_list, idcg_list, 10)
    ndcg_tmp_15 = NDCG_at_k(dcg_list, idcg_list, 15)
    ndcg_tmp_50 = NDCG_at_k(dcg_list, idcg_list, 50)

    # precision@k
    precision_1 = count_1
    precision_5 = count_5 / 5.0
    precision_10 = count_10 / 10.0
    precision_15 = count_15 / 15.0
    precision_50 = count_50 / 50.0

    l = len(test)
    if l == 0:
        l = 1
    # recall@k
    recall_1 = count_1 / l
    recall_5 = count_5 / l
    recall_10 = count_10 / l
    recall_15 = count_15 / l
    recall_50 = count_50 / l

    # return precision, recall, ndcg_
    return np.array([precision_1, precision_5, precision_10, precision_15, precision_50]),\
           np.array([recall_1, recall_5, recall_10, recall_15, recall_50]),\
           np.array([ndcg_tmp_1, ndcg_tmp_5, ndcg_tmp_10, ndcg_tmp_15, ndcg_tmp_50])


def neg_sampling(train_R_b, idx, neg_sample_rate):

    num_cols = train_R_b.shape[1]
    num_rows = train_R_b.shape[0]
    # randomly sample negative samples
    mask = copy.copy(train_R_b)
    if neg_sample_rate == 0:
        return mask
    for b_idx in idx:
        mask_list = mask[b_idx, :]
        unobsv_list = np.where(mask_list == 0)
        unobsv_list = unobsv_list[0]  # unobserved indices
        obsv_num = num_cols - len(unobsv_list)
        neg_num = int(obsv_num * neg_sample_rate)
        if neg_num > len(unobsv_list):  # if the observed positive ratings are more than the half
            neg_num = len(unobsv_list)
        if neg_num == 0:
            neg_num = 1
        neg_samp_list = np.random.choice(unobsv_list, size=neg_num, replace=False)
        mask_list[neg_samp_list] = 1
        mask[b_idx, :] = mask_list
    return mask


# calculate the metrics of the result
def test_model_batch(prediction, test_mask, train_b, train_mask=None):
    precision_1, precision_5, precision_10, precision_15, precision_50 = 0.0000, 0.0000, 0.0000, 0.0000, 0.0000
    recall_1, recall_5, recall_10, recall_15, recall_50 = 0.0000, 0.0000, 0.0000, 0.0000, 0.0000
    ndcg_1, ndcg_5, ndcg_10, ndcg_15, ndcg_50 = 0.0000, 0.0000, 0.0000, 0.0000, 0.0000
    precision = np.array([precision_1, precision_5, precision_10, precision_15, precision_50])
    recall = np.array([recall_1, recall_5, recall_10, recall_15, recall_50])
    ndcg = np.array([ndcg_1, ndcg_5, ndcg_10, ndcg_15, ndcg_50])

    prediction = prediction + train_b * -100000.0
    count = 0
    user_num = prediction.shape[0]
    for u in range(user_num):  # iterate each user
        u_test = test_mask[u]
        u_test = np.where(u_test == 1)[0]  # the indices of the true positive items in the test set
        u_pred = prediction[u, :]

        #nnn = 15 + len(train_mask[u])
        nnn = 50
        top50_item_idx_no_train = np.argpartition(u_pred, -nnn)[-nnn:]
        top50 = (np.array([top50_item_idx_no_train, u_pred[top50_item_idx_no_train]])).T
        top50 = sorted(top50, key=itemgetter(1), reverse=True)

        # calculate the metrics
        if not len(u_test) == 0:
            #precision_u, recall_u, ndcg_u = user_precision_recall_ndcg(remove_train[:15], u_test)
            precision_u, recall_u, ndcg_u = user_precision_recall_ndcg(top50, u_test)
            precision += precision_u
            recall += recall_u
            ndcg += ndcg_u
            count += 1
        else:
            user_num -= 1

    return precision, recall, ndcg, count


def test_model_agg(precision, recall, ndcg, user_num):
    # compute the average over all users
    precision /= user_num
    recall /= user_num
    ndcg /= user_num
    print('precision_1\t[%.7f],\t||\t precision_5\t[%.7f],\t||\t precision_10\t[%.7f],\t||\t precision_15\t[%.7f],\t||\t precision_50\t[%.7f]' \
          % (precision[0],
             precision[1],
             precision[2],
             precision[3],
             precision[4]))
    print('recall_1   \t[%.7f],\t||\t recall_5   \t[%.7f],\t||\t recall_10   \t[%.7f],\t||\t recall_15   \t[%.7f],\t||\t recall_50   \t[%.7f]' \
          % (recall[0], recall[1],
             recall[2], recall[3], recall[4]))
    f_measure_1 = 2 * (precision[0] * recall[0]) / (precision[0] + recall[0]) if not precision[0] + recall[0] == 0 else 0
    f_measure_5 = 2 * (precision[1] * recall[1]) / (precision[1] + recall[1]) if not precision[1] + recall[1] == 0 else 0
    f_measure_10 = 2 * (precision[2] * recall[2]) / (precision[2] + recall[2]) if not precision[2] + recall[2] == 0 else 0
    f_measure_15 = 2 * (precision[3] * recall[3]) / (precision[3] + recall[3]) if not precision[3] + recall[3] == 0 else 0
    f_measure_50 = 2 * (precision[4] * recall[4]) / (precision[4] + recall[4]) if not precision[4] + recall[4] == 0 else 0
    print('f_measure_1\t[%.7f],\t||\t f_measure_5\t[%.7f],\t||\t f_measure_10\t[%.7f],\t||\t f_measure_15\t[%.7f],\t||\t f_measure_50\t[%.7f]' \
          % (f_measure_1,
             f_measure_5,
             f_measure_10,
             f_measure_15,
             f_measure_50))
    f_score = [f_measure_1, f_measure_5, f_measure_10, f_measure_15, f_measure_50]
    print('ndcg_1     \t[%.7f],\t||\t ndcg_5     \t[%.7f],\t||\t ndcg_10     \t[%.7f],\t||\t ndcg_15     \t[%.7f],\t||\t ndcg_50     \t[%.7f]' \
          % (ndcg[0],
             ndcg[1],
             ndcg[2],
             ndcg[3],
             ndcg[4]))
    return precision, recall, f_score, ndcg



