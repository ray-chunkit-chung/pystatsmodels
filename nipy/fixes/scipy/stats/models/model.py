import numpy as np
from numpy.linalg import inv

from scipy.stats import t, norm
from scipy import optimize
from models.contrast import ContrastResults
from models.tools import recipr

import numpy.lib.recfunctions as nprf

class Model(object):
    """
    A (predictive) statistical model. The class Model itself does nothing
    but lays out the methods expected of any subclass.
    """

    _results = None

    def fit(self):
        """
        Fit a model to data.
        """
        raise NotImplementedError

#TODO: decide on this.
#Changed the way that this works.  It's now a predict attribute.
#        Does this make sense?
# but predict for AR, should be it's own method, etc.
# always make this take a params argument as it was?
    def predict(self):
        """
        After a model has been fit, results are (assumed to be) stored
        in self.results, which itself should have a predict method.

        """
        return self.results.predict

class LikelihoodModel(Model):
    """
    Likelihood model is a subclass of Model.
    """

    def __init__(self, endog, exog=None):
        self._endog = endog
        self._exog = exog
        self.initialize()
        
    def initialize(self):
        """
        Initialize (possibly re-initialize) a Model instance. For
        instance, the design matrix of a linear model may change
        and some things must be recomputed.
        """
        pass

    def loglike(self, params):
        """
        Log-likelihood of model.
        """
        raise NotImplementedError

    def score(self, params):
        """
        Score function of model = gradient of logL with respect to
        params.
        """
        raise NotImplementedError

    def information(self, params):
        """
        Fisher information function of model = - Hessian of logL with respect
        to params.
        """
        raise NotImplementedError

#TODO: newton's method is not correctly implemented yet
    def fit(self, params, method='newton'):
        if method is 'newton':
            results = self.newton(params)
        else: 
            raise ValueError("Unknown fit method.")
        self._results = results

#FIXME: This does not work as implemented
#FIXME: Params should be a first guess on the params
#       so supplied or default guess?
    def newton(self, params):
        #JP this is not newton, it's fmin
# optimize.newton is only for singlevariate?
# fmin can take multivariate
# probably called newton bc it's the well known 
# root finding for MLE
# SS no this isn't used anywhere right now, but needs attention for
# MLE
        # is this used anywhere
        # results should be attached to self
        f = lambda params: -self.loglike(params)
        xopt, fopt, iter, funcalls, warnflag =\
          optimize.fmin(f, params, full_output=True)
        converge = not warnflag
        extras = dict(iter=iter, evaluations=funcalls, converge=converge)
#        return LikelihoodModelResults(self, params, llf=fopt, **extras)
        return LikelihoodModelResults(self, xopt)
        

class Results(object):
    """
    Class to contain model results
    """
    def __init__(self, model, params, **kwd):
        """
        Parameters
        ----------
        model : class instance
            the previously specified model instance
        params : array
            parameter estimates from the fit model
        """
        self.__dict__.update(kwd)
        self.initialize(model, params, **kwd)
    
    def initialize(self, model, params, **kwd):
        self.params = params
        self.model = model

class LikelihoodModelResults(Results):
    """ Class to contain results from likelihood models """
    def __init__(self, model, params, normalized_cov_params=None, scale=1.):
        """ 
        Parameters
        -----------
        params : 1d array_like
            parameter estimates from estimated model
        normalized_cov_params : 2d array
           Normalized (before scaling) covariance of params
            normalized_cov_paramss is also known as the hat matrix or H
            (Semiparametric regression, Ruppert, Wand, Carroll; CUP 2003)
        scale : float
            For (some subset of models) scale will typically be the
            mean square error from the estimated model (sigma^2)
        
        Comments
        --------
            
        The covariance of params is given by scale times
        normalized_cov_params
        """
        
        #JP what are the minimum attributes and methods that are used of model
        # i.e. can this be called with an almost empty model
        # what's the smallest duck that quacks like a model - list
# SS the minimum is data.endog, data.exog (except for AR)
# some models take more kwd arguments
# the minimum needed for results are the inits here
        super(LikelihoodModelResults, self).__init__(model, params)
        self.normalized_cov_params = normalized_cov_params
        self.scale = scale

    def normalized_cov_params(self):
        raise NotImplementedError

#    def scale(self):    #JP very bad, first scale is an attribute, now a method
#        raise NotImplementedError
                        # SS It's not used I don't think and can be removed

    def t(self, column=None):
        """
        Return the t-statistic for a given parameter estimate.

        Parameters
        ----------
        column : array-like
            The columns for which you would like the t-value.
            Note that this uses Python's indexing conventions.

        See also
        ---------
        Use t_test for more complicated t-statistics.

        Examples
        --------
        >>>from models.datasets.longley.data import load
        >>>from models.tools import add_constant
        >>>from models.regression import OLS
        >>>data = load()
        >>>data.exog = add_constant(data.exog)
        >>>results = OLS(data.endog, data.exog).fit()
        >>>results.t()
        array([ 0.17737603, -1.06951632, -4.13642736, -4.82198531, -0.22605114,
        4.01588981, -3.91080292])
        >>>results.t([1,2,4])
        array([-1.06951632, -4.13642736, -0.22605114])
        >>>import numpy as np
        >>>results.t(np.array([1,2,4]))
        array([-1.06951632, -4.13642736, -0.22605114])
        """

        if self.normalized_cov_params is None:
            raise ValueError, 'need covariance of parameters for computing T statistics'

        if column is None:
            column = range(self.params.shape[0])

        column = np.asarray(column)
        _params = self.params[column]
        _cov = self.cov_params(column=column)
        if _cov.ndim == 2:
            _cov = np.diag(_cov)
        _t = _params * recipr(np.sqrt(_cov))
        return _t


    def cov_params(self, contrast=None, column=None, scale=None, other=None):
        """
        Returns the variance/covariance matrix.
        
        The variance/covariance matrix can be of a linear contrast
        of the estimates of params or all params multiplied by scale which
        will usually be an estimate of sigma^2.  Scale is assumed to be
        a scalar.

        Parameters
        -----------
        contrast : array-like
            Can be 1d, or 2d.  Can be used alone or with other.
        column :  array-like
            Must be used on its own.  Can be 0d or 1d see below.
        scale : float
            Can be specified or not.  Default is None, which means that
            the scale argument is taken from the model.
        other : array-like
            Can be used when contrast is specified.

        Returns
        -------
        (The below are assumed to be in matrix notation.)

        cov : ndarray

        If no argument is specified returns the covariance matrix of a model
        (scale)*(X.T X)^(-1)

        If contrast is specified it pre and post-multiplies as follows
        (scale) * contrast (X.T X)^(-1) contrast.T

        If contrast and other are specified returns
        (scale) * contrast (X.T X)^(-1) other.T

        If column is specified returns
        (scale) * (X.T X)^(-1)[column,column] if column is 0d 
        
        OR

        (scale) * (X.T X)^(-1)[column][:,column] if column is 1d

        """
        if self.normalized_cov_params is None:
            raise ValueError, 'need covariance of parameters for computing \
(unnormalized) covariances'
        if column is not None and (contrast is not None or other is not None):
            raise ValueError, 'Column should be specified without other \
arguments.'
        if other is not None and contrast is None:
            raise ValueError, 'other can only be specified with contrast'
        if scale is None:
            scale = self.scale
        if column is not None:
            column = np.asarray(column)
            if column.shape == ():
                return self.normalized_cov_params[column, column] * scale
            else:
                return self.normalized_cov_params[column][:,column] * scale
        elif contrast is not None:
            contrast = np.asarray(contrast)
            if contrast.shape == ():
                raise ValueError, "contrast should be 1d or 2d"
            if other is None:
                other = contrast
            else:
                other = np.asarray(other)
            tmp = np.dot(contrast, np.dot(self.normalized_cov_params, 
                np.transpose(other)))
            return tmp * scale
        if contrast is None and column is None:
#            if np.shape(scale) == ():   # can be a scalar or array
# TODO: Algorithm for HCCM
# the first return is needed if scale is not a scalar
#                scale=np.eye(len(self._model._endog))*scale
#            return np.dot(np.dot(self.calc_params, np.array(scale)), 
#                self.calc_params.T)
            return self.normalized_cov_params * scale

    def t_test(self, r_matrix, t=True, sd=True, scale=None):
        """
        Compute a tcontrast/t-test for a row vector array.      
        
        Parameters
        ----------
        r_matrix : array-like
            Linear restrictions.
        
        See also
        ---------
        To get the t-statistic for a single column, use the 't' method.

        """

        r_matrix = np.asarray(r_matrix)

        if self.normalized_cov_params is None:
            raise ValueError, 'Need covariance of parameters for computing T statistics'

        _t = _sd = None

        _effect = np.dot(r_matrix, self.params)
        if sd:
            _sd = np.sqrt(self.cov_params(contrast=r_matrix))
        if t:
            _t = _effect * recipr(_sd)
        return ContrastResults(effect=_effect, t=_t, sd=_sd, df_denom=self.df_resid)

    def f_test(self, r_matrix, eff=True, t=True, sd=True, scale=None, 
            invcov=None):
        """
        Compute an Fcontrast for a contrast matrix.

        Here, matrix M is assumed to be non-singular. More precisely,

        M pX pX' M'

        is assumed invertible. Here, pX is the generalized inverse of the
        design matrix of the model. There can be problems in non-OLS models
        where the rank of the covariance of the noise is not full.

        See the contrast module to see how to specify contrasts.
        In particular, the matrices from these contrasts will always be
        non-singular in the sense above.

        """
        r_matrix = np.asarray(r_matrix)
        #JP: needs asarray and atleast_2d (exception), (potential) problems if not
        
        if self.normalized_cov_params is None:
            raise ValueError, 'need covariance of parameters for computing F statistics'

        cparams = np.dot(r_matrix, self.params)

        q = r_matrix.shape[0]
        if invcov is None:
            invcov = inv(self.cov_params(contrast=r_matrix, scale=1.0))
        F = np.add.reduce(np.dot(invcov, cparams) * cparams, 0) * \
                recipr((q * self.scale))
        return ContrastResults(F=F, df_denom=self.df_resid, 
                    df_num=invcov.shape[0])

    def conf_int(self, alpha=.05, cols=None):
        """
        Returns the confidence interval of the specified params estimates.

        Parameters
        ----------
        alpha : float, optional
            The `alpha` level for the confidence interval.
            ie., `alpha` = .05 returns a 95% confidence interval.
        cols : tuple, optional
            `cols` specifies which confidence intervals to return
                
        Returns : array
            Each item contains [lower, upper]
        
        Example
        -------
        >>>import numpy as np
        >>>from numpy.random import standard_normal as stan
        >>>import nipy.fixes.scipy.stats.models as SSM
        >>>x = np.hstack((stan((30,1)),stan((30,1)),stan((30,1))))
        >>>params=np.array([3.25, 1.5, 7.0])
        >>>y = np.dot(x,params) + stan((30))
        >>>model = SSM.regression.OLSModel(x, hascons=False).fit(y)
        >>>model.conf_int(cols=(1,2))

        Notes
        -----
        TODO:
        tails : string, optional
            `tails` can be "two", "upper", or "lower"
        """
        if self.__class__.__name__ in ['RLMResults','GLMResults']:
            dist = norm
        else:
            dist = t
        if cols is None and dist == t:
            lower = self.params - dist.ppf(1-alpha/2,self.df_resid) *\
                    self.bse
            upper = self.params + dist.ppf(1-alpha/2,self.df_resid) *\
                    self.bse
        elif cols is None and dist == norm:
            lower = self.params - dist.ppf(1-alpha/2)*self.bse
            upper = self.params + dist.ppf(1-alpha/2)*self.bse
        elif cols is not None and dist == t:
            lower=[]
            upper=[]
            for i in cols:
                lower.append(self.params[i] - dist.ppf(1-\
                        alpha/2,self.df_resid) *self.bse) 
                upper.append(self.params[i] + dist.ppf(1-\
                        alpha/2,self.df_resid) *self.bse)
        elif cols is not None and dist == norm:
            lower = self.params - dist.ppf(1-alpha/2)*self.bse
            upper = self.params + dist.ppf(1-alpha/2)*self.bse
        return np.asarray(zip(lower,upper))




