import numpy as np
import sys
import time
from copy import deepcopy
from scipy.sparse import csr_matrix
from scipy.sparse import spdiags
from scipy.stats import multivariate_normal
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import normalize

def diag(array):
    n = len(array)
    return spdiags(array, 0, n, n)

def logpdf_diagonal_gaussian(x, mean, cov):
    '''
    Compute logpdf of a multivariate Gaussian distribution with diagonal covariance at a given point x.
    A multivariate Gaussian distribution with a diagonal covariance is equivalent
    to a collection of independent Gaussian random variables.

    x should be a sparse matrix. The logpdf will be computed for each row of x.
    mean and cov should be given as 1D numpy arrays
    mean[i] : mean of i-th variable
    cov[i] : variance of i-th variable
    '''
    n = x.shape[0]
    dim = x.shape[1]
    assert(dim == len(mean) and dim == len(cov))

    # multiply each i-th column of x by (1/(2*sigma_i)), where sigma_i is sqrt of variance of i-th variable.
    scaled_x = x.dot( diag(1./(2*np.sqrt(cov))) )
    # multiply each i-th entry of mean by (1/(2*sigma_i))
    scaled_mean = mean/(2*np.sqrt(cov))

    # sum of pairwise squared Eulidean distances gives SUM[(x_i - mean_i)^2/(2*sigma_i^2)]
    return -np.sum(np.log(np.sqrt(2*np.pi*cov))) - pairwise_distances(scaled_x, [scaled_mean], 'euclidean').flatten()**2

def log_sum_exp(x, axis):
    '''Compute the log of a sum of exponentials'''
    x_max = np.max(x, axis=axis)
    if axis == 1:
        return x_max + np.log( np.sum(np.exp(x-x_max[:,np.newaxis]), axis=1) )
    else:
        return x_max + np.log( np.sum(np.exp(x-x_max), axis=0) )

def EM_for_high_dimension(data, means, covs, weights, cov_smoothing=1e-5, maxiter=int(1e3), thresh=1e-4, verbose=False):
    # cov_smoothing: specifies the default variance assigned to absent features in a cluster.
    #                If we were to assign zero variances to absent features, we would be overconfient,
    #                as we hastily conclude that those featurese would NEVER appear in the cluster.
    #                We'd like to leave a little bit of possibility for absent features to show up later.
    n = data.shape[0]
    dim = data.shape[1]
    mu = deepcopy(means)
    Sigma = deepcopy(covs)
    K = len(mu)
    weights = np.array(weights)

    ll = None
    ll_trace = []

    for i in range(maxiter):
        # E-step: compute responsibilities
        logresp = np.zeros((n,K))
        for k in range(K):
            logresp[:,k] = np.log(weights[k]) + logpdf_diagonal_gaussian(data, mu[k], Sigma[k])
        ll_new = np.sum(log_sum_exp(logresp, axis=1))
        if verbose:
            print(ll_new)
        sys.stdout.flush()
        logresp -= np.vstack(log_sum_exp(logresp, axis=1))
        resp = np.exp(logresp)
        counts = np.sum(resp, axis=0)

        # M-step: update weights, means, covariances
        weights = counts / np.sum(counts)
        for k in range(K):
            mu[k] = (diag(resp[:,k]).dot(data)).sum(axis=0)/counts[k]
            mu[k] = mu[k].A1

            Sigma[k] = diag(resp[:,k]).dot( data.multiply(data)-2*data.dot(diag(mu[k])) ).sum(axis=0) \
                       + (mu[k]**2)*counts[k]
            Sigma[k] = Sigma[k].A1 / counts[k] + cov_smoothing*np.ones(dim)

        # check for convergence in log-likelihood
        ll_trace.append(ll_new)
        if ll is not None and (ll_new-ll) < thresh and ll_new > -np.inf:
            ll = ll_new
            break
        else:
            ll = ll_new

    out = {'weights':weights,'means':mu,'covs':Sigma,'loglik':ll_trace,'resp':resp}

    return out
