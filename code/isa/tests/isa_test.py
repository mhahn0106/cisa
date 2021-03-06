import sys
import unittest

sys.path.append('./code')

from isa import ISA
from numpy import sqrt, sum, square, dot, var, eye, cov, diag, std, max, asarray, mean
from numpy import ones, cos, sin, all, sort, log, pi, exp, copy
from numpy.linalg import inv, eig
from numpy.random import randn, permutation
from scipy.optimize import check_grad
from scipy.stats import kstest, laplace, ks_2samp
from tempfile import mkstemp
from pickle import dump, load

class Tests(unittest.TestCase):
	def test_default_parameters(self):
		isa = ISA(2, 4)
		params = isa.default_parameters()

		# simple sanity checks
		self.assertTrue(isinstance(params, dict))
		self.assertEqual(sys.getrefcount(params) - 1, 1)
		self.assertEqual(sys.getrefcount(params['sgd']) - 1, 1)
		self.assertEqual(sys.getrefcount(params['lbfgs']) - 1, 1)
		self.assertEqual(sys.getrefcount(params['mp']) - 1, 1)
		self.assertEqual(sys.getrefcount(params['gsm']) - 1, 1)
		self.assertEqual(sys.getrefcount(params['gibbs']) - 1, 1)
		self.assertEqual(sys.getrefcount(params['ais']) - 1, 1)
		self.assertEqual(sys.getrefcount(params['merge']) - 1, 1)



	def test_nullspace_basis(self):
		isa = ISA(2, 5)
		B = isa.nullspace_basis()

		# simple sanity checks
		self.assertTrue(B.shape[0], 3)
		self.assertTrue(B.shape[1], 5)

		# B should be orthogonal to A and orthonormal
		self.assertLess(max(abs(dot(isa.A, B.T).flatten())), 1e-10)
		self.assertLess(max(abs((dot(B, B.T) - eye(3)).flatten())), 1e-10)

		self.assertEqual(sys.getrefcount(B) - 1, 1)



	def test_initialize(self):
		def sqrtmi(mat):
			"""
			Compute matrix inverse square root.

			@type  mat: array_like
			@param mat: matrix for which to compute inverse square root
			"""

			# find eigenvectors
			eigvals, eigvecs = eig(mat)

			# eliminate eigenvectors whose eigenvalues are zero
			eigvecs = eigvecs[:, eigvals > 0.]
			eigvals = eigvals[eigvals > 0.]

			# inverse square root
			return dot(eigvecs, dot(diag(1. / sqrt(eigvals)), eigvecs.T))

		# white data
		data = randn(5, 1000)
		data = dot(sqrtmi(cov(data)), data)

		isa = ISA(5, 10)
		isa.initialize(data)

		# rows of A should be roughly orthogonal
		self.assertLess(sum(square(dot(isa.A, isa.A.T) - eye(5)).flatten()), 1e-3)

		p = kstest(
			isa.sample_prior(100).flatten(),
			lambda x: laplace.cdf(x, scale=1. / sqrt(2.)))[1]

		# prior marginals should be roughly Laplace
		self.assertGreater(p, 0.0001)

		# test initialization with larger subspaces
		isa = ISA(5, 10, ssize=2)
		isa.initialize(data)



	def test_orthogonalize(self):
		isa = ISA(4, 8)
		isa.orthogonalize()

		self.assertLess(sum(square(dot(isa.A, isa.A.T) - eye(4)).flatten()), 1e-3)



	def test_subspaces(self):
		isa = ISA(2, 4, 2)

		# simple sanity checks
		self.assertEqual(isa.subspaces()[0].dim, 2)
		self.assertEqual(isa.subspaces()[1].dim, 2)

		self.assertEqual(sys.getrefcount(isa.subspaces()), 1)
		self.assertEqual(sys.getrefcount(isa.subspaces()[0]), 1)



	def test_train(self):
		# make sure train() doesn't throw any errors
		isa = ISA(2)
		params = isa.default_parameters()
		params['verbosity'] = 0
		params['max_iter'] = 2
		params['training_method'] = 'SGD'
		params['sgd']['max_iter'] = 1
		params['sgd']['batch_size'] = 57

		isa.initialize(randn(2, 1000))
		isa.train(randn(2, 1000), params)

		isa = ISA(4, ssize=2)
		isa.initialize(randn(4, 1000))
		isa.train(randn(4, 1000), params)

		isa = ISA(2, 3)
		params['gibbs']['ini_iter'] = 2
		params['gibbs']['num_iter'] = 2
		params['verbosity'] = 0
		params['gibbs']['verbosity'] = 0
		isa.initialize(randn(2, 1000))
		isa.train(randn(2, 1000), params)



	def test_train_lbfgs(self):
		isa = ISA(2)
		isa.initialize()

		isa.A = eye(2)

		samples = isa.sample(10000)

		# initialize close to original parameters
		isa.A = asarray([[cos(0.4), sin(0.4)], [-sin(0.4), cos(0.4)]])

		params = isa.default_parameters()
		params['training_method'] = 'LBFGS'
		params['train_prior'] = False
		params['max_iter'] = 1
		params['lbfgs']['max_iter'] = 50

		isa.train(samples, params)

		# L-BFGS should be able to recover the parameters
		self.assertLess(sqrt(sum(square(isa.A.flatten() - eye(2).flatten()))), 0.1)



	def test_train_mp(self):
		isa = ISA(5, 10)

		params = isa.default_parameters()
		params['training_method'] = 'MP'
		params['mp']['num_coeff'] = 4

		samples = isa.sample(100)

		states = isa.matching_pursuit(samples, params)

		# simple sanity checks
		self.assertEqual(states.shape[1], 100)
		self.assertEqual(states.shape[0], 10)
		self.assertFalse(any(sum(states > 0., 0) > 4))

		# make sure training with MP doesn't throw any errors
		isa.train(isa.sample(1011), params)



	def test_sample_prior(self):
		isa = ISA(5, 10)
		samples = isa.sample_prior(20)

		# simple sanity checks
		self.assertEqual(samples.shape[0], 10)
		self.assertEqual(samples.shape[1], 20)



	def test_sample(self):
		isa = ISA(3, 4)

		samples = isa.sample(100)
		samples_prior = isa.sample_prior(100)

		# simple sanity checks
		self.assertEqual(samples.shape[0], isa.num_visibles)
		self.assertEqual(samples.shape[1], 100)
		self.assertEqual(samples_prior.shape[0], isa.num_hiddens)
		self.assertEqual(samples_prior.shape[1], 100)



	def test_prior_energy_gradient(self):
		isa = ISA(4)

		samples = isa.sample_prior(100)
		grad = isa.prior_energy_gradient(samples)

		# simple sanity checks
		self.assertEqual(grad.shape[0], samples.shape[0])
		self.assertEqual(grad.shape[1], samples.shape[1])

		f = lambda x: isa.prior_energy(x.reshape(-1, 1)).flatten()
		df = lambda x: isa.prior_energy_gradient(x.reshape(-1, 1)).flatten()

		for i in range(samples.shape[1]):
			relative_error = check_grad(f, df, samples[:, i]) / sqrt(sum(square(df(samples[:, i]))))

			# comparison with numerical gradient
			self.assertLess(relative_error, 0.001)



	def test_loglikelihood(self):
		isa = ISA(7, ssize=3)

		samples = isa.sample(100)

		energy = isa.prior_energy(dot(inv(isa.A), samples))
		loglik = isa.loglikelihood(samples)

		# difference between loglik and -energy should be const
		self.assertTrue(var(loglik + energy) < 1e-10)

		isa = ISA(2, 3)

		samples = isa.sample(20)

		params = isa.default_parameters()
		params['ais']['num_samples'] = 5
		params['ais']['num_iter'] = 10

		loglik = isa.loglikelihood(samples, params, return_all=True)

		# simple sanity checks
		self.assertTrue(loglik.shape[0], params['ais']['num_samples'])
		self.assertTrue(loglik.shape[1], samples.shape[1])



	def test_callback(self):
		isa = ISA(2)

		# callback function
		def callback(i, isa_):
			callback.count += 1
			self.assertTrue(isa == isa_)
		callback.count = 0

		# set callback function
		parameters = {
				'verbosity': 0,
				'max_iter': 7,
				'callback': callback,
				'sgd': {'max_iter': 0}
			}

		isa.train(randn(2, 1000), parameters=parameters)

		# test how often callback function was called
		self.assertEqual(callback.count, parameters['max_iter'] + 1)

		def callback(i, isa_):
			if i == 5:
				return False
			callback.count += 1
		callback.count = 0

		parameters['callback'] = callback

		isa.train(randn(2, 1000), parameters=parameters)

		# test how often callback function was called
		self.assertEqual(callback.count, 5)

		# make sure referece counts stay stable
		self.assertEqual(sys.getrefcount(isa) - 1, 1)
		self.assertEqual(sys.getrefcount(callback) - 1, 2)



	def test_sample_scales(self):
		isa = ISA(2, 5, num_scales=4)

		# get a copy of subspaces
		subspaces = isa.subspaces()

		# replace scales
		for gsm in subspaces:
			gsm.scales = asarray([1., 2., 3., 4.])

		isa.set_subspaces(subspaces)

		samples = isa.sample_prior(100000)
		scales = isa.sample_scales(samples)

		# simple sanity checks
		self.assertEqual(scales.shape[0], isa.num_hiddens)
		self.assertEqual(scales.shape[1], samples.shape[1])

		priors = mean(abs(scales.flatten() - asarray([[1., 2., 3., 4.]]).T) < 0.5, 1)

		# prior probabilities of scales should be equal and sum up to one
		self.assertLess(max(abs(priors - 1. / subspaces[0].num_scales)), 0.01)
		self.assertLess(abs(sum(priors) - 1.), 1e-10)



	def test_sample_posterior(self):
		isa = ISA(2, 3, num_scales=10)
		isa.A = asarray([[1., 0., 1.], [0., 1., 1.]])

		isa.initialize()

		params = isa.default_parameters()
		params['gibbs']['verbosity'] = 0
		params['gibbs']['num_iter'] = 100

		states_post = isa.sample_posterior(isa.sample(1000), params)
		states_prio = isa.sample_prior(states_post.shape[1])

		states_post = states_post.flatten()
		states_post = states_post[permutation(states_post.size)]
		states_prio = states_prio.flatten()
		states_prio = states_prio[permutation(states_prio.size)]

		# on average, posterior samples should be distributed like prior samples
		p = ks_2samp(states_post, states_prio)[1]

		self.assertGreater(p, 0.0001)

		samples = isa.sample(100)
		states = isa.sample_posterior(samples, params)

		# reconstruction should be perfect
		self.assertLess(sum(square(dot(isa.A, states) - samples).flatten()), 1e-10)



	def test_sample_posterior_ais(self):
		isa = ISA(2, 3, num_scales=10)
		isa.A = asarray([[1., 0., 1.], [0., 1., 1.]])

		isa.initialize()

		params = isa.default_parameters()
		params['ais']['verbosity'] = 0
		params['ais']['num_iter'] = 100

		samples = isa.sample(100)
		states, _ = isa.sample_posterior_ais(samples, params)

		# reconstruction should be perfect
		self.assertLess(sum(square(dot(isa.A, states) - samples).flatten()), 1e-10)



	def test_evaluate(self):
		isa1 = ISA(2)
		isa1.A = eye(2)

		subspaces = isa1.subspaces()
		for gsm in subspaces:
			gsm.scales = ones(gsm.num_scales)
		isa1.set_subspaces(subspaces)

		# equivalent overcomplete model
		isa2 = ISA(2, 4)
		A = copy(isa2.A)
		A[:, :2] = isa1.A / sqrt(2.)
		A[:, 2:] = isa1.A / sqrt(2.)
		isa2.A = A

		subspaces = isa2.subspaces()
		for gsm in subspaces:
			gsm.scales = ones(gsm.num_scales)
		isa2.set_subspaces(subspaces)

		data = isa1.sample(100)

		# the results should not depend on the parameters
		ll1 = isa1.evaluate(data)
		ll2 = isa2.evaluate(data)

		self.assertLess(abs(ll1 - ll2), 1e-5)

		isa1 = ISA(2)
		isa1.initialize()

		# equivalent overcomplete model
		isa2 = ISA(2, 4)

		isa2.set_subspaces(isa1.subspaces() * 2)
		A = isa2.basis()
		A[:, :2] = isa1.basis()
		A[:, 2:] = 0.
		isa2.set_basis(A)

		data = isa1.sample(100)

		params = isa2.default_parameters()
		params['ais']['num_iter'] = 100
		params['ais']['num_samples'] = 100

		ll1 = isa1.evaluate(data)
		ll2 = isa2.evaluate(data, params)

		self.assertLess(abs(ll1 - ll2), 0.1)



	def test_merge(self):
		isa1 = ISA(5, ssize=2)
		isa2 = ISA(5)

		isa1.initialize()
		isa1.orthogonalize()

		isa2.initialize()
		isa2.A = isa1.A

		params = isa2.default_parameters()
		params['train_basis'] = False
		params['merge_subspaces'] = True
		params['merge']['verbosity'] = 0

		isa2.train(isa1.sample(10000), params)

		ssizes1 = [gsm.dim for gsm in isa1.subspaces()]
		ssizes2 = [gsm.dim for gsm in isa2.subspaces()]

		# algorithm should be able to recover subspace sizes
		self.assertTrue(all(sort(ssizes1) == sort(ssizes2)))



	def test_pickle(self):
		isa0 = ISA(4, 16, ssize=3)
		isa0.set_hidden_states(randn(16, 100))

		tmp_file = mkstemp()[1]

		# store model
		with open(tmp_file, 'w') as handle:
			dump({'isa': isa0}, handle)

		# load model
		with open(tmp_file) as handle:
			isa1 = load(handle)['isa']

		# make sure parameters haven't changed
		self.assertEqual(isa0.num_visibles, isa1.num_visibles)
		self.assertEqual(isa0.num_hiddens, isa1.num_hiddens)
		self.assertLess(max(abs(isa0.A - isa1.A)), 1e-20)
		self.assertLess(max(abs(isa0.hidden_states() - isa1.hidden_states())), 1e-20)
		self.assertLess(max(abs(isa0.subspaces()[1].scales - isa1.subspaces()[1].scales)), 1e-20)



if __name__ == '__main__':
	unittest.main()
